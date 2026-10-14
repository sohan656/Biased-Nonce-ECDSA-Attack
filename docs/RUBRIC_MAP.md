# Stage II Progress Evaluation — Evidence Map (target: 10/10)

How each deliverable in this project maps to the rubric's **Excellent** column.
Use this as your demo-day checklist and talking-track.

---

### 1 · Progress Against Proposed Plan — target 2/2
*Excellent: work substantially exceeds planned milestones; systematic progress.*

- All 6 synopsis phases through Phase 5 are **complete**; Phase 6 (report/demo)
  is underway. See the phase table in `docs/DEVLOG.md`.
- **Exceeded the plan**: added a live interactive **web dashboard** and a
  self-recovery-verification step that were not in the synopsis.
- **Show:** the phase table in DEVLOG; say "we are at the Week 9–11 milestone
  with working recovery *and* empirical evaluation already done."

### 2 · Technical Implementation — target 2/2
*Excellent: functional core; sound security concepts; correct coding; independent problem solving.*

- **Functional:** `python3 demo.py` recovers and **verifies** the private key for
  all three bias models in ~2.5 s each.
- **Sound concepts:** correct ECDSA, correct HNP reduction, correct Curve448
  math (`N·G = ∞` self-test), LLL implemented from first principles.
- **Independent problem solving:** entire SageMath PoC re-implemented in pure
  Python (curve, modular arithmetic, LLL) because Sage/fpylll were unavailable.
- **Show:** run `demo.py` live; point out `verified vs public Q: True`.

### 3 · Testing & Preliminary Results — target 2/2
*Excellent: appropriate test cases/metrics; results documented and interpreted.*

- **Self-tests** in every module (`ecc.py`, `lll.py`) + a plain-signature
  verification sanity check.
- **Metrics:** recovery success rate, minimum signatures/bias, runtime.
- **Documented & interpreted results:** success-rate curve shows a sharp
  transition at the predicted boundary (`fig_success_vs_bias.png`); trade-off and
  runtime curves included; model comparison table.
- **Show:** the figures in `results/`, and the live charts in the dashboard.

### 4 · Problem Solving & Adaptability — target 2/2
*Excellent: identifies challenges, explains root causes, implements justified solutions.*

- The **three-attempt LLL story** (DEVLOG §B): rational-GSO (too slow) →
  integer-determinant (blow-up) → exact-basis + high-precision `decimal` GSO
  (works). Each failure's **root cause** is explained and the fix justified.
- Numerical-stability fix (float → decimal precision scaled to entry size) and
  the lattice integer-scaling trick (`×2^l`) are concrete, defensible decisions.
- **Show:** DEVLOG §B; be ready to explain *why* float64 failed (53-bit mantissa
  vs 450-bit entries).

### 5 · Documentation & Presentation — target 2/2
*Excellent: clear records, diagrams/screenshots/logs, strong technical communication.*

- **README.md** (overview, math, run instructions, results, mitigations),
  **DEVLOG.md** (dated log + progress table), **RUBRIC_MAP.md** (this file),
  figures in `results/`, inline math/docstrings in every source file.
- **Presentation asset:** `docs/progress_presentation.html` — a one-screen,
  rubric-aligned summary to project on demo day.
- **Show:** open the presentation page; walk the panels left to right.

---

## Demo-day script (3 minutes)

1. **Motivate (20s):** "ECDSA is only safe if every nonce is perfectly random.
   A few leaked bits per nonce lets us recover the whole private key."
2. **Live attack (45s):** run `python3 demo.py` → point at the ✓ verified line.
3. **Dashboard (45s):** `python3 web/app.py`, run Zero-MSB `l=20,t=25`; slide `l`
   down to show it fail at the boundary.
4. **Results (40s):** show `fig_success_vs_bias.png` — the 0→100% transition.
5. **Problem solving (30s):** the LLL three-attempt story.
6. **Mitigation (10s):** "RFC 6979 deterministic nonces close this."

## Likely viva questions (be ready)

- *Why does a biased nonce leak the key?* → the HNP relation `k = z/s + (r/s)d`.
- *What does LLL actually find?* → a short lattice vector whose coordinates are
  the small nonces; `d` sits in a fixed coordinate.
- *Why did you not use Sage?* → unavailable; so we implemented ECC + LLL ourselves.
- *Why decimal and not float in the LLL?* → 450-bit entries need >53-bit precision.
- *How do you know recovery is correct?* → we re-derive `Q = d·G` and compare.
- *The fix?* → RFC 6979 deterministic nonces + constant-time scalar mult.
