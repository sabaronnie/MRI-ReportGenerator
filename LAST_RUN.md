# LAST_RUN.md — session handoff (group 2 disc measurements)

Reference for future chats. Newest context first.

---

## Session 2026-05-27 → 2026-05-28 — calibration loop, automation, UI, SPIDER validation

### TL;DR
- Automated end-to-end pipeline: first 10 Duke scans → TSS → measurements → `group2_summary.csv`.
- Calibrated all 4 disc-measurement files in an iterative loop driven by a structured scorecard; baseline **7/16 PASS → final 18/18** on 51 scans (210+ reliable cervical discs).
- Added plausibility guards (VB AP, disc AP width), an auto-calibration system that no-ops when clean, a phantom accuracy test (algorithm exact to ≤1 mm), a Flask UI, a per-scan-folder segmentation batch (target 100), and SPIDER-based discrimination validation on 1,452 lumbar discs (DHI AUC **0.735** for narrowing, posterior_bulge AUC **0.713** for herniation, Pfirrmann Spearman **0.63**).
- **Nothing committed yet** — git status showed all edits unstaged on `mokaBranch` and the user pivoted before commit. To commit later, stage the files listed below by name (NEVER `git add .`).

### Files created (this session)
- [colab/run_group2_pipeline.py](colab/run_group2_pipeline.py) — orchestrates Duke→TSS→measurements→CSV; per-scan-folder cache + `--no-segment`.
- [colab/segment_batch.py](colab/segment_batch.py) — TSS-only batch, one folder per scan at `tss_runs/segmentations/<scan>/step2_output/`; resumable; reuses legacy caches.
- [colab/evaluate_calibration.py](colab/evaluate_calibration.py) — scorecard (18 checks); `run_checks` returns tagged tuples so other tools can act on specific failures.
- [colab/auto_calibrate.py](colab/auto_calibrate.py) — measure → score → no-op if clean, else refit Pfirrmann cuts; geometry failures are review-only.
- [colab/accuracy_phantom.py](colab/accuracy_phantom.py) — builds synthetic discs of known geometry, asserts the measurement formulas are exact.
- [colab/ui_app.py](colab/ui_app.py) — single-file Flask web UI (path input + format selector + auto-refreshing results table); reuses the calibrated pipeline.
- [colab/validate_spider_discrimination.py](colab/validate_spider_discrimination.py) — runs helpers + Pfirrmann on SPIDER lumbar masks/images, computes AUC vs radiologist labels.
- `group2_calibration_report.md` (auto-written), `services/measurements/calibration.json` (written only on refit; both gitignored), `spider_data/discrimination_results.csv` (gitignored).

### Files modified (this session)
- [services/measurements/geometric/disc_si_height.py](services/measurements/geometric/disc_si_height.py) — anterior/posterior heights via robust AP-column SI extent (`_band_si_extent`, `AP_COLUMN_FRACTION=0.22`) replacing the corner-drift-prone `_dist_mm` corners; AP width trimmed (`AP_WIDTH_TRIM_PCT=2.5`); new plausibility flag `ap_width_implausible` (AP > 25 mm).
- [services/measurements/geometric/disc_ap_bulge.py](services/measurements/geometric/disc_ap_bulge.py) — rewrote `_posterior_bulge` to reference the disc against the **more-posterior, reliable** adjacent VB wall (`min(upper,lower)` of band-median posterior anchors) with p90 of per-row excursion; added `vb_ap_implausible` guard (`VB_AP_FLOOR_MM=10.5`, `RATIO_IMPLAUSIBLE=1.30`) that flags an under-measured VB and suppresses false bulge flags.
- [services/measurements/geometric/cervical_body_morphometry.py](services/measurements/geometric/cervical_body_morphometry.py) — same `AP_WIDTH_TRIM_PCT=2.5` applied to body-slice AP so disc/VB ratio is method-consistent (ratio went 0.876 → 1.00).
- [services/measurements/signal/pfirrmann_grade.py](services/measurements/signal/pfirrmann_grade.py) — region-aware `_grade_disc` + `NORM_CUTS` (cervical recentred to (0.30,0.18,0.095,0.04) for the Duke T2 scale); `_region_for(disc_name)`; loads `services/measurements/calibration.json` overrides into `ACTIVE_CUTS` at import (lets auto-calibration drop in new cuts without code edits).
- [services/measurements/tests/test_cervical_body_morphometry.py](services/measurements/tests/test_cervical_body_morphometry.py) — widened AP tolerance to `abs=1.5` for the percentile-trimmed AP.
- (17 unit tests still pass after all changes.)

### Turn-by-turn log

1. **Prompt:** "automate the pipeline of fetching mri scans from `DukeCSpineSeg_annotation` through totalspineseg and measurements to output a summary csv called `group2_summary.csv`, first 10 scans."
   **Answer:** Wrote `run_group2_pipeline.py`; for each scan: find cached seg or run TSS, then `load_context` → 4 disc components → per-disc CSV. Ran it: 9 scans were cache-hits, 000001 segmented fresh (~10 min on GPU). Produced **87 disc rows, 10 patients**.

2. **Prompt:** "in group2_summary.csv which measurements don't make sense?"
   **Answer:** Ranked the issues against the project's own reference ranges:
   - **Pfirrmann** worst — 55% grade IV, 83% grade III–IV (`nucleus_norm` median 0.138 vs III-threshold 0.15); `signal/pfirrmann_grade.py`.
   - **Posterior bulge** over-reads — median 1.89 mm with 48% ≥ 2 mm and max 11.7 mm; `_posterior_bulge` uses `max` over voxels; `disc_ap_bulge.py`.
   - **Anterior/posterior heights** — 56% have posterior > anterior (wedge inverted); max 14.4 mm; `disc_si_height.py`.
   - **AP widths** ~10–30% high (driven by `_measure_body_slice` extreme-voxel method); ratio still ~0.99 so lower priority.

3. **Prompt:** "calibrate/change/improve all files that lead to measurements that don't make sense. then re-run and re-evaluate. use statistical comparisons to the normal thresholds. redo this loop until you find accurate measurements."
   **Answer:** Built `evaluate_calibration.py` (16 PASS/FAIL checks) and iterated:
   - **Baseline:** 7/16 pass.
   - **Iter 1** (cervical Pfirrmann cuts recentred; bulge → p90; column-band ant/post heights; tighter AP trim): 11/16.
   - **Iter 2** (wedge band → 0.22; AP trim p5/p95; disc-self-contained bulge): 13/16 — but the self-contained bulge measured the disc's natural lens curvature, not bulging — wrong.
   - **Iter 3** (rewrote bulge to reference the disc against the more-posterior of the two adjacent VB walls): **16/16**.
   - **Iter 4** (applied the same `p2.5/p97.5` AP trim to `_measure_body_slice` so disc and VB use the SAME estimator; widened the phantom test tolerance; raised AP ceiling 24→25 with anatomical justification for junctional discs): **16/16**, disc/VB ratio improved 0.876 → 1.002.
   - All 17 measurement unit tests pass throughout.

4. **Prompt:** "scale to 100 — first I want segmentation outputs only, each in a folder, skip ones already done, edit the script."
   **Answer:** Wrote `segment_batch.py`: per-scan folder layout at `tss_runs/segmentations/<scan>/step2_output/`; reuses 13 legacy-cached segs (copies them in); runs TSS only for the missing ~87; resumable; `--keep-only step2_output`. Dry-run verified the plan before any TSS calls.

5. **Prompt:** "it runs one scan at a time — doesn't run 87 automatically?"
   **Answer:** Clarified: **one command, fully unattended**, processes all 87 back-to-back sequentially in a loop — "one at a time" means not in parallel (single GPU per call), not waiting for user input.

6. **Prompt:** "see how many segs are done; which file do I run for measurements?"
   **Answer:** 29 segs done; modified `run_group2_pipeline.py` to (a) discover segs in the new per-scan layout, (b) add `--no-segment` so it measures only what's already segmented (won't fire up TSS and collide with the running batch). Verified: 254 disc rows from 28 patients (1 segmentation produced no valid discs).

7. **Prompt:** "re-run measurements + re-calibrate against normal thresholds. what did you change?"
   **Answer:** Calibration generalised (still 16/16 on 29 scans) but the larger sample exposed a tail the medians missed: **disc/VB ratio max 1.84**. Diagnosed on 000014 C5-C6: the *vertebral body* is under-measured (`_measure_body_slice` reads 10.4 mm vs the true 16.5 mm), inflating the ratio — not a real bulge. Added `vb_ap_implausible` guard (`disc_ap_bulge.py`), propagated the AP-component's reliability into the CSV `reliable`/`flags` columns (`run_group2_pipeline.py`), added a ratio-tail check to the scorecard → **17/17**.

8. **Prompt:** "make automatic calibration that fixes this without me having to ask each time; if all measurements are normal, no calibration is needed."
   **Answer:** Drew the honest line — **only Pfirrmann should auto-recalibrate** (it depends on the dataset's T2 intensity scale, legitimately re-anchorable to the cohort's own healthy discs); **geometry must never be auto-shifted toward "normal"** because a degenerative cohort is supposed to read abnormal in mm, and shifting it hides pathology (CLAUDE.md medical rule). Built `auto_calibrate.py`: measure → score → if all pass, **no-op** ("no calibration needed"); if Pfirrmann checks fail, refit cervical cut-points from the data's `nucleus_norm` percentiles (TARGET_CUM=(.10,.35,.70,.95)) into `services/measurements/calibration.json`, re-measure, re-score; geometry/anchor failures are **review-only**, never silently shifted. `pfirrmann_grade.py` reads `calibration.json` at import (`ACTIVE_CUTS`). Also added `ap_width_implausible` guard and a reliable-disc-fraction monitor (18 checks). Demonstrated the refit rule reproduces the hand-tuned ladder.

9. **Prompt:** "how much sense do they make, how can I test if exactly correct?"
   **Answer:** Distinction matters — the scorecard proves **plausibility**, not **accuracy**. Built `accuracy_phantom.py`: synthetic segs of *known* disc/VB geometry → measurements come back exact. Initial test had a bug in *my* truth values for the bulge case (didn't account for the bulge widening the disc); fixed the truth formulas. All 5 phantoms pass — **H_center / DHI / bulge exact, AP width ~0.8 mm low (known, sub-voxel trim bias)**. Worst error 0.95 mm. Stated the validation ladder honestly: phantom (algorithm exact) → SPIDER (Pfirrmann lumbar GT, prior session) → radiologist manual mm (the unfilled gap for cervical accuracy).

10. **Prompt:** "is there a sagittal cervical MRI dataset with exact disc SI height + AP width measured?"
    **Answer (web-sourced):** **No** public cervical MRI dataset ships caliper mm GT for both. Closest options: (a) lumbar Mendeley dataset 10.17632/x6ggzp2ycn.1 (515 lumbar T2 with mm disc heights + Pfirrmann — the only public source of real mm GT, but lumbar); (b) Duke's own 481 expert masks for the segmentation-error experiment; (c) published cervical normative studies for distribution-level checks (1211-volunteer MRI, CT 1000-patient — your medians already land near these). For per-case cervical mm GT, a radiologist subset is unavoidable.

11. **Prompt:** "commit changes to mokaBranch only."
    **Answer:** Confirmed branch (`mokaBranch`) and ran `git status` — five modified files in `services/`, eight untracked files in repo. Was about to stage by name when the next message arrived; **no commit was actually executed** in this session.

12. **Prompt:** "what is there to do next."
    **Answer:** Showed prioritized menu (validate accuracy / wire 4 disc components into orchestrator / finish 100 + scale / improve measurement quality / course-deploy team-scope) and asked which to tackle. User redirected.

13. **Prompt:** "create a simple UI for me to input an mri file…"
    **Answer:** Wrote `ui_app.py` (Flask, single file, inline HTML). Path-based input (NIfTI file or DICOM folder) + format selector; background thread + auto-refresh on the status page; reuses `find_cached_seg` (instant on already-done Duke scans) and `measure_case`. Smoke test failed: `input_handler.prepare_nifti`'s sagittal check rejected Duke files (`('P','S','R')` — sagittal but L–R is axis 2, the check assumed axis 0). **Found a real bug in shared `input_handler.py`** — the working pipeline never used it, so it never surfaced. Worked around it in the UI with an orientation-order-independent sagittal check (L–R axis must be the coarsest-spacing/slice axis). Re-tested: cached Duke scan → instant rendered table with all calibrated metrics, Pfirrmann pills, flagged rows.

14. **Prompt:** "what is bulge, why is it 0 for all except C2-C3?"
    **Answer:** Defined posterior_bulge_mm as disc-posterior protrusion past the adjacent VB wall. Explained 0 is expected (most discs aren't bulging; the new measurement is deliberately conservative). Corrected the premise — across the data only 11/472 discs are nonzero, and they cluster at **C3–C4 / C4–C5**, not C2–C3 (C2–C3 is always flagged unreliable anyway due to the dens). Noted the remaining 9.88 mm outlier at C4-C5 and offered to add a bulge plausibility guard.

15. **Prompt:** "is there a dataset to identify short/large measurements? + radiopaedia link."
    **Answer:** On radiopaedia — useful as a qualitative/demo source (find a case, drop into the UI) but not a structured benchmark (narrative labels, web images not 3D volumes, licensing). Built `validate_spider_discrimination.py`: SPIDER expert lumbar masks + raw images + per-disc radiologist labels. Bypassed cervical-only `DISC_LABELS` by calling the geometric helpers with SPIDER's integer labels directly. **Smoke test (10 patients, 67 discs):** narrowing-by-DHI AUC 0.81, herniation-by-bulge 0.81, Pfirrmann within-1 72%. **Full run (210 patients, 1,452 discs):** narrowing -DHI **AUC 0.735**, -H_center 0.671, -H_middle 0.632; bulging ratio 0.604 / bulge 0.622; herniation ratio 0.560 / bulge **0.713**; Pfirrmann exact 27%, within-1 67%, **Spearman 0.63**. The calibration changes preserved (and modestly improved) discrimination vs the prior session's 0.66/0.74.

16. **Prompt:** "you said cervical labels are required, labels of exactly what."
    **Answer:** Two flavours — (i) per-disc categorical (narrowing y/n, bulging y/n, herniation y/n, Pfirrmann 1–5) for SPIDER-style discrimination AUC (~20 cases × 6 discs is enough); (ii) per-disc mm caliper measurements (height + AP width) for absolute accuracy (ICC, Bland–Altman). Cheapest path: parse existing radiology reports into structured per-disc labels rather than de-novo reading.

17. **Prompt:** "record all edits done in this chat including the prompts and your answers to last_run.md." → **this entry.**

### Key numeric results

| Stage | n discs (reliable cerv.) | Scorecard | Notable medians |
|---|---|---|---|
| Baseline (10 scans, pre-calibration) | 50 | 7/16 PASS | DHI 0.37, H_post>H_ant 56%, bulge med 1.89, Pfirrmann G4 = 55% |
| Final (10 scans, all calibrations) | 50 | 16/16 PASS | DHI 0.37, wedge inv 38%, bulge med 0, ratio 1.00, Pfirrmann G4 = 22% |
| 29 scans | 142 → 134 (vb_ap guard fires) | 17/17 PASS | medians stable; max ratio capped at 1.22 |
| 50 scans + auto_calibrate | 232 → 236 (ap_width guard) | 18/18 PASS | "NO CALIBRATION NEEDED" no-op |
| Phantom accuracy | 5 phantoms | all exact | H_center/DHI/bulge error 0.00; AP off 0.75–0.95 mm (trim) |
| SPIDER discrimination | 1,452 discs / 210 patients | — | -DHI→narrowing AUC 0.735; bulge→herniation 0.713; Pfirrmann Spearman 0.63 |

### Real bug surfaced (worked around in the UI, not yet fixed at source)
`services/segmentation/input_handler.py::_validate_sagittal` rejects valid sagittal NIfTIs whose L–R axis isn't axis 0 (Duke files are `('P','S','R')` — sagittal, L–R on axis 2). The working pipeline never called this function, so it never surfaced before. The UI does its own orientation-order-independent check. The shared file remains buggy — fix worth a PR (segmentation owner).

### Open / not done in this session
- Did not commit (asked once, user pivoted before staging).
- Did not register the four disc components in `services/measurements/orchestrator.COMPONENTS` — the Flask `/measure` endpoint still doesn't run the disc measurements (they run only via `run_group2_pipeline.py` and the UI).
- Did not fix `input_handler._validate_sagittal` at source.
- Did not run the full 100-scan corpus through auto_calibrate after `segment_batch.py` finishes (was at ~51 last checked).
- Did not build a bulge plausibility guard for the 9.88 mm C4–C5 outlier (offered, no answer).
- No cervical radiologist mm GT acquired (the unfilled accuracy gap).

---

## TL;DR
- Built + tested the 4 group-2 disc services, validated them on **real public
  data** (Duke cervical via TotalSpineSeg, and **SPIDER** lumbar — non-Duke,
  with radiologist ground truth).
- **Pfirrmann (lumbar) is now calibrated against ground truth**: 48.9% exact,
  89.9% within-1, Spearman 0.65 (5-fold CV). Cervical Pfirrmann stays heuristic
  (no cervical ground truth exists).
- Found + fixed two real measurement biases (disc height too small; disc/VB AP
  ratio too big). Added a **standardization layer** but proved it's a no-op on
  good inputs (its value is QC/edge-cases, not fixing measurements).
- Committed the standardization layer to **`mokaBranch`** (commit `402b36e`, not
  pushed).

## Environment & repo state
- **Interpreter:** `py -3.12` (has numpy/nibabel/scipy/SimpleITK/totalspineseg/
  torch+CUDA). Default msys2 `python` does NOT.
- **TSS:** installed; run with `py -3.12 -m totalspineseg.inference <in> <out> --device cuda`.
- **`group2` is a git clone** of `github.com/sabaronnie/MRI-ReportGenerator`,
  currently on branch **`mokaBranch`**. A second clone is at
  `Desktop/GitHub/MRI-ReportGenerator` (branch `research/mohammad/groups-2-4-impl`).
- group2 now mirrors the repo: measurement components use the repo's
  `compute(ctx, prior)` pattern with `MeasurementContext`/`load_context`/
  `ComponentResult` in `services/measurements/context.py`.

## Layout (group 2 = the measurements service)
- `services/measurements/geometric/`: `disc_si_height.py` (2.1), `disc_ap_bulge.py`
  (2.2), `disc_height_index.py` (2.3) + repo's `cervical_body_morphometry.py`,
  `genant_6point.py`, `spondylolisthesis.py`.
- `services/measurements/signal/pfirrmann_grade.py` (2.4).
- `services/segmentation/`: `input_handler.py`, **`standardize.py` (new)**,
  `segmenter.py` (TSS wrapper), `cli.py`.
- `colab/`: validation/calibration harnesses (`validate_cohort.py`,
  `validate_spider.py`, `validate_spider_pfirrmann.py`, `calibrate_pfirrmann.py`,
  `analyze_discrimination.py`, `measure_compare.py`).
- Data (git-ignored): `tss_runs/` (batch_in raw Duke, batch_out baseline segs,
  std_in/std_out standardized), `spider_data/`, `totalspineseg_output/`.

## What was built / changed
- **2.1**: added `h_center_mm` (central-column height) — Chae 4-corner `h_middle`
  underestimates biconvex discs.
- **2.2**: added `vb_ap_width_mm` + `disc_vb_ap_ratio`; **fixed VB-AP over-clipping**
  (body isolation now extends to the disc posterior margin → ratio ~1.0, not 1.25).
- **2.4**: scale-robust `nucleus_norm = (nucleus-dark)/(csf-dark)`; calibrated
  ordinal cut-points (`NORM_CUTS`); grade V gated on height collapse; `region`
  + `experimental` columns.
- **All 4**: `flags` + `reliable` columns (C2-C3 dens, FOV-edge, truncation).
- **Standardization layer** `services/segmentation/standardize.py` (Phase 1.5,
  wired into segmentation `cli.py`): RAS reorient + intensity normalize + spacing
  flag, **no-downsample default** (`allow_downsample=False`).

## Validation results (real data)
**Geometry vs literature** — medians in range on both cohorts; disc/VB AP ratio
median ≈ 1.00–1.01 and scale-invariant (corr with voxel size +0.13).

**Resolution / "zoom" hypothesis** — mm geometry is affine-correct, so zoom
doesn't bias it; thin-height drift (corr −0.23 at native res) vanishes (+0.03)
after 1 mm resampling. Much of the apparent drift was **corrupt spacing headers**.

**Ground-truth cross-checks (SPIDER radiologist labels):** narrowed discs → lower
DHI; bulging discs → higher disc/VB AP ratio (correct direction).

**Pfirrmann vs ground truth (SPIDER, 1452 discs, 5-fold CV):** 48.9% exact,
89.9% within-1, Spearman 0.65 (within inter-radiologist range). Mean predicted
grade rises monotonically with true grade (1.80→2.17→2.93→3.70→3.93).

**Normal-vs-abnormal disc height (vs radiologist "narrowing", 1102 discs):**
DHI AUC ≈ **0.66 disc-level, 0.74 patient-level** → useful as a screen, NOT a
standalone diagnostic.

## Known measurement biases + expected ranges
- **Disc height (`h_middle`, Chae) reads TOO SMALL** — proven: lumbar 5.0 mm vs
  central-column 8.3 mm on the same discs. **Use `h_center_mm`.**
- **DHI reads TOO SMALL** (consequence of `h_middle`): lumbar ~0.19, cervical ~0.27.
- **disc/VB AP ratio WAS too big (~1.25)** → fixed to ~1.0 (VB body had been
  under-measured by canal-edge over-clipping).
- **AP widths are fine.**

| measure | cervical ref | lumbar ref |
|---|---|---|
| disc central height | ~4–6 mm | ~8–12 mm |
| DHI (disc ÷ VB) | ~0.30–0.45 | ~0.30–0.40 |
| disc AP width | ~14–18 mm | ~32–38 mm |
| disc/VB AP ratio | ~0.85–1.05 | ~0.9–1.1 |

## Standardization layer — honest verdict
For correctly-tagged inputs, standardized output == raw baseline **exactly**
(proven on 2 scans via `colab/measure_compare.py`). So it does NOT fix
measurements. Forcing 1 mm *downsampling* of a high-res 0.43 mm scan actively
degraded it (ratios 1.4–1.6, C7-T1 broke) — hence the no-downsample default.
Real value: flag bad spacing, upsample genuinely low-res scans, consistent
intensity/orientation. Recommendation: keep only the spacing sanity-check (could
move into `input_handler` QC); orientation step is redundant (`context.py`
already reorients).

## Open items / recommendations (for accuracy)
1. **Switch DHI numerator to `h_center`** so both height and DHI land in range (quick).
2. **Endplate-perpendicular height axis (PCA)** — current heights are image-axis
   aligned; tilted discs over-read. Reuse `cervical_body_morphometry`'s PCA.
3. **Multi-slice aggregation** (median over central ~3–5 sagittal slices + report
   spread) — single-slice noise is the main discrimination ceiling.
4. **Per-level, age/sex-adjusted reference ranges (z-scores)** — biggest lever to
   push normal/abnormal AUC toward ≥0.85; needs a normative cohort.
5. **Register disc components in `orchestrator.COMPONENTS`** — currently only
   `cervical_body_morphometry` + `spondylolisthesis` are registered, so `run_all`
   / `/measure` does NOT run the disc measurements. Drive order via `DEPENDS_ON`
   (`disc_si_height` → `disc_ap_bulge`/`disc_height_index` → `pfirrmann_grade`).
6. **mm ground truth** (AUBMC radiologist subset) — the only way to quantify
   absolute geometric accuracy (ICC/Bland-Altman); cervical Pfirrmann needs
   labeled cervical data to move from heuristic to calibrated.

## Git
- On `mokaBranch`. Commit `402b36e` = standardization layer (`standardize.py`,
  `test_standardize.py`, `cli.py` wiring, `colab/measure_compare.py`). **Not pushed.**
- `colab/_stage_standardized.py` left untracked (throwaway helper).
- `main` untouched.

## Gotchas
- TSS `step2_output` follows input spacing unless `--iso`; reads voxel size from
  the affine (never assume 1 mm).
- C2-C3 unreliable (dens); FOV-edge discs under-segment → flagged.
- Pfirrmann needs the T2 image (`ctx.raw_data` via `load_context(seg, raw)`);
  raw must match seg space/shape.
- SPIDER masks are `.mha` (SimpleITK); labels: vertebrae 1..N, canal 100,
  discs 201+. Adapter remaps canal→2, vertebrae +100, discs unchanged.
</content>
