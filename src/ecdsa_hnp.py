"""
ecdsa_hnp.py  --  ECDSA signing + biased-nonce key recovery via the
                  Hidden Number Problem (HNP) and LLL lattice reduction.

================================================================================
THE MATH (keep this handy for the viva)
================================================================================
ECDSA signing produces, for message hash z, nonce k, private key d:

        s = (z + r * d) / k   (mod n)        where  r = x-coord(k*G) mod n

Rearranging to isolate the nonce:

        k = (z + r*d) / s = (z/s) + (r/s) * d   (mod n)

Define the publicly computable quantities
        a_i = r_i / s_i   (mod n)
        b_i = z_i / s_i   (mod n)
so that for every signature
        k_i = a_i * d + b_i   (mod n).                       (*)

Normally k_i is a uniform ~446-bit number and (*) tells us nothing.  But if the
nonce is BIASED so that k_i is unusually *small* -- e.g. its top l bits are zero,
so  0 <= k_i < 2**(446-l) ~ n / 2**l  -- then (*) says:

        "a_i * d + b_i  mod n  is a small number."

That is exactly the Hidden Number Problem: recover the hidden d from many
noisy/approximate linear relations.  We solve it by building a lattice in which
the vector encoding the true d is unusually short, then calling LLL.

Each bias model below just rewrites the leak as the same shape
        small_i = a_i * d + b_i   (mod n),  small_i < n / 2**l
by choosing a_i, b_i appropriately.
================================================================================
"""

from __future__ import annotations
from hashlib import sha256
import hmac
import os
import time
import random
from dataclasses import dataclass

from . import ecc
from .ecc import N, G
from .lll import lll


# ----------------------------------------------------------------------------
# Hashing + core ECDSA
# ----------------------------------------------------------------------------
def H(msg: bytes) -> int:
    return int.from_bytes(sha256(msg).digest(), "big") % N


def keygen(rng: random.Random | None = None):
    rng = rng or random.Random()
    d = rng.randrange(1, N)
    Q = ecc.mul(d, G)
    return d, Q


def sign(msg: bytes, d: int, nonce: int) -> tuple[int, int]:
    """Deterministic-nonce signing (nonce supplied so we can inject bias)."""
    k = nonce % N
    if k == 0:
        raise ValueError("nonce 0")
    r = ecc.mul(k, G).x % N
    if r == 0:
        raise ValueError("r == 0, pick another nonce")
    z = H(msg)
    s = ((z + r * d) * ecc.inv_mod(k, N)) % N
    if s == 0:
        raise ValueError("s == 0, pick another nonce")
    return r, s


def verify(msg: bytes, r: int, s: int, Q: ecc.Point) -> bool:
    z = H(msg)
    w = ecc.inv_mod(s, N)
    u1 = (z * w) % N
    u2 = (r * w) % N
    Pt = ecc.add(ecc.mul(u1, G), ecc.mul(u2, Q))
    if Pt.is_infinity:
        return False
    return Pt.x % N == r


# ----------------------------------------------------------------------------
# Biased-nonce generators.  `l` = number of leaked/zero bits of bias.
# Nonce bit-length for this curve is 446.
# ----------------------------------------------------------------------------
NBITS = 446


def nonce_zero_msb(l: int, rng: random.Random) -> int:
    """Top l bits are zero  ->  k < 2**(446-l)."""
    return rng.getrandbits(NBITS - l)


def nonce_zero_lsb(l: int, rng: random.Random) -> int:
    """Bottom l bits are zero  ->  k = k' << l,  k' < 2**(446-l)."""
    return rng.getrandbits(NBITS - l) << l


def nonce_known_msb(l: int, rng: random.Random):
    """Uniform nonce, but we leak its top l bits as `p`."""
    k = rng.randrange(1, N)
    p = k >> (NBITS - l)
    return k, p


# ----------------------------------------------------------------------------
# Signature collection for each model -> list of rows [a_i, b_i] + bookkeeping
# ----------------------------------------------------------------------------
@dataclass
class Sample:
    r: int
    s: int
    z: int
    a: int          # a_i = r/s mod n
    b: int          # b_i depends on model (so that a*d + b mod n is small)


def collect(model: str, d: int, l: int, t: int, rng: random.Random) -> list[Sample]:
    samples: list[Sample] = []
    while len(samples) < t:
        msg = os.urandom(16)
        z = H(msg)
        try:
            if model == "zero_msb":
                k = nonce_zero_msb(l, rng)
                r, s = sign(msg, d, k)
                a = (r * ecc.inv_mod(s, N)) % N
                b = (z * ecc.inv_mod(s, N)) % N
            elif model == "zero_lsb":
                k = nonce_zero_lsb(l, rng)
                r, s = sign(msg, d, k)
                inv = ecc.inv_mod((s * pow(2, l, N)) % N, N)
                a = (r * inv) % N
                b = (z * inv) % N                       # leaked low bits p = 0
            elif model == "known_msb":
                k, p = nonce_known_msb(l, rng)
                r, s = sign(msg, d, k)
                a = (r * ecc.inv_mod(s, N)) % N
                b = (z * ecc.inv_mod(s, N) - p * pow(2, NBITS - l, N)) % N
            else:
                raise ValueError(f"unknown model {model!r}")
        except ValueError:
            continue
        samples.append(Sample(r, s, z, a, b))
    return samples


# ----------------------------------------------------------------------------
# HNP lattice construction + solve  (pure-Python port of the PoC's matrix)
# ----------------------------------------------------------------------------
def build_basis(samples: list[Sample], l: int):
    """
    Integer lattice (the PoC's QQ matrix scaled by 2**l to clear denominators).

    Rows:
        i in [0, t):   2**l * n * e_i
        row t    :   [2**l*a_0, ..., 2**l*a_{t-1},   1,   0]
        row t+1  :   [2**l*b_0, ..., 2**l*b_{t-1},   0,   n]

    A short vector in this lattice has the form (small_i, d, n), from which the
    private key d is read off directly.
    """
    t = len(samples)
    scale = pow(2, l)
    rows = []
    for i in range(t):
        row = [0] * (t + 2)
        row[i] = scale * N
        rows.append(row)
    row_a = [scale * sm.a for sm in samples] + [1, 0]
    row_b = [scale * sm.b for sm in samples] + [0, N]
    rows.append(row_a)
    rows.append(row_b)
    return rows


def solve(samples: list[Sample], l: int, Q: ecc.Point | None = None):
    """
    Run LLL and extract the private key.  Returns (d_recovered, info_dict).
    If Q is given, the returned d is the one whose public key matches Q.
    """
    basis = build_basis(samples, l)
    reduced = lll(basis)

    candidates = []
    for row in reduced:
        last = row[-1]
        if last in (N, -N):
            d_rec = (row[-2] * (1 if last == N else -1)) % N
            candidates.append(d_rec)

    # try candidates and their negations; verify against Q if available
    tried = []
    for d_rec in candidates:
        for cand in (d_rec, (-d_rec) % N, (N - d_rec) % N):
            if cand in tried:
                continue
            tried.append(cand)
            if Q is None:
                return cand, {"candidates": candidates, "verified": False}
            if ecc.mul(cand, G).x == Q.x:
                return cand, {"candidates": candidates, "verified": True}

    best = candidates[0] if candidates else None
    return best, {"candidates": candidates, "verified": False}


# ----------------------------------------------------------------------------
# One-call end-to-end attack
# ----------------------------------------------------------------------------
def run_attack(model: str = "zero_msb", l: int = 11, t: int = 60, seed: int | None = None):
    rng = random.Random(seed)
    d, Q = keygen(rng)
    samples = collect(model, d, l, t, rng)
    d_rec, info = solve(samples, l, Q)
    return {
        "model": model, "l": l, "t": t,
        "d_true": d, "d_rec": d_rec,
        "success": (d_rec is not None and d_rec == d),
        "verified": info["verified"],
        "Q": Q,
    }


# ----------------------------------------------------------------------------
# MITIGATION: RFC 6979 deterministic nonce generation (HMAC-DRBG).
# A nonce derived deterministically from (d, message) has no exploitable bias,
# so the HNP/LLL attack cannot gain any foothold.
# ----------------------------------------------------------------------------
_QLEN = NBITS                       # 446
_RLEN = (NBITS + 7) // 8            # 56 bytes

def _int2octets(x: int) -> bytes:
    return (x % N).to_bytes(_RLEN, "big")

def _bits2int(b: bytes) -> int:
    x = int.from_bytes(b, "big")
    extra = len(b) * 8 - _QLEN
    return x >> extra if extra > 0 else x

def _bits2octets(b: bytes) -> int:
    return _bits2int(b) % N

def rfc6979_nonce(d: int, msg: bytes) -> int:
    """Deterministic nonce k per RFC 6979 using HMAC-SHA256."""
    h1 = sha256(msg).digest()
    hlen = 32
    x = _int2octets(d)
    h1o = _int2octets(_bits2octets(h1))
    V = b"\x01" * hlen
    K = b"\x00" * hlen
    K = hmac.new(K, V + b"\x00" + x + h1o, sha256).digest()
    V = hmac.new(K, V, sha256).digest()
    K = hmac.new(K, V + b"\x01" + x + h1o, sha256).digest()
    V = hmac.new(K, V, sha256).digest()
    while True:
        T = b""
        while len(T) * 8 < _QLEN:
            V = hmac.new(K, V, sha256).digest()
            T += V
        k = _bits2int(T)
        if 1 <= k < N:
            return k
        K = hmac.new(K, V + b"\x00", sha256).digest()
        V = hmac.new(K, V, sha256).digest()

def sign_rfc6979(msg: bytes, d: int):
    """ECDSA signing with a safe deterministic nonce (the mitigation)."""
    return sign(msg, d, rfc6979_nonce(d, msg))


MODEL_INFO = {
    "zero_msb":  "Top l bits of every nonce k are ZERO  (k < 2^(446-l))",
    "zero_lsb":  "Bottom l bits of every nonce k are ZERO  (k = k' << l)",
    "known_msb": "Top l bits of every nonce k are LEAKED and known to us",
}


def attack_stages(model: str = "zero_msb", l: int = 20, t: int = 25,
                  seed: int | None = None) -> dict:
    """
    Run the full attack with per-stage timing + intermediate data, for the
    live web demo.  Returns a JSON-serialisable dict.
    """
    rng = random.Random(seed)
    stages = []

    def stage(name):
        return {"name": name, "t0": time.time()}

    # 1. key generation
    st = stage("Key generation")
    d, Q = keygen(rng)
    st["seconds"] = round(time.time() - st["t0"], 3)
    st["detail"] = "private key d and public key Q = d*G created"
    stages.append(st)

    # 2. biased signing
    st = stage("Biased signing")
    samples = collect(model, d, l, t, rng)
    st["seconds"] = round(time.time() - st["t0"], 3)
    st["detail"] = f"{t} signatures collected with biased nonces"
    stages.append(st)

    # sample signatures to display (truncated hex)
    def h(x, n=20):
        s = hex(x % N)[2:]
        return s[:n] + ("…" if len(s) > n else "")
    sample_sigs = [{"r": h(sm.r), "s": h(sm.s), "z": h(sm.z)} for sm in samples[:6]]

    # 3. lattice construction
    st = stage("Lattice construction")
    basis = build_basis(samples, l)
    st["seconds"] = round(time.time() - st["t0"], 3)
    st["detail"] = f"{len(basis)}x{len(basis)} HNP lattice (entries ~2^{(l+446)} bits)"
    stages.append(st)

    # 4. LLL reduction + 5. recovery
    st = stage("LLL reduction + key recovery")
    d_rec, info = solve(samples, l, Q)
    st["seconds"] = round(time.time() - st["t0"], 3)
    st["detail"] = "shortest lattice vector -> candidate private key"
    stages.append(st)

    # 6. verification + show that recovered nonces are indeed small
    small_demo = []
    if d_rec is not None:
        for sm in samples[:6]:
            kval = (sm.a * d_rec + sm.b) % N
            small_demo.append({"bits": kval.bit_length()})

    success = (d_rec is not None and d_rec == d)
    verified = info["verified"]

    return {
        "model": model, "model_desc": MODEL_INFO.get(model, ""),
        "l": l, "t": t, "dim": t + 2, "nbits": NBITS,
        "d_true": hex(d), "d_rec": hex(d_rec) if d_rec is not None else None,
        "success": success, "verified": verified,
        "stages": stages,
        "total_seconds": round(sum(s["seconds"] for s in stages), 3),
        "sample_sigs": sample_sigs,
        "recovered_nonce_bits": small_demo,
        "key_bits": NBITS,
    }


if __name__ == "__main__":
    # quick sanity: a normal signature verifies
    rng = random.Random(0)
    d, Q = keygen(rng)
    m = b"testing"
    r, s = sign(m, d, rng.randrange(1, N))
    print("plain signature verifies:", verify(m, r, s, Q))
