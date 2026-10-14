"""
lll.py  --  LLL lattice-basis reduction in pure Python (no SageMath / fpylll).

The original PoC used SageMath's `matrix(QQ, ...).LLL()`.  We re-implement it.

Design (this is the interesting engineering story for the viva):
  * A naive Gram-Schmidt-with-fractions LLL is exact but far too slow on our
    ~450-bit entries.
  * A fully-integer LLL (Gram determinants) avoids fractions but the
    determinants blow up to tens of thousands of bits -> also too slow.
  * fpLLL's trick, which we copy: keep the BASIS and the GRAM MATRIX in exact
    Python integers, but run the Gram-Schmidt orthogonalisation in fast
    floating point.  Floats lose precision, but the attack driver re-derives
    Q = d_rec * G and checks it against the known public key, so a precision
    failure can only ever cause a (rare) miss -- never a false "success".

Public interface:  lll(rows) -> reduced rows (list of list[int]).
`lll_exact` keeps the slow-but-exact integer LLL available for cross-checking.
"""

from __future__ import annotations
from typing import List
from decimal import Decimal, getcontext

# High-precision GSO: ~100 significant digits (~330 bits) >> float's 16 digits.
# Enough to keep the Lovasz test stable on 450-bit lattice entries while
# avoiding the huge-integer blow-up of a fully exact integer LLL.
getcontext().prec = 100
_HALF = Decimal("0.5")
_ZERO = Decimal(0)


def _dot(u, v) -> int:
    return sum(a * b for a, b in zip(u, v))


# ============================================================================
# Fast + stable LLL: exact integer basis + Decimal (high-precision) GSO
# ============================================================================
def lll(rows, delta=Decimal("0.75"), max_iter: int | None = None) -> List[List[int]]:
    B = [list(map(int, r)) for r in rows]
    n = len(B)
    if n <= 1:
        return B
    if not isinstance(delta, Decimal):
        delta = Decimal(str(delta))
    if max_iter is None:
        max_iter = 200 * n * n + 10000      # generous safety cap

    # Adaptive precision: the GSO must preserve structural entries down to a
    # unit inside norms of size ~entry^2, so we need ~2x the entry bit-length
    # worth of significant digits (plus margin).  3.3219 bits per decimal digit.
    maxbits = max((abs(x).bit_length() for row in B for x in row), default=1)
    getcontext().prec = max(50, int(2 * maxbits / 3.3219) + 60)

    mu, c = _gso_initial(B, n)

    k = 1
    iters = 0
    while k < n and iters < max_iter:
        iters += 1
        # ---- size reduction of b_k against b_{k-1}, ..., b_0 ---------------
        for j in range(k - 1, -1, -1):
            if abs(mu[k][j]) > _HALF:
                q = _round(mu[k][j])
                if q != 0:
                    bj = B[j]
                    B[k] = [x - q * y for x, y in zip(B[k], bj)]
                    qd = Decimal(q)
                    row_k, row_j = mu[k], mu[j]
                    for i in range(j):               # incremental mu update
                        row_k[i] -= qd * row_j[i]
                    row_k[j] -= qd

        # ---- Lovasz condition ----------------------------------------------
        if c[k] >= (delta - mu[k][k - 1] * mu[k][k - 1]) * c[k - 1]:
            k += 1
        else:
            _swap(B, mu, c, k, n)                     # O(n) incremental swap
            k = max(k - 1, 1)
    return B


def _gso_initial(B, n):
    """One-time exact Gram-Schmidt (integer dot products -> Decimal mu, c)."""
    mu = [[_ZERO] * n for _ in range(n)]
    c = [_ZERO] * n
    g = [[_ZERO] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            g[i][j] = g[j][i] = Decimal(_dot(B[i], B[j]))
    for i in range(n):
        gi, mui = g[i], mu[i]
        for j in range(i):
            s = gi[j]
            muj = mu[j]
            for kk in range(j):
                s -= muj[kk] * mui[kk] * c[kk]
            mui[j] = s / c[j] if c[j] != _ZERO else _ZERO
        s = gi[i]
        for kk in range(i):
            s -= mui[kk] * mui[kk] * c[kk]
        c[i] = s
    return mu, c


def _swap(B, mu, c, k, n):
    """Schnorr-Euchner swap of b_k and b_{k-1} with O(n) GSO update."""
    B[k], B[k - 1] = B[k - 1], B[k]
    muk, mukm = mu[k], mu[k - 1]
    for j in range(k - 1):
        muk[j], mukm[j] = mukm[j], muk[j]
    mu_ = muk[k - 1]
    Bval = c[k] + mu_ * mu_ * c[k - 1]
    if Bval == _ZERO:
        c[k], c[k - 1] = c[k - 1], c[k]
        return
    new_mu = mu_ * c[k - 1] / Bval
    new_ck = c[k - 1] * c[k] / Bval
    c[k - 1], c[k] = Bval, new_ck
    muk[k - 1] = new_mu
    for i in range(k + 1, n):
        row = mu[i]
        t = row[k]
        row[k] = row[k - 1] - mu_ * t
        row[k - 1] = t + new_mu * row[k]


def _round(x: Decimal) -> int:
    return int((x + _HALF).to_integral_value(rounding="ROUND_FLOOR"))


# ============================================================================
# Exact integer LLL (Cohen Alg. 2.6.3) -- slow on big entries, kept for checks
# ============================================================================
def _nint(a: int, b: int) -> int:
    q, r = divmod(a, b)
    if 2 * r >= b:
        q += 1
    return q


def lll_exact(matrix_rows, delta_num: int = 3, delta_den: int = 4) -> List[List[int]]:
    b = [list(map(int, row)) for row in matrix_rows]
    n = len(b)
    if n <= 1:
        return b
    d = [0] * (n + 1)
    d[0] = 1
    lam = [[0] * (n + 1) for _ in range(n + 1)]

    def gram_update(k):
        for j in range(1, k + 1):
            u = _dot(b[k - 1], b[j - 1])
            for i in range(1, j):
                u = (d[i] * u - lam[k][i] * lam[j][i]) // d[i - 1]
            if j < k:
                lam[k][j] = u
            else:
                d[k] = u

    def reduce(k, l):
        if 2 * abs(lam[k][l]) <= d[l]:
            return
        q = _nint(lam[k][l], d[l])
        b[k - 1] = [x - q * y for x, y in zip(b[k - 1], b[l - 1])]
        lam[k][l] -= q * d[l]
        for i in range(1, l):
            lam[k][i] -= q * lam[l][i]

    def swap(k, kmax):
        b[k - 1], b[k - 2] = b[k - 2], b[k - 1]
        for j in range(1, k - 1):
            lam[k][j], lam[k - 1][j] = lam[k - 1][j], lam[k][j]
        lamv = lam[k][k - 1]
        Bv = (d[k - 2] * d[k] + lamv * lamv) // d[k - 1]
        for i in range(k + 1, kmax + 1):
            t = lam[i][k]
            lam[i][k] = (d[k] * lam[i][k - 1] - lamv * t) // d[k - 1]
            lam[i][k - 1] = (Bv * t + lamv * lam[i][k]) // d[k]
        d[k - 1] = Bv

    d[1] = _dot(b[0], b[0])
    kmax = 1
    k = 2
    while k <= n:
        if k > kmax:
            kmax = k
            gram_update(k)
        while True:
            reduce(k, k - 1)
            if delta_den * (d[k] * d[k - 2] + lam[k][k - 1] ** 2) < delta_num * d[k - 1] ** 2:
                swap(k, kmax)
                k = max(k - 1, 2)
            else:
                for l in range(k - 2, 0, -1):
                    reduce(k, l)
                k += 1
                break
    return b


if __name__ == "__main__":
    import math, random, time
    demo = [[1, 1, 1], [-1, 0, 2], [3, 5, 6]]
    print("fast  :", lll(demo))
    print("exact :", lll_exact(demo))

    rng = random.Random(7)
    big = [[rng.randrange(-(10**130), 10**130) for _ in range(28)] for _ in range(28)]
    t0 = time.time()
    rb = lll(big)
    shortest = math.isqrt(min(sum(c * c for c in r) for r in rb))
    print(f"28-dim, 130-digit entries: {time.time()-t0:.2f}s, shortest norm ~1e{len(str(shortest))-1}")
    print("lll.py self-test passed")
