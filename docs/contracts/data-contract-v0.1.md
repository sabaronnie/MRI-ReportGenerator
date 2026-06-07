# Data Contract v0.1 — MRI-ReportGenerator (science ⇄ frontend/infra coupling)

> The single coupling point between the **science track** (segmentation + measurements +
> interpretation; owns service internals) and the **frontend/infra track** (Next.js, EEP
> FastAPI front-door, Docker/k8s, AWS, monitoring). Build the UI/EEP against the SHAPES
> here with a mock; the real science code drops in behind the same shapes — no rewrite.
>
> **Owner:** science track (Andrew). **Consumers:** frontend + EEP + infra.
> Companion docs: [`segmentation-viewer-v0.1.md`](segmentation-viewer-v0.1.md) (NiiVue, #2),
> sample fixtures in [`samples/`](samples/).

## Status legend
- 🟢 **FROZEN** — stable; build against it. Changing it is a versioned breaking change.
- 🟡 **LIKELY-TO-CHANGE** — shape is real but names/values may shift before v1.0; mock it, expect churn.
- ⚪ **PROPOSED** — not yet emitted by code (EEP/reporting are scaffolds); this doc *defines* it. Highest churn.

`schema_version` accompanies every top-level object. v0.1 = first freeze of the measurement/interpretation core; the case/job/upload/report envelopes are PROPOSED (the EEP + reporting services are still scaffolds).

---

## 0. The big picture
The measurement service (`services/measurements`) already emits a real, stable report object
(verified by running it on a healthy control — see [`samples/case-healthy.json`](samples/case-healthy.json)).
The EEP wraps that in a **case envelope** (id, status, job, report) — that wrapper is PROPOSED here.

```
case envelope (PROPOSED, EEP)
├── case            ⚪  identity + de-id metadata + status
├── job             ⚪  processing stage + progress
├── measurements    🟢  {measurement_key: {level_or_pair: number}}     ← REAL, from orchestrator
├── flags           🟢  {flag_key: {level_or_pair: bool}}              ← REAL, from orchestrator
├── components       🟢  {component_name: {status, duration_s, error?, metadata?}}  ← REAL
├── interpretations 🟢  {measurements: [InterpretedMeasurement, ...]}  ← REAL, from interpretation svc
└── report          🟡  impression[] + findings + disclaimers          ← reporting svc scaffold
```

---

## 1. 🟢 `measurements` — numeric outputs (FROZEN core)
Shape: `{ measurement_key: { level_or_pair: number } }`. Values are floats (mm, deg, ratio, grade).
Levels we measure: **C3, C4, C5, C6, C7** (C1/C2 excluded by design). Disc/segmental keys use **pairs**.

| measurement_key | unit | keyed by | group | catalog status |
|---|---|---|---|---|
| `AP_width` | mm | level (C3–C7) | G1 | quality sanity 12–22 mm |
| `H_anterior` | mm | level | G1 | feeds Ha/Hp |
| `H_middle` | mm | level | G1 | feeds biconcave |
| `H_posterior` | mm | level | G1 | feeds Ha/Hp |
| `tilt_deg` | deg | level | G1 | quality caution |
| `vb_hahp_ratio` | ratio | level | G5/G1 | **flag < 0.68**, borderline < 0.81 |
| `spondy_slip_mm` | mm | pair (e.g. `C3-C4`) | G1 | flag ≥ 2.0 (experimental) |
| `spondy_pct_of_lower_AP` | % | pair | G1 | Meyerding-style |
| `Cobb_C3_C7` | deg | `C3-C7` (single) | G4 | descriptive class, lordosis-positive |
| `segmental_angle` | deg | pair (`C3-C4`…`C6-C7`) | G4 | no norm yet (review-only) |
| `posterior_tangent_C3_C7` | deg | `C3-C7` | G4 | no norm yet (review-only) |
| `dural_sac_AP_min` | mm | level | G3 | normal >13 / borderline / stenosis <10 |
| `cord_AP` | mm | level | G3 | normative via SCT, no fixed cut |
| `SAC` | mm | level | G3 | high_risk < 3 mm |
| `disc_SI_height` | mm | pair (`C2-C3`…) | G2 | — |
| `disc_height_index` / `DHI` | ratio | pair | G2 | review-only (no validated cut) |
| `posterior_bulge_mm` | mm | pair | G2 | bulge >1 / cord-risk >1.35 (1.35 unverified) |
| `pfirrmann_grade` | grade (1–5) | pair | G2 | Miyazaki, research-grade |

> **Currently WIRED in the orchestrator** (`COMPONENTS` registry): `cervical_body_morphometry`,
> `spondylolisthesis`, `c3c7_cobb_angle`, `lordosis_classification`, `segmental_angles`,
> `posterior_tangent_angle`, `group5_fracture_screen`, `functional_canal_ap`, `cord_ap`, `sac`.
> **NOT yet wired:** the G2 disc components (`disc_si_height`, `disc_ap_bulge`, `disc_height_index`,
> `pfirrmann_grade`) — they exist but await integration (Mohammad). So a live report today carries
> G1/G4/G5 + G3 keys; disc keys arrive later. Frontend should treat any measurement_key as
> **optional/may-be-absent** (a component can also error — see §3). 🟡 on the disc keys' presence.

---

## 2. 🟢 `flags` — boolean clinical/quality flags
Shape: `{ flag_key: { level_or_pair: bool } }`. A flag being `true` means "finding for physician
review," never a diagnosis. **Two classes** (frontend should style differently):

| flag_key | class | meaning | keyed by |
|---|---|---|---|
| `vb_compression_screen_positive` | clinical | Ha/Hp below cohort screen cut | level |
| `wedge_fracture` | clinical | Genant wedge shape | level |
| `biconcave_fracture` | clinical | Genant biconcave shape | level |
| `spondylolisthesis_present` | clinical | slip ≥ 2 mm | pair |
| `ap_width_outlier` | **quality** | AP width outside 12–22 mm sanity | level |
| `tilt_outlier` | **quality** | vertebra tilt caution (segmentation/orientation) | level |

**Quality vs clinical** is decided centrally: a flag is "quality/caution" if its name contains any of
`low_confidence, misaligned, approximate, resolution, warning, outlier, unreliable`
(see `interpretation.QUALITY_FLAG_MARKERS`). Quality flags must NOT be shown as patient abnormalities —
render them as data-quality cautions. 🟢 on the two classes; 🟡 on the exact flag_key set (more arrive with G2/G3).

---

## 3. 🟢 `components` — per-component execution status
Shape: `{ component_name: { status, duration_s, error?, metadata? } }`.
- `status`: `"ok"` | `"error"` 🟢
- `error`: present only when status=error; a human-readable message (e.g. *"c3c7_cobb_angle: C3 or
  C7 inferior endplate is not measurable…"*). A component erroring is NORMAL (e.g. cord components
  without an SCT mask, or Cobb when C7 is obscured) — the rest of the report is still valid.
- `metadata`: optional per-component extras (grade strings, level lists, caveats). 🟡 contents vary by component.

Frontend rule: a measurement_key is absent if its component errored or isn't wired. Show "not measured" not "0".

---

## 4. 🟢 `interpretations.measurements[]` — the InterpretedMeasurement container (FROZEN)
This is the most useful object for the UI: one row per (measurement × level), already classified
against the cited threshold catalog. Shape (`dataclass InterpretedMeasurement`):

```json
{
  "measurement": "vb_hahp_ratio",
  "level": "C4",
  "value": 0.91,
  "unit": "ratio",
  "status": "within_reference",
  "severity": "normal",
  "flag": false,
  "demographics_used": {},
  "quality_flags": ["tilt_outlier"],
  "caveat": "Vertebral-body compression/deformity screen, NOT a general fracture detector …"
}
```

- `status` 🟢 **standardized vocabulary** (exactly these four):
  `within_reference` | `outside_reference` | `review_only` | `not_interpretable`.
- `severity` 🟡 **per-measurement label** (string or null) — vocabulary differs by measurement:
  - Ha/Hp: `normal | borderline | compression_screen_positive`
  - slip: `neutral | borderline | slip_present_screen`
  - dural sac: `normal | borderline | stenosis_provisional`
  - SAC: `normal | high_risk`
  - Cobb: `lordotic | straightened | kyphotic`
  - bulge: `no_bulge | bulge_present | cord_risk`
  - Pfirrmann/Miyazaki: `grade_I … grade_V`
  - AP width (quality): `within_sanity | ap_width_outlier`
  - myelomalacia: `none | signal_anomaly_present`
  - gaps (segmental_angle, posterior_tangent, DHI, cord_AP, tilt): `null` (review_only / not_interpretable)
- `flag` 🟢 boolean; `true` ⇔ `status == outside_reference`.
- `caveat` 🟢 string|null — the cited modality caveat (provenance lives centrally in `thresholds.py`).
- `quality_flags` 🟢 list of quality flag names active at this level.
- `demographics_used` 🟡 currently `{}`; will carry age/sex when demographic norms land.

### value → status mapping (so the frontend/EEP can mock it)
`classify(measurement_key, value)` walks ordered bands `[lo, hi)` (lo inclusive, hi exclusive; null = open):
- `vb_hahp_ratio`: ≥0.81 within·normal; [0.68,0.81) within·borderline; <0.68 **outside**·compression_screen_positive
- `spondy_slip_mm`: <1.0 within·neutral; [1.0,2.0) within·borderline; ≥2.0 **outside**·slip_present_screen
- `dural_sac_AP_min`: ≥13 within·normal; [10,13) within·borderline; <10 **outside**·stenosis_provisional
- `SAC`: ≥3 within·normal; <3 **outside**·high_risk
- `Torg_Pavlov_ratio`: ≥0.8 within·normal; <0.8 **outside**·developmental_stenosis_screen
- `Cobb_C3_C7`: ≥10 within·lordotic; [0,10) **review**·straightened; <0 **review**·kyphotic
- `posterior_bulge_mm`: <1 within·no_bulge; [1,1.35) **outside**·bulge_present; ≥1.35 **outside**·cord_risk
- `pfirrmann_grade`: grade g → **review**·grade_{I..V}
- `myelomalacia`: <0.5 within·none; ≥0.5 **outside**·signal_anomaly_present
- `AP_width`: [12,22) within; else **review**·ap_width_outlier
- `DHI`, `cord_AP`, `segmental_angle`, `posterior_tangent_C3_C7`, `tilt_deg`: no bands → `review_only`
  (tilt → `not_interpretable`)

> ⚠️ Several catalog thresholds (dural-sac/SAC/Torg over-flag on MRI; the 1.35 mm bulge cord-risk
> figure is unverified) are **scheduled for correction** during validation. The *shape* is frozen;
> some band *cut values* are 🟡 and will be updated. Frontend: don't hardcode cut values — read them
> from the response, not from this table.

---

## 5. 🟡 `interpretations` extras (available, not yet in the default report)
- **Group 5 → 6 findings contract** (`group5/flags_contract.py::build_flags_contract`): a per-level
  document with `levels[].fracture` (Ha/Hp, Genant grade/type, screen status, note) and
  `levels[].myelomalacia` (assessed/present/engine), plus `not_assessed`, `provenance` (norm + rule +
  z + citations), `caveats`. Currently attached under the fracture-screen component's metadata
  (`group5_contract`). 🟡
- **Syndrome indicators** (`interpretation.detect_syndromes`): provisional, advisory-only patterns
  (`possible_myelopathy`, `possible_radiculopathy`) — `{syndrome, level, status, advisory,
  contributing[], provisional:true, caveat}`. Not wired into the default report yet. ⚪/🟡

---

## 6. ⚪ `case` — identity + de-identified metadata (PROPOSED, EEP)
```json
{
  "case_id": "demo-healthy-0001",
  "status": "ready",
  "modality": "T2 sagittal MRI",
  "series_description": "T2 SAG",
  "study_date": null,
  "uploader": "demo",
  "triage_badge": "none",
  "patient": { "sex": null, "age": null },
  "created_at": "ISO-8601", "updated_at": "ISO-8601",
  "levels_measured": ["C3","C4","C5","C6","C7"],
  "segmenters_used": { "vertebra_disc": "...", "canal_cord": "...", "alignment_endplate": "..." }
}
```
- `status` ⚪ enum: `queued | processing | ready | error | reviewed`.
- `triage_badge` 🟡 enum proposal: `none | review | urgent` (derive from worst flag; rule TBD).
- No PHI ever (medical-AI rule): de-identified ids only; no raw names/MRN.

## 7. ⚪ Upload + QC error (PROPOSED, EEP)
- Accepts: a **DICOM series as .zip** OR a **NIfTI `.nii.gz`** (one sagittal T2 cervical study).
- Limits 🟡: proposal ≤ 500 MB; reject non-sagittal / non-cervical / 4D / degenerate (the segmentation
  `input_handler` already does fail-fast QC).
- Success response: `{ "case_id": "...", "status": "queued" }`.
- QC-fail response uses the standard error shape (§9) with `failed_stage:"upload"` (e.g.
  `{code:"qc_orientation", message:"series is coronal, expected sagittal", failed_stage:"upload", retryable:false}`).

## 8. ⚪ `job` — processing status (PROPOSED, EEP)
```json
{ "stage": "measuring",
  "stages": ["queued","segmenting","measuring","interpreting","ready"],
  "progress": 0.6, "error": null }
```
`stage` ⚪ enum (the 5 above + `error`). `progress` 🟡 0..1.

## 9. ⚪ Error shape (PROPOSED, used everywhere)
```json
{ "code": "string_enum", "message": "human readable", "failed_stage": "upload|segmenting|measuring|interpreting|reporting", "retryable": true }
```

## 10. 🟡 `report` — rendered document (reporting svc scaffold)
`reporting/builder.build_report_document` currently returns `{case, impression, findings, metadata}`.
Proposed fuller shape:
```json
{ "impression": [ { "text": "...", "traceable_to": ["vb_hahp_ratio"], "status": "within_reference" } ],
  "findings_by_level": "see interpretations.measurements",
  "disclaimers": ["screens flag for physician review, never a diagnosis", "..."] }
```
Every impression item carries `traceable_to` (the measurement_keys behind it) so the UI can link
impression → measurement → citation. 🟡

---

## What's FROZEN today vs what will move
- 🟢 FROZEN: `measurements`/`flags`/`components`/`interpretations` shapes; the 4-value `status` vocab;
  `InterpretedMeasurement` fields; level=`C3..C7`, pair=`C3-C4` formats; quality-vs-clinical flag rule.
- 🟡 WILL MOVE: some band *cut values* (validation corrections), the disc-key/flag-key *set* (G2/G3
  wiring), `severity` labels at the margins, `triage_badge`/limits.
- ⚪ PROPOSED (define-with-EEP): `case`, `job`, `upload`, error shape, `report` envelope.

**Mock-first guidance:** build the UI against [`samples/case-healthy.json`](samples/case-healthy.json)
(real pipeline output + the proposed envelope). Read cut values/citations from the response, never hardcode.
Treat every measurement/flag key as optional. The science code will drop in behind these shapes unchanged.
