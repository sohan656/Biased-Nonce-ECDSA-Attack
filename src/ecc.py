"""
ecc.py  --  Pure-Python elliptic-curve arithmetic for Curve448.

This replaces the SageMath `EllipticCurve` / `GF` objects used in the original
proof-of-concept so the whole project runs on a stock Python install
(no SageMath, no fpylll).

Curve (exactly matching the PoC):
    field prime   p = 2**448 - 2**224 - 1            (the Curve448 / "Goldilocks" prime)
    curve         y^2 = x^3 + A*x^2 + x   with A = 0x262A6 = 156326   (Montgomery form, B = 1)
    group order   n = 2**446 - 0x8335DC163BB124B65129C96FDE933D8D723A70AADC873D6D54A7BB0D
    base point    G = lift_x(5)

Everything here is affine arithmetic with explicit modular inverses. It is NOT
constant-time and is meant for study/experiments, not production use.
"""

from __future__ import annotations
from dataclasses import dataclass

# ----------------------------------------------------------------------------
# Domain parameters  (identical to poc1.py)
# ----------------------------------------------------------------------------
P = 2**448 - 2**224 - 1
A = 0x262A6                      # = 156326
B = 1
N = 2**446 - 0x8335DC163BB124B65129C96FDE933D8D723A70AADC873D6D54A7BB0D


def inv_mod(a: int, m: int) -> int:
    """Modular inverse via Python's built-in extended Euclid (3.8+)."""
    return pow(a % m, -1, m)


def sqrt_mod(a: int, p: int = P) -> int:
    """
    Square root mod p.  p = 2**448 - 2**224 - 1 satisfies p % 4 == 3,
    so a QR has sqrt = a**((p+1)/4) mod p.  Raises if `a` is a non-residue.
    """
    a %= p
    if a == 0:
        return 0
    r = pow(a, (p + 1) // 4, p)
    if (r * r) % p != a:
        raise ValueError("no square root exists for the given x (not on curve)")
    return r


@dataclass(frozen=True)
class Point:
    """Affine point on the curve, or the point at infinity (x = y = None)."""
    x: int | None
    y: int | None

    @property
    def is_infinity(self) -> bool:
        return self.x is None


INF = Point(None, None)


def is_on_curve(Pt: Point) -> bool:
    if Pt.is_infinity:
        return True
    lhs = (B * Pt.y * Pt.y) % P
    rhs = (Pt.x ** 3 + A * Pt.x * Pt.x + Pt.x) % P
    return lhs == rhs


def lift_x(x: int, even: bool = True) -> Point:
    """
    Recover a point from its x-coordinate (Sage's C.lift_x).
    `even` selects which of the two roots to return (deterministic base point).
    """
    x %= P
    rhs = (x ** 3 + A * x * x + x) % P
    y = sqrt_mod(rhs, P)
    if (y % 2 == 0) != even:
        y = (-y) % P
    return Point(x, y)


def neg(Pt: Point) -> Point:
    if Pt.is_infinity:
        return INF
    return Point(Pt.x, (-Pt.y) % P)


def add(Pt: Point, Qt: Point) -> Point:
    """Affine addition on the Montgomery curve y^2 = x^3 + A x^2 + x (B = 1)."""
    if Pt.is_infinity:
        return Qt
    if Qt.is_infinity:
        return Pt
    if Pt.x == Qt.x and (Pt.y + Qt.y) % P == 0:
        return INF  # P + (-P)

    if Pt.x == Qt.x and Pt.y == Qt.y:
        # doubling:  lam = (3x^2 + 2A x + 1) / (2 B y)
        num = (3 * Pt.x * Pt.x + 2 * A * Pt.x + 1) % P
        den = (2 * B * Pt.y) % P
    else:
        # addition:  lam = (y2 - y1) / (x2 - x1)
        num = (Qt.y - Pt.y) % P
        den = (Qt.x - Pt.x) % P

    lam = (num * inv_mod(den, P)) % P
    x3 = (B * lam * lam - A - Pt.x - Qt.x) % P
    y3 = (lam * (Pt.x - x3) - Pt.y) % P
    return Point(x3, y3)


def mul(k: int, Pt: Point) -> Point:
    """Scalar multiplication k*Pt via double-and-add."""
    k %= N
    if k == 0 or Pt.is_infinity:
        return INF
    result = INF
    addend = Pt
    while k:
        if k & 1:
            result = add(result, addend)
        addend = add(addend, addend)
        k >>= 1
    return result


# Canonical base point, matching  G = C.lift_x(F(5))
G = lift_x(5)


if __name__ == "__main__":
    # ---- self-test ----------------------------------------------------------
    assert is_on_curve(G), "G is not on the curve!"
    assert mul(N, G).is_infinity, "N*G should be the identity (wrong order?)"
    # distributivity / basic sanity
    a, b = 123456789, 987654321
    assert add(mul(a, G), mul(b, G)).x == mul(a + b, G).x
    # a round number
    assert mul(2, G).x == add(G, G).x
    print("ecc.py self-test passed")
    print("G.x =", hex(G.x))
    print("G.y =", hex(G.y))
    print("(N)*G is infinity:", mul(N, G).is_infinity)
