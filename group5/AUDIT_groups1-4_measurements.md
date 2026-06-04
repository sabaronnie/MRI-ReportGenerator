# Audit — Groups 1–4 geometric/signal measurement code (teammates')

**Working reference doc (mainly for Claude continuity). Date: 2026-06-05. Auditor: Andrew's Group-5 chat via 8 read-only subagents.**

## Provenance / what was audited
- Branches as pulled into worktrees (one level above the repo, `../teammate-worktrees/`):
  - **Ronnie** = `Standarization-Ronnie` @ `6ab3a2f` (owns G1 vertebra + G3 canal/cord)
  - **Mohammad/"Moka"** = `mokaBranch` @ `1b53cc7` (owns G2 disc + G4 alignment)
  - Merged baseline = `services/` on `groups-5-6`/`main`.
- ⚠️ Reflects these commits only — **re-pull before trusting; teammates may have pushed newer work.**
- All findings are quoted from real code + test files + the colab validation scripts. Read-only; no edits made in worktrees.

## TL;DR verdict
**Their measurement MATH is mostly correct — not nonsense.** The risk is not "broken formulas," it's: **(a) ~nothing validated on real cervical data, (b) 4 of 6 measurements have NO unit tests, (c) almost every clinical cutoff is uncited** (breaks the project's "cite every medical number" rule). Plus a few concrete accuracy holes (below). Cervical accuracy is genuinely **unknown**.

## Scorecard
| Measurement | Math right? | Unit tests? | Real-neck validation? | Numbers cited? | Biggest issue |
|---|---|---|---|---|---|
| Foundation (`context.py` loader/orchestrator) | ✅ mostly | ⚠️ partial | ❌ | n/a (engineering) | thick-slice false precision |
| Bone height (`cervical_body_morphometry.py`) | ✅ | ⚠️ happy-path only | ❌ | ❌ | body-vs-arch isolation fragile on tilt/fusion |
| Bone slippage (`spondylolisthesis.py`) | ✅ | ✅ incl. positive | ❌ | ✅ Meyerding (1mm/2mm uncited) | *their best* — just unvalidated |
| Disc height + index (`disc_si_height.py`, `disc_height_index.py`) | ✅ mostly | ❌ none | ❌ lumbar only | ❌ | no tests; DHI<0.30 + formula uncited/non-standard |
| Disc bulge (`disc_ap_bulge.py`) | ⚠️ design flaw | ❌ none | ❌ lumbar only | ❌ | **under-reports bulges** + edge levels never flag |
| Disc wear grade (`signal/pfirrmann_grade.py`) | ✅ good normalization | ❌ none | ❌ cervical (lumbar validated) | ❌ cervical cut-points | cervical grades heuristic/hand-tuned |

## Per-measurement key findings
- **Foundation** (audited Ronnie's, richer): orientation→canonical RAS (axis0=L→R, axis1=P→A, axis2=I→S) is **correct**, spacing read *after* reorientation so `(LR,PA,IS)` order is right (the scary "swapped spacing corrupts every mm" bug is NOT present). NN resampling preserves integer labels. **BUT** anisotropic thick-slice cervical T2 is upsampled to 1mm → reports **through-plane precision the scan doesn't have**; the `low_through_plane_resolution` flag is advisory and **silently turns off when the source-spacing manifest is absent**. Orchestrator only catches `MeasurementError` → any other exception (ValueError/IndexError) **aborts the whole report** instead of degrading one component. No test asserts the axis-order contract (a future permutation regression would pass all tests).
- **Bone height (morphometry):** disc-anchored AP crop to drop the posterior arch (no canal cut) + per-vertebra **PCA tilt correction in mm** (same core idea as ours) + sub-voxel 4× refinement (Ronnie) + multi-slice avg. Fragile: on a tilted neck the spinous process can fall inside the disc AP window → arch not excluded → corrupts PCA/heights; missing disc → whole level dropped; **no fusion handling**; PCA SI/AP axis can flip when AP≈SI. Tests are clean rectangles only (no tilt/fusion/positive case). No real validation. AP 12–22mm + tilt 20° + 0.70 wedge ratio all uncited.
- **Bone slippage (spondylolisthesis):** cleanest module. Correct axis/sign/anisotropy/percentage-denominator/Meyerding boundaries; real (synthetic) tests incl. a positive slipped case; Meyerding 1932 cited + supine-MRI caveat (Lattig 2012/Segebarth 2015) cited. Tilt uncorrected (minor); could pair non-adjacent levels if a middle level is missing. 1mm/2mm thresholds uncited. No real-data validation.
- **Disc height + index:** axis/mm/anisotropy correct. **C7–T1 disc = label 71 — VERIFIED CORRECT** against real TSS output (TSS emits 67→71, skipping 68; agent's "maybe 68" suspicion was WRONG — checked on all 12 out_sg/ masks). DHI = disc-mid-height ÷ mean adjacent-VB-mid-height — **uncited and a non-standard definition**; `reduced_dhi` cutoff **0.30 uncited**. `h_center` uses raw axis-aligned voxels (tilt-inconsistent with the PCA heights). **No unit tests.** Validated only on SPIDER (lumbar), discrimination-AUC only, no mm-accuracy/ICC/Bland-Altman.
- **Disc bulge:** axis/sign/units correct, thoughtful VB-mismeasure guards. **DESIGN FLAW:** reference "back wall" = `min(upper_corner, lower_corner)` as a flat vertical line → in a lordotic (curved) neck this sits behind the true wall → **systematically under-reports real bulges** (excursions clamp to 0); and forces bulge=0 whenever a neighbor vertebra is missing → **edge levels (C2-C3, C7-T1) can never flag**. 90th-pct reducer can let segmentation noise fake a small bulge. Thresholds 2.0mm / ratio 1.10 uncited. **No unit tests.** Validated only on lumbar SPIDER (AUC).
- **Disc wear grade (Pfirrmann):** **sound instinct** — normalizes nucleus brightness against CSF + dark reference → affine-invariant ratio (NOT raw intensity), so robust to global scanner scale/offset. BUT cervical cut-points `(0.30,0.18,0.095,0.04)` are **hand-tuned to 10 Duke scans, self-described "heuristic, no cervical ground truth."** Lumbar cut-points ARE GT-calibrated on SPIDER (within-1 ~90%, Spearman ~0.65) — but cervical (the production target) is **unvalidated**. Scanner-robustness relies on an `auto_calibrate`/`calibration.json` that **doesn't exist in the worktree** → baked-in Duke cuts are live. References computed over whole 3D volume but disc sampled on one 2D slice (coil-shading mismatch risk). **No unit tests.**

## Concrete bugs/risks ranked
1. **Disc bulge under-reports** (flat back-wall on a curved neck + edge levels never flag). Real accuracy hole.
2. **Thick-slice false precision** (foundation): 1mm numbers on ~4mm scans; warning can vanish with missing metadata.
3. **Orchestrator non-graceful crash**: one component's unexpected exception kills the whole report.
4. ~~C7-T1 label 71 vs 68~~ — **CLEARED, verified correct on real TSS output.**

## Systemic gaps
- **No unit tests** for disc height, disc index, disc bulge, disc wear (only morphometry + spondy + the unregistered genant have tests).
- **Uncited clinical cutoffs** nearly everywhere (DHI<0.30, bulge 2mm, ratio 1.10, AP 12-22mm, tilt 20°, Pfirrmann cut-points, slip 1mm/2mm). Violates CLAUDE.md medical rule 1.
- **Zero cervical real-data validation.** Checks are synthetic boxes or **SPIDER = lumbar**. Cervical accuracy unknown.
- **Not built yet:** canal-width (G3 stenosis/SAC/Torg), spinal-cord measures, spine-curvature (G4 Cobb/alignment).

## Version / overlap state (the "D" reconciliation)
- `genant_6point.py`: identical on all 3 copies, settled, but **NOT registered in orchestrator** (dead-ish); `cervical_body_morphometry.py` is the live producer.
- `cervical_body_morphometry.py`: **merged baseline is STALE** (2026-04-28 base). Ronnie's branch adds sub-voxel refinement (+52L); Mohammad's adds AP-width spike-trim (+13L). **Orthogonal, mergeable** — the team needs to combine both. No single "most advanced" copy.
- Overlap with our 5.2: their `wedge_fracture = Ha<0.70·Hp` is the SAME metric as ours; their fixed 0.70 ≈ our data-driven 0.68. Our `cervical_deformity_flag` is a calibrated/cited/validated upgrade of the flag they already have. Recommendation: ONE shared morphometry producer (theirs, productionized) + G5 adds the validated compression screen on top; don't maintain two codebases. (Team decision — surfaced, not merged.)

## Validation strategy (the "other inputs" we need)
Reading code proves *plausibility*; proving *accuracy* needs reference data. Three tiers:
1. **Healthy-norm comparison (DOABLE NOW).** Run their measurements on the **12 healthy Spine-Generic necks we already have** (`~/dev/group5-proto/out_sg/` TSS masks) and confirm outputs land in published healthy ranges — the exact method that validated our 5.2. Needs the **published cervical norms** for each measurement → launch research (prompts drafted 2026-06-05).
2. **Known-size phantoms (cheap):** synthetic exact-mm objects → proves the formula only (they have a little of this).
3. **Expert-marked cervical scans (gold standard, hard):** no public cervical dataset exists (prior research; KIND-B = 0) → **AUBMC** path.
- We already hold (prior research): VB height/width + canal/SAC/Torg norms (Nell 2019/SHIP), VerSe masks. **Missing norms = disc height/DHI, disc bulge, Pfirrmann cervical distribution, spondylolisthesis thresholds.**

## Next steps
- Launch the 4 healthy-norm research prompts → then tier-1 validation of their geometric measurements on out_sg/.
- Surface the disc-bulge flat-wall flaw + the thick-slice false-precision + orchestrator-crash to the team.
- Reconcile the stale morphometry baseline (Ronnie+Mohammad merge) — team call.
- When norms land: do for their measurements what we did for 5.2 (healthy-lands-in-range test).
