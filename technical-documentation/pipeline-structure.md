# Pipeline Structure — Input → Report (every group)

> Integration map for the full pipeline, for the frontend chat and the report. States, per group:
> the measurement component(s), their output keys, validation status, whether they are wired into the
> orchestrator, and where patient demographics enter. Honest about the current gaps so the frontend
> links to what actually exists. Source of truth for status: `docs/validation/group-status-2026-06-08.md`.

## 1. End-to-end flow
```
INPUTS                         PROCESSING                              OUTPUT
------                         ----------                              ------
MRI (sagittal T2, DICOM/NIfTI) ─► Segmentation IEP (TSS + SCT + SPINEPS)
                                     │  vertebrae / discs / canal / cord / endplate masks
                                     ▼
                                  Measurements IEP — orchestrator.run_all(ctx)
                                     │  G1 morphometry · G2 disc · G3 canal/cord · G4 alignment · G5 screens
                                     ▼
patient: { age, sex } ───────────► Assessement (G6) — build_assessed_measurements()
   (used by future age/sex norms)   │  status per finding: outside_reference / review_only / within
                                     ▼
                                  Reporting IEP (/render) ─► clinical report ("flagged for physician review")
```

`height` is **not** consumed anywhere (no cervical norm is height-normalized) — collect it if you want it
on the record, but it does not feed G6. `age` + `sex` are the demographics the pipeline is built to use.

## 2. Inputs
| Input | Required? | Used by | Status |
|---|---|---|---|
| MRI sagittal T2 (DICOM/NIfTI) | **yes** | segmentation → all groups | live |
| `age` | optional (recommended) | G6 — age/sex percentile norms (Nell 2019 canal/SAC; PAM50 cord) | **contract field exists (`patient.age`), NOT yet wired to adjust thresholds** |
| `sex` | optional (recommended) | G6 — same age/sex norms | **contract field exists (`patient.sex`), NOT yet wired** |
| `height` | optional | — | **not in contract, not used by any threshold** |

## 3. Per-group map
| Group | Component(s) (orchestrator NAME) | Key outputs | Validated? | Wired into orchestrator? |
|---|---|---|---|---|
| **G1** vertebra | `cervical_body_morphometry`, `spondylolisthesis` | `H_anterior/H_middle/H_posterior`, `AP_width`, `tilt_deg`; slip | screen ✅; heights fixed (endplate-line), tilt recalibrated | ✅ |
| **G2** disc | `disc_si_height`, `disc_height_index`, `disc_ap_bulge`, `pfirrmann_grade` | `disc_SI_height`, `DHI`, `posterior_bulge_mm`, `disc_vb_ap_ratio`, `nucleus_csf_ratio` | partial — disc/VB AP ratio discriminates (AUC 0.62); signal/bulge negative | ✅ **wired** (J25; all four components in orchestrator `COMPONENTS`) |
| **G3** canal/cord | `functional_canal_ap`, `cord_ap`, `sac` | `canal_AP`, `cord_AP`, `SAC` (per level) | ✅ **strong** (p=0.0001) | ✅ |
| **G4** alignment | `c3c7_cobb_angle`, `lordosis_classification`, `segmental_angles`, `posterior_tangent_angle` | `Cobb_C3_C7` (prefers SPINEPS C1) | **method-valid, NOT a discriminator** (balanced 26 H vs 41 U: d=0.28, AUC 0.57, p=0.32; J26); production C1 path verified | ✅ |
| **G5** screens | `fracture_screen` (+ myelomalacia in group5 pipeline) | compression/wedge flags; lesion flags | screens validated (~91% specificity) | `fracture_screen` ✅; myelomalacia via group5 contract |
| **G6** assess | `services/assessement` (`build_assessed_measurements`, `classify`, `detect_syndromes`) | per-finding status + syndrome detection | built + unit-tested; **wired end-to-end** (J25) | ✅ called inside `run_all()`; `classify()` applied per catalogued key (see §4) |

## 4. G6 assessement — how it works + what's pending
- **`thresholds.py`** — a cited threshold catalog (`Band`/`ThresholdSpec`/`classify(key, value)`), provenance
  notes per band, demographic hooks (`ThresholdSpec.demographic`, `Band.demographic`).
- **`assessement.py`** — `build_assessed_measurements(report, ...)` wraps each numeric output with a
  status, `detect_syndromes()` flags stenosis/radiculopathy-style patterns, `assess_group5_contract()`
  folds in the G5 flags. The report carries `assessements.measurements[*].demographics_used` (today `{}`).
- **`classify()` IS wired (J25):** `build_assessed_measurements` calls `classify(key, value)` for every
  catalogued measurement (it was NOT a pure scaffold, as an earlier draft of this doc claimed); non-catalogued
  keys fall back to flag-only (`outside_reference` if a pathology flag is set, else `review_only`).
- **Demographics consumed (J25):** `demographics_used` is populated per measurement; **sex adjusts the
  dural-sac cut** (Nell 2019 M<10/F<9 mm). `age`/`height` flow into the context; `height` is record-only (no
  cervical norm normalises by height). Age/sex *percentile* lookups for canal/SAC/cord beyond the dural-sac
  sex cut remain future work (cord is delegated to SCT PAM50).
- **Threshold corrections (from `cervical_unhealthy_validation_plan`)** partly reflected (e.g. DHI<0.30
  debunked); still to verify/apply: dural-sac/SAC/Torg over-flag relaxation, drop the 1.35 mm bulge figure,
  van Santbrink offset direction, Miyazaki IV non-discriminating.
- Not a standalone Flask service — it runs inside the measurements orchestrator and the reporting IEP renders it.

## 5. Report contract (what the frontend consumes)
The reporting IEP emits (per `docs/contracts/data-contract-v0.1.md` on `feat/contract/data-contract-v0.1`):
```
{ "measurements": {<key>: {<level>: value}},
  "flags":        {<flag>: {<level>: bool}},
  "assessements": { "measurements": [ {measurement, level, value, status, demographics_used}, ... ] },
  "patient": { "sex": null, "age": null },     # <- the demographics input lands here
  "triage_badge": "none|review|urgent",        # derive from worst flag (rule TBD)
  "job": { stage, progress } }
```
Quality flags (e.g. `tilt_outlier`) must NOT be shown as patient abnormalities (see
`assessement.QUALITY_FLAG_MARKERS`).

## 6. Integration status (updated 2026-06-08 — most gaps now closed in code)
1. ✅ **G2 disc wired** into the orchestrator `COMPONENTS` — disc numbers + assessements now in the report.
2. ✅ **`classify()` already in use** — every catalogued measurement gets its cited band status (it was not a
   pure scaffold; non-catalogued keys fall back to flag-only).
3. ✅ **Demographics wired** — `load_context`/`run_all` carry `age/sex/height`; the report has a `patient`
   block; `demographics_used` is populated per measurement; **sex adjusts the dural-sac cut** (Nell M10/F9).
   `height` is captured **record-only** (no cervical norm normalises by height). Age/sex *percentile* lookups
   for canal/SAC/cord beyond the dural-sac sex cut are still future work (cord is delegated to SCT PAM50).
4. ✅ **DHI flag corrected** — debunked absolute DHI<0.30 replaced with the cited relative >30% cross-level
   drop (Suzuki 2018).
5. 🟡 **Reporting IEP** must render `assessements` + `patient` + `triage_badge` (confirm on infra side).
6. 🟡 **EEP → measurements**: the EEP `POST /cases` must forward `{age, sex}` into `load_context` (the
   measurement service already accepts them) — this is the frontend/infra integration point.
7. 🟡 **G3** needs the SCT canal/cord segmentations in the context to populate canal/SAC/cord (works when
   provided; errors gracefully otherwise).
8. ⚪ **Assessement as a standalone Flask IEP** — deliberately NOT done: it runs inside the measurements
   IEP (the 2 deployed IEPs are measurements + reporting). Splitting it out is optional, not required for GT3.

## 7. What the frontend chat needs from us (deliver right after G4 validation closes)
A short integration handoff: the exact request shape (MRI + `{age, sex}`), the response shape (§5), the
list of measurement keys + which are validated vs review-only, and the quality-flag exclusion list — so the
frontend links inputs→outputs against what exists today, with the gaps in §6 flagged as in-progress.
