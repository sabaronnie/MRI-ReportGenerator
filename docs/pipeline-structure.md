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
patient: { age, sex } ───────────► Interpretation (G6) — build_interpreted_measurements()
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
| **G2** disc | `disc_si_height`, `disc_height_index`, `disc_ap_bulge`, `pfirrmann_grade` | `disc_SI_height`, `DHI`, `posterior_bulge_mm`, `disc_vb_ap_ratio`, `nucleus_csf_ratio` | partial — disc/VB AP ratio discriminates (AUC 0.62); signal/bulge negative | ❌ **NOT wired** (contract confirms) |
| **G3** canal/cord | `functional_canal_ap`, `cord_ap`, `sac` | `canal_AP`, `cord_AP`, `SAC` (per level) | ✅ **strong** (p=0.0001) | ✅ |
| **G4** alignment | `c3c7_cobb_angle`, `lordosis_classification`, `segmental_angles`, `posterior_tangent_angle` | `Cobb_C3_C7` (prefers SPINEPS C1) | directional/borderline (p=0.070); production C1 path verified | ✅ |
| **G5** screens | `fracture_screen` (+ myelomalacia in group5 pipeline) | compression/wedge flags; lesion flags | screens validated (~91% specificity) | `fracture_screen` ✅; myelomalacia via group5 contract |
| **G6** interpret | `services/interpretation` (`build_interpreted_measurements`, `classify`, `detect_syndromes`) | per-finding status + syndrome detection | built + unit-tested | ✅ called inside `run_all()` (scaffold — see §4) |

## 4. G6 interpretation — how it works + what's pending
- **`thresholds.py`** — a cited threshold catalog (`Band`/`ThresholdSpec`/`classify(key, value)`), provenance
  notes per band, demographic hooks (`ThresholdSpec.demographic`, `Band.demographic`).
- **`interpretation.py`** — `build_interpreted_measurements(report, ...)` wraps each numeric output with a
  status, `detect_syndromes()` flags stenosis/radiculopathy-style patterns, `interpret_group5_contract()`
  folds in the G5 flags. The report carries `interpretations.measurements[*].demographics_used` (today `{}`).
- **Current limitation (the scaffold gap):** `build_interpreted_measurements` marks a value
  `outside_reference` only when a known pathology flag is set, else `review_only` — it does **not yet** run
  the full `classify()` catalog per measurement. So the rich cited catalog exists but the orchestrator's
  interpretation pass is a simpler scaffold. Wiring `classify()` in is a known task.
- **Demographics not yet consumed:** `demographics_used` stays `{}`; age/sex are in the contract but no band
  is age/sex-adjusted yet (the catalog cites Nell 2019 / PAM50 as the proper norms — implementing the
  percentile lookup is future work).
- **Threshold corrections (from `cervical_unhealthy_validation_plan`)** partly reflected (e.g. DHI<0.30
  debunked); still to verify/apply: dural-sac/SAC/Torg over-flag relaxation, drop the 1.35 mm bulge figure,
  van Santbrink offset direction, Miyazaki IV non-discriminating.
- Not a standalone Flask service — it runs inside the measurements orchestrator and the reporting IEP renders it.

## 5. Report contract (what the frontend consumes)
The reporting IEP emits (per `docs/contracts/data-contract-v0.1.md` on `feat/contract/data-contract-v0.1`):
```
{ "measurements": {<key>: {<level>: value}},
  "flags":        {<flag>: {<level>: bool}},
  "interpretations": { "measurements": [ {measurement, level, value, status, demographics_used}, ... ] },
  "patient": { "sex": null, "age": null },     # <- the demographics input lands here
  "triage_badge": "none|review|urgent",        # derive from worst flag (rule TBD)
  "job": { stage, progress } }
```
Quality flags (e.g. `tilt_outlier`) must NOT be shown as patient abnormalities (see
`interpretation.QUALITY_FLAG_MARKERS`).

## 6. Integration gaps to close for a live end-to-end pipeline
1. **Wire G2 disc components** into the orchestrator `COMPONENTS` (currently excluded).
2. **Promote G6 from scaffold to `classify()`** so each measurement gets its cited band status.
3. **Wire `patient.age`/`patient.sex`** through `load_context`/`run_all` into `build_interpreted_measurements`
   and implement the age/sex percentile lookup for canal/SAC (Nell 2019) and cord (PAM50).
4. **Confirm the reporting IEP** renders `interpretations` + `patient` + `triage_badge`.
5. **Frontend:** collect `age` + `sex` (skip `height` or mark it record-only); POST them with the MRI; render
   the report blocks above.

## 7. What the frontend chat needs from us (deliver right after G4 validation closes)
A short integration handoff: the exact request shape (MRI + `{age, sex}`), the response shape (§5), the
list of measurement keys + which are validated vs review-only, and the quality-flag exclusion list — so the
frontend links inputs→outputs against what exists today, with the gaps in §6 flagged as in-progress.
