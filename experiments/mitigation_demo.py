#!/usr/bin/env python3
"""
mitigation_demo.py -- show that RFC 6979 deterministic nonces defeat the attack.

1. RFC 6979 nonces are deterministic and produce valid signatures.
2. With unbiased (full-size) nonces there is no short lattice vector, so the
   HNP/LLL attack that recovered the key under bias now FAILS to recover it.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import ecdsa_hnp as e
from src.ecc import N, G
import src.ecc as ecc

print("=" * 64)
print("  MITIGATION CHECK: RFC 6979 deterministic nonces")
print("=" * 64)

rng = random.Random(1234)
d, Q = e.keygen(rng)

# (1) determinism + validity
m = b"transfer 100 coins to Alice"
r1, s1 = e.sign_rfc6979(m, d)
r2, s2 = e.sign_rfc6979(m, d)
print(f"\n[1] deterministic : same (r,s) on repeat? {(r1, s1) == (r2, s2)}")
print(f"    signature valid: {e.verify(m, r1, s1, Q)}")

# (2) run the SAME attack pipeline against unbiased RFC-6979 signatures
l, t = 20, 25
samples = []
while len(samples) < t:
    msg = os.urandom(16)
    z = e.H(msg)
    r, s = e.sign_rfc6979(msg, d)
    a = (r * ecc.inv_mod(s, N)) % N
    b = (z * ecc.inv_mod(s, N)) % N
    samples.append(e.Sample(r, s, z, a, b))

d_rec, info = e.solve(samples, l, Q)
recovered = (d_rec is not None and d_rec == d)
print(f"\n[2] attack with l={l}, t={t} against RFC-6979 signatures:")
print(f"    key recovered?  {recovered}   (expected: False)")
print(f"    verified vs Q?  {info['verified']}   (expected: False)")

print("\n" + "=" * 64)
print("  CONCLUSION: deterministic nonces remove the bias the attack needs.")
print("  The exact same lattice pipeline that broke biased ECDSA fails here.")
print("=" * 64)
