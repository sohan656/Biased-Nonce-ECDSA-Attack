# Development Log & Progress Report

Mini project: *Recovery of ECDSA Private Keys from Biased Nonces* (ICT-3141).
This log maps work completed against the **synopsis timeline**, and records the
technical decisions and problems solved along the way.

---

## A. Progress against the proposed plan

The synopsis proposed six phases. Status at this Stage-II checkpoint:

| Phase | Planned deliverable | Status | Evidence |
|------:|---------------------|--------|----------|
| 1 | Literature review (ECDSA, HNP, lattices) | ✅ Done | §C below, README refs |
| 2 | HNP formulation for each bias model | ✅ Done | `src/ecdsa_hnp.py` header + 3 models |
| 3 | Signature simulator with configurable bias | ✅ Done | `collect()`, `nonce_*` generators |
| 4 | Lattice construction + LLL/recovery | ✅ Done | `build_basis()`, `src/lll.py`, verified recovery |
| 5 | Experimentation & evaluation | ✅ Done | `experiments/`, `results/*.csv`, figures |
| 6 | Report, mitigations, demo | 🟡 In progress | README, this log, mitigations §, web demo |

**We are at/ahead of the Week-9–11 milestone**: a working key-recovery script
(Phase 4) *and* an empirical evaluation (Phase 5) are both complete, plus a live
interactive demo that was not in the original plan.

### Objective-by-objective

1. **Derive HNP for each bias model** — ✅ zero-MSB, zero-LSB, known-MSB derived
   and implemented; each reduces to `a_i·d + b_i ≡ small (mod n)`.
2. **Biased-nonce signature simulator** — ✅ on Curve448, configurable `l`, `t`.
3. **Lattice recovery via LLL** — ✅ implemented from scratch (no Sage/fpylll).
4. **Minimum signatures / minimum bias** — ✅ measured empirically; recovery
   boundary ≈ `l·t > 1.2 × 446`.
5. **Success rate, runtime, mitigations** — ✅ success curves + runtime curve +
   RFC 6979 discussion.

---

## B. Chronological development log

**Day 1 — environment & port.**
Target environment had Python 3.13 + NumPy + Matplotlib + Flask, but **no
SageMath and no fpylll**. The provided PoC (`poc1.py`) was 100% Sage. Decision:
re-implement every primitive in pure Python. This became the core of the
project's "problem-solving" work.

**Curve448 arithmetic (`src/ecc.py`).**
Identified the PoC curve `[0,0x262A6,0,1,0]` as **Curve448** in Montgomery form
`y² = x³ + 156326x² + x` over `p = 2⁴⁴⁸−2²²⁴−1`. Implemented affine add/double,
`lift_x` (needs √ mod p; since `p ≡ 3 mod 4`, used `a^((p+1)/4)`), and
double-and-add scalar mult. **Validation:** `N·G = ∞` (confirms both the curve
and the group order) and `(a+b)G = aG + bG`. ✔

**ECDSA + HNP reduction (`src/ecdsa_hnp.py`).**
Implemented sign/verify; confirmed a normal signature verifies. Derived and
coded the three bias models so each yields `a_i·d + b_i ≡ small`.

**LLL — three attempts (the hard part):**
1. *Rational Gram-Schmidt LLL.* Correct, but on 450-bit entries a single
   27-dim reduction **timed out (>2 min)** — exact-fraction GSO on huge numbers.
2. *Fully-integer LLL (Cohen 2.6.3).* No fractions, but the Gram **determinants
   blow up to ~20,000-bit integers**; still ~68 s per solve.
3. *Exact basis + floating-point GSO (fpLLL's trick).* Fast, but **pure float64
   (53-bit mantissa) was numerically unstable** on 450-bit lattices — the Lovász
   test oscillated and the reducer **looped forever**.
**Resolution:** exact integer basis + **`decimal` GSO with precision scaled to
the entry size** (~2× the entry bit-length in digits) + **incremental O(n) GSO
updates**. Stable *and* fast (≈2.5 s at dim 27). Because the driver re-derives
`Q = d·G`, any residual precision issue can only cause a miss, never a false
success.

**Lattice tuning.**
Ported the PoC's `QQ` matrix (fractional `1/2^l`, `n/2^l`) to an **integer**
lattice by scaling by `2^l`; verified it recovers `d` and matches `Q`. Found the
pure-Python LLL needs slightly more signature margin than Sage near the boundary
(e.g. `l=11` wants `t≈65`, not `60`) — recorded as a measured result.

**Evaluation + web demo.**
Built a resumable experiment harness (CSV-backed) and a Flask dashboard that runs
the real attack live and plots the empirical curves.

---

## C. Literature grounding

- **Boneh–Venkatesan (1996)** — introduced the HNP; MSB leakage + lattices ⇒ key
  recovery. Foundation of this attack.
- **Howgrave-Graham–Smart (2001)** — practical lattice attack on (EC)DSA with
  partially known nonces; the lattice shape we use.
- **Nguyen–Shparlinski (2002)** — formal insecurity bounds for partially known
  nonces; informs the `l·t` vs key-size relationship we measure.
- **Aranha et al. (2020), LadderLeak** — sub-bit bias suffices; motivates why
  nonce bias is severe in practice.
- **RFC 6979 (Pornin, 2013)** — deterministic nonces, the primary mitigation.

---

## D. Known limitations / next steps

- Pure-Python LLL is slower than fpLLL and needs ~20% more margin near the
  boundary; a BKZ pass would tighten this.
- Shared-unknown-MSB model (EHNP) outlined but not yet implemented.
- Attack assumes bias from nonce *generation*, not nonce reuse (a separate, even
  easier break).
