#!/usr/bin/env python3
"""
demo.py -- End-to-end demonstration of the biased-nonce ECDSA key-recovery attack.

Run:  python3 demo.py

For each biased-nonce model it (1) generates a fresh key pair, (2) produces
biased signatures, (3) recovers the private key via HNP + LLL, and (4) VERIFIES
the recovered key by re-deriving the public key and comparing to the original.

No SageMath, no fpylll -- pure Python (stdlib only).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import ecdsa_hnp as e


BANNER = "=" * 70

# reliable, fast demo parameters (bias bits l, #signatures t)
CASES = [
    ("zero_msb",  "Top l bits of every nonce are ZERO",            20, 25),
    ("zero_lsb",  "Bottom l bits of every nonce are ZERO",         20, 25),
    ("known_msb", "Top l bits of every nonce are LEAKED (known)",  20, 25),
]


def short(x, n=24):
    h = hex(x)[2:]
    return "0x" + h[:n] + "..." + h[-6:]


def main():
    print(BANNER)
    print("  Biased-Nonce ECDSA Private-Key Recovery  (HNP + LLL lattice attack)")
    print("  Curve448  |  pure-Python port of the SageMath proof-of-concept")
    print(BANNER)

    # sanity: a correctly generated signature must verify
    import random
    rng = random.Random()
    d0, Q0 = e.keygen(rng)
    m = b"a normal message"
    r, s = e.sign(m, d0, rng.randrange(1, e.N))
    print(f"\n[sanity]  A normal ECDSA signature verifies: {e.verify(m, r, s, Q0)}")

    total_ok = 0
    for model, desc, l, t in CASES:
        print("\n" + BANNER)
        print(f"  MODEL: {model}   ({desc})")
        print(f"  bias l = {l} bits   |   signatures t = {t}   |   lattice dim = {t+2}")
        print(BANNER)
        t0 = time.time()
        res = e.run_attack(model=model, l=l, t=t)
        dt = time.time() - t0

        print(f"  true  private key d : {short(res['d_true'])}")
        if res["d_rec"] is not None:
            print(f"  recovered         d : {short(res['d_rec'])}")
        print(f"  match               : {res['success']}")
        print(f"  verified vs public Q: {res['verified']}   (re-derived Q = dG)")
        print(f"  wall-clock time     : {dt:.2f} s")
        total_ok += res["success"]

    print("\n" + BANNER)
    print(f"  RESULT: {total_ok}/{len(CASES)} models fully recovered & verified.")
    print(BANNER)


if __name__ == "__main__":
    main()
