# Recovery of ECDSA Private Keys from Biased Nonces
### A Hidden Number Problem + Lattice Reduction Approach

**Information Security Lab — ICT-3141 — Mini Project**
Team: Tejas Raj (33), Sohan Paresh Nikumbh (20), Venkataraman Seshadri (24) · B.Tech CCE-B

A complete, from-scratch implementation that recovers a full **ECDSA private
key** from a handful of signatures whose nonces are *slightly* biased — by
turning the bias into a **Hidden Number Problem (HNP)** and solving it with
**LLL lattice reduction**. It runs on a stock Python install: **no SageMath, no
fpylll** — the elliptic curve, the big-integer modular arithmetic, and the
lattice reducer are all implemented here.

---

## 1. The attack in 60 seconds

ECDSA signs a message hash `z` with private key `d` and a per-signature random
nonce `k`:

```
s = (z + r·d) / k   (mod n),      r = x-coordinate(k·G) mod n
```

Rearrange to isolate the nonce:

```
k = (z/s) + (r/s)·d   (mod n)        ← one linear equation, two unknowns (k, d)
```

For a *uniform* `k` this leaks nothing. But if the nonce is **biased** — say its
top `l` bits are always zero, so `k < n / 2^l` — then the right-hand side is a
**small** number modulo `n`. Collect `t` such signatures and you have `t`
equations of the form

```
a_i·d + b_i   (mod n)   is small          (a_i = r_i/s_i,  b_i = z_i/s_i)
```

This is exactly the **Hidden Number Problem**. We embed it in a lattice where the
vector encoding the true `d` is unusually short, run **LLL**, read `d` off the
shortest vector, and **verify** it by re-deriving `Q = d·G`.

> A bias of only ~13–20 bits per nonce is enough to recover a 446-bit key from
> 25–50 signatures. This is why real nonce bugs (bad RNGs, side channels) are
> catastrophic.

---

## 2. Bias models implemented

| Model | Leak | Reduction to `a_i·d + b_i` small |
|-------|------|----------------------------------|
| **Zero MSB**  | top `l` bits of `k` are 0 | `a=r/s`, `b=z/s` |
| **Zero LSB**  | bottom `l` bits of `k` are 0 | `a=r/(s·2^l)`, `b=z/(s·2^l)` |
| **Known MSB** | top `l` bits of `k` leaked as `p` | `a=r/s`, `b=z/s − p·2^(446−l)` |

(Shared-unknown-MSB is discussed as a future extension; see DEVLOG.)

---

## 3. Repository layout

```
ecdsa-hnp-attack/
├── demo.py                     one-command end-to-end demonstration
├── src/
│   ├── ecc.py                  Curve448 field + point arithmetic (replaces Sage)
│   ├── ecdsa_hnp.py            ECDSA sign/verify, bias models, HNP solve
│   └── lll.py                  LLL lattice reduction, implemented from scratch
├── experiments/
│   ├── run_experiments.py      resumable success-rate / runtime sweeps → CSV
│   └── make_plots.py           CSV → report-ready figures
├── web/
│   ├── app.py                  Flask API (live attack + results)
│   └── templates/index.html    interactive dashboard
├── results/                    experiments.csv + figures
├── docs/                       DEVLOG, mitigations, rubric mapping
├── requirements.txt
└── RUN.md
```

---

## 4. How to run

```bash
# 1) the attack itself — standard library only
python3 demo.py

# 2) the interactive dashboard
pip install flask matplotlib
python3 web/app.py        # → http://127.0.0.1:5000

# 3) reproduce the empirical study (resumable)
python3 experiments/run_experiments.py

# 4) regenerate the figures
python3 experiments/make_plots.py
```

Each source file also runs its own self-test, e.g. `python3 src/ecc.py`
(checks `N·G = ∞`) and `python3 src/lll.py`.

---

## 5. Results (summary)

- **Recovery works and is verified**: the recovered `d` always re-derives the
  exact public key `Q` before we report success (no false positives possible).
- **Sharp recovery boundary**: with `t = 36` signatures fixed, the recovery rate
  jumps from 0 to 100% as the bias crosses ≈15 bits — see
  `results/fig_success_vs_bias.png`.
- **Signatures ↔ bias trade-off**: fewer leaked bits per nonce are compensated by
  more signatures; our pure-Python LLL reliably succeeds once the total leaked
  information exceeds the key size by ~20% (`l·t ≳ 1.2 × 446`).
- **Runtime** of our LLL grows smoothly with the lattice dimension — see
  `results/fig_runtime_vs_dim.png`.

Figures: `fig_success_vs_bias.png`, `fig_success_vs_sigs.png`,
`fig_runtime_vs_dim.png`, `fig_model_comparison.png`.

---

## 6. Implementation notes (the interesting part)

The original proof-of-concept depended entirely on **SageMath** (`EllipticCurve`,
`Zmod`, `matrix(QQ).LLL()`). This environment has no Sage, so every cryptographic
primitive was re-implemented:

- **Curve448** as a Montgomery curve `y² = x³ + 156326·x² + x` over
  `p = 2⁴⁴⁸ − 2²²⁴ − 1`, with affine add/double, `lift_x` via a `p ≡ 3 (mod 4)`
  square root, and double-and-add scalar multiplication.
- **LLL from scratch.** A naïve rational Gram-Schmidt LLL was correct but far too
  slow on 450-bit entries (minutes); a fully-integer LLL blew up to 20,000-bit
  determinants. The working version copies fpLLL's strategy — **exact integer
  basis + high-precision (`decimal`) Gram-Schmidt**, with precision scaled to the
  entry size and incremental O(n) GSO updates. See DEVLOG for the full story.

---

## 7. Mitigations

1. **Deterministic nonces — RFC 6979.** Derive `k` deterministically from the
   private key and message via HMAC, eliminating RNG bias entirely.
2. **Constant-time scalar multiplication** to remove timing/cache side channels
   that leak nonce bits.
3. **Modern signatures (Ed25519/Ed448)** which bake deterministic nonces into the
   scheme.

---

## 8. References

- Boneh & Venkatesan, *Hardness of Computing the MSBs of Secret Keys…*, CRYPTO 1996
- Howgrave-Graham & Smart, *Lattice Attacks on Digital Signature Schemes*, DCC 2001
- Nguyen & Shparlinski, *The Insecurity of (EC)DSA with Partially Known Nonces*, J. Cryptology 2002
- Aranha et al., *LadderLeak: Breaking ECDSA With Less Than One Bit…*, CCS 2020
- Pornin, *Deterministic (EC)DSA*, RFC 6979, 2013

*Educational / defensive-security project. Do not use against systems you do not own.*
