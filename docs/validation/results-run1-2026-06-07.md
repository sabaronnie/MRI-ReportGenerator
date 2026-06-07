# Validation Run 1 — threshold-crossing on real healthy + unhealthy MRI (2026-06-07)

First end-to-end validation on real cervical MRI: **12 healthy** (Spine-Generic) vs **10 symptomatic**
(MMCSD cervical spondylosis: 5 CSM + 5 CSR). Segmentation: TotalSpineSeg (G1/G4) + Spinal Cord Toolbox
(G3), Colab A100. Measurements run locally with our methods. Design = **threshold-crossing**
(healthy normal-side; pathology crosses) — no per-case radiologist GT (see `validation-design-and-decisions.md`).

## Cohort summary
| Measure | Healthy (n=12) | Unhealthy (n=10) | Threshold | Verdict |
|---|---|---|---|---|
| **G3 canal AP min** | median **11.7 mm** [10.5–14.5], 0% <10 | median **8.6 mm** [7.5–10.0], **100% <10** | <10 mm stenosis | ✅ **clean separation** |
| **G3 SAC min** | median **4.7 mm** [3.6–7.2], 0% <3 | median **2.3 mm** [1.8–3.4], **80% <3** | <3 mm risk | ✅ **clean separation** |
| **G3 cord AP min** | median 6.3 mm [5.6–6.7] | median 5.5 mm [5.1–6.5] | normative | ✅ thinner (cord compression) |
| **G4 Cobb C3-C7** (canal-cut) | median −3.2° (noisy, 1 outlier +56°) | median **−13.2°** (more kyphotic) | descriptive | ⚠️ right direction, noisy → needs C1 |
| **G1 Ha/Hp compression** | median 0.92, **0% flag** | median 0.94, **0% flag** | <0.68 | ✅ correctly flat (see note) |

## Reading it
- **G3 (canal stenosis + SAC) is the headline: textbook threshold-crossing.** The distributions barely
  touch (healthy canal-min floor 10.5 mm vs unhealthy ceiling 9.97 mm). Healthy sits normal, the
  spondylosis cohort crosses into stenosis exactly as a CSM/CSR cohort should. **G3 discriminates.**
- **G4 Cobb:** unhealthy is clearly more kyphotic (−13° vs −3°) = the expected loss of lordosis in
  spondylosis — directionally correct. But the canal-cut method is noisy (a +56° healthy endpoint
  outlier; only 9/12 measurable). The SPINEPS endplate-voxel **C1** method (Run B) is the fix for the
  absolute values; the cohort *direction* already separates.
- **G1 Ha/Hp compression = 0% flags in BOTH cohorts, and that is correct, not a failure.** Spondylosis
  is degenerative, not compression-fracture — so MMCSD vertebral heights are normal (true negatives).
  This empirically confirms the design point: MMCSD does not exercise the compression axis (that needs a
  dedicated compression-fracture set — the documented gap). Healthy 0% flag also re-confirms specificity.
- **cord AP** thinner in unhealthy (5.5 vs 6.3 mm) — consistent with cord flattening under compression.

## Honest caveats (for the report)
- **n is small** (12 vs 10) and the 10 unhealthy were **selected to have mid-cervical lesions**, so the
  G3 separation is partly by construction. A random/representative draw from the 250 MMCSD (next step)
  will test whether separation holds without cherry-picking.
- Healthy = young Spine-Generic controls (wide canals) → the clean 0% over-flag on canal<10 / SAC<3 is
  reassuring but an older clinical "normal" population could sit tighter. The earlier worry that
  radiograph-origin SAC<3 / canal<10 over-flags healthy on MRI did **not** materialize on this set (0%).
- G4 absolute Cobb pending the C1 (SPINEPS) run; G2 disc pending Mohammad's code; compression axis (G1)
  pending a fracture dataset.

## Bottom line
First hard evidence that the pipeline **reads normal on healthy and crosses into abnormal on real
pathology** — strongest for **G3 (canal/SAC/cord)**, directionally for **G4**, and with **G1 correctly
silent** on a non-compression cohort. Reproduce: `~/dev/group5-proto/run_validation_cohort.py` on the
Run-A masks. Raw output archived alongside this file.
