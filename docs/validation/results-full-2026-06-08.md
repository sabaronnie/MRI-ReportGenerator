# Full Validation — all groups, 12 healthy vs 10 unhealthy (2026-06-08)

Threshold-crossing + distribution-separation on real cervical MRI. **Healthy** = 12 Spine-Generic
controls. **Unhealthy** = 10 MMCSD symptomatic spondylosis (5 CSM + 5 CSR, selected to carry
mid-cervical lesions). Segmentation: TotalSpineSeg + Spinal Cord Toolbox (Colab A100) + SPINEPS
(separate session). Measurements + stats run locally. Significance = Mann-Whitney U (two-sided) on the
per-case summary metric. No per-case radiologist GT → we show separation, not sensitivity/specificity.
Design rationale: `validation-design-and-decisions.md`. Reproduce: `~/dev/group5-proto/run_validation_master.py`.

## Headline table
| Measure | Healthy med | Unhealthy med | Mann-Whitney p | Verdict |
|---|---|---|---|---|
| **G3 canal AP min (mm)** | 11.7 (n=12) | 8.6 (n=10) | **0.0001** | ✅ **strong separation** |
| **G3 SAC min (mm)** | 4.7 | 2.3 | **0.0001** | ✅ **strong separation** |
| **G3 cord AP min (mm)** | 6.3 | 5.5 | **0.009** | ✅ significant (cord thinner) |
| **G4 Cobb C1 C3-C7 (deg)** | 15.2 (n=11) | 8.8 (n=10) | 0.13 | ⚠️ directional (loss of lordosis), n.s. at this n |
| **G1 Ha/Hp min** | 0.81 | 0.80 | 0.92 | ✅ correctly null (see below) |
| **G2 DHI median** | 0.23 | 0.26 | 0.05 | ❌ **backwards — bug** |
| **G2 bulge median (mm)** | 2.95 | 0.91 | 0.005 | ❌ **backwards — bug** |

Per-measure strip plots in `figures/` (healthy vs unhealthy, with the p-value).

## Per-group reading

### G3 canal / cord / SAC — VALIDATED (the headline)
Canal-AP minimum and SAC both separate at **p = 0.0001**; the distributions barely touch (healthy
canal floor 10.5 mm vs unhealthy ceiling 9.97 mm). Cord AP is thinner in unhealthy (p = 0.009),
consistent with cord compression. This is exactly the threshold-crossing we wanted: healthy sits
normal, the CSM/CSR cohort crosses into stenosis. **G3 discriminates pathology on real MRI.**

### G4 Cobb (C1, SPINEPS endplate voxels) — method-validated, directional discrimination
C1 reads healthy **+15.2°** (proper lordosis, matches the F1000 literature mean 15.4°) vs unhealthy
**+8.8°** (straightened / reduced lordosis = expected in spondylosis). Direction is correct and C1 is
far cleaner than canal-cut (which gave a +56° healthy outlier). But the separation is **not significant
at this n (p = 0.13)** — alignment is inherently less specific for CSM than stenosis, and n is small.
**Verdict: C1 is the validated *method* (precision + correct lordosis); as a *discriminator* it is
directional only.** canal-cut stays the fallback.

### G1 Ha/Hp compression — correctly NULL (by design, not a failure)
No difference (0.81 vs 0.80, p = 0.92), **0 compression flags in either cohort.** This is the
*expected and correct* result: spondylosis is degenerative, not compression-fracture, so MMCSD
vertebral heights are normal (true negatives). It empirically confirms the design point that MMCSD does
not exercise the compression axis — that axis needs a dedicated cervical compression-fracture dataset
(the one documented data gap; hunt pending). Healthy 0% over-flag re-confirms the 5.2 specificity.

### G2 disc (DHI, AP bulge) — FAILS validation: both metrics read BACKWARDS (bug confirmed)
- **DHI:** healthy 0.23 vs unhealthy 0.26 — healthy reads *more degenerated* than pathological, which
  is impossible. Both are far below Mohammad's anchor (0.49–0.57). `reduced_dhi` fires 77% on healthy.
- **AP bulge:** healthy 2.95 mm vs unhealthy 0.91 mm — healthy reads *more bulge*. Backwards.
- **Root cause (confirmed via the intermediates):** the DHI denominator (adjacent VB middle height) is
  **over-measured at the junction levels** — e.g. healthy `h_upperVB_middle_mm` C2-C3 = **26.6 mm**,
  C7-T1 = 20.5 mm, vs the true cervical ~12–13 mm. An inflated denominator collapses DHI → false
  `reduced_dhi`. Mid-cervical VB heights (C3-C6 ≈ 12–14 mm) are fine, so the bug is level-specific
  (C2 / cervicothoracic junction). The bulge metric also over-reports on healthy (separate issue).
- **Action:** this is Group 2 (Mohammad's) code. Per our teammate-code rule the bug is **documented and
  flagged for Mohammad** (he predicted exactly this denominator discrepancy in his handoff), **not
  blind-rewritten overnight** — a wrong edit to his Duke-tuned algorithm without his review/GT would be
  irresponsible. Candidate fix: robustify `measure_adjacent_body_slice` so junction/C2 VB heights aren't
  over-measured (cap to the body, exclude posterior elements), then re-run this validation.

### G5 (fracture screen + myelomalacia) — VALIDATED (prior runs)
5.2 healthy FP 17%→0%; 5.1 SCIseg ~91% healthy specificity. Unchanged here. The G1-null result above
re-confirms 5.2 specificity on the full 12 healthy.

## What this validation establishes
- The pipeline **reads normal on healthy and crosses into abnormal on real pathology** for **G3
  (p=0.0001)**, directionally for **G4-C1**, with **G1 correctly silent** on a non-compression cohort,
  and **G5** already validated. **4 of 5 groups behave correctly.**
- The validation methodology **works as a bug detector**: it caught that **G2's DHI + bulge are
  backwards** (a real, root-caused bug) — exactly what a validation harness should do.

## Honest caveats
- n small (12 / 10); the 10 unhealthy were **selected to carry mid-cervical lesions**, so part of the
  G3 sharpness is by construction — a random draw from the 250 MMCSD is the next test.
- Healthy = young controls (wide canals). Notably the prior worry that SAC<3 / canal<10 *over-flag*
  healthy on MRI did NOT materialize (0% healthy flagged) — the cuts behaved well here.
- No radiologist GT → separation/precision, not sensitivity/specificity or absolute Cobb accuracy.
- G2 pending the disc-code fix; compression axis pending a fracture dataset; spondylolisthesis remains
  experimental (no supine-MRI threshold).
