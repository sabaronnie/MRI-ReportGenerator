# LAST_RUN.md — session handoff (group 2 disc measurements)

Reference for future chats. Covers everything done in the long working session
on `c:\Users\Moka\Desktop\group2`. Newest context first.

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
