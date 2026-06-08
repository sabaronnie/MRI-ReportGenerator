═══════════════════════════════════════════════════════════════════════════════
HANDOFF → FRONTEND/INFRA chat: LINK the measurement pipeline to the report UI · 2026-06-08
From: the executor/science chat. Paste this whole block. I am Andrew.
═══════════════════════════════════════════════════════════════════════════════

## 0) GOAL
The measurement + interpretation pipeline is ready and produces output that ALREADY matches your
frozen contract shape. Link it so a real uploaded MRI flows: **MRI → measurements (this code) →
contract JSON → your existing report components render it.** Report generation stays yours; this side
only produces the data.

## 1) PULL THE MEASUREMENT CODE
- Branch (pushed): **`research/andrew/writeups`** (origin). The code you need is two dirs:
  `services/measurements/**` and `services/interpretation/**`. Merge/cherry-pick those into the
  measurements IEP image. (The branch also carries paper/docs — ignore those for this task.)
- What changed since you last pulled (all tested, 137/137 green):
  - **G2 disc is now WIRED into the orchestrator** (was excluded) → the report now includes
    `DHI`, `posterior_bulge_mm`, `pfirrmann_grade`, `disc_vb_ap_ratio`.
  - **Patient demographics** flow through: `load_context(..., age=, sex=, height_cm=)`; the run output
    has a `patient` block; interpretation populates `demographics_used` and applies the **sex-specific
    dural-sac cut** (Nell M<10/F<9 mm).
  - **G6 fixes**: only cited thresholds raise a clinical flag (no more fabricated flags on intermediate
    keys); debunked `DHI<0.30` replaced by relative >30% drop.

## 2) THE INTERFACE (how to call it)
```python
from services.measurements.context import load_context
from services.measurements.orchestrator import run_all

ctx = load_context(
    seg_path,                       # TotalSpineSeg step2 labelmap (required)
    levels_path=...,                # TSS step1_levels (required for G3 canal/cord level-mapping)
    raw_path=...,                   # grayscale MRI (optional; needed only for disc SIGNAL grade)
    sct_canal_seg_path=..., sct_cord_seg_path=...,   # SCT masks → G3 (run live in the deployed env)
    spineps_seg_path=...,           # SPINEPS seg-vert → G4 C1 Cobb (optional; falls back to canal-cut)
    age=58, sex="M", height_cm=175, # demographics from upload; pass None when unknown
)
report = run_all(ctx)               # dict: components, measurements, flags, interpretations, patient
```
`run_all` returns a JSON-serialisable dict. **A missing input never crashes** — that component reports
`status:"error"` and its keys are simply absent (your contract already treats every key as optional).

## 3) THE MAPPING — run_all output → your contract envelope
Your contract (`frontend/src/lib/api/contract.ts`) top keys: `schema_version, case, job, measurements,
flags, interpretations, report`. The mapping is almost a passthrough:

| Contract field | Source from `run_all` | Note |
|---|---|---|
| `measurements` | `report["measurements"]` | **passthrough** — same `{key:{level:number}}` shape |
| `flags` | `report["flags"]` | **passthrough** — `{key:{level:bool}}` |
| `interpretations.measurements` | `report["interpretations"]["measurements"]` | **EXACT match** — every row already has `measurement, level, value, unit, status, severity, flag, demographics_used, quality_flags, caveat` (your `InterpretedMeasurement` type) |
| `case.patient` | `report["patient"]` → `{sex, age}` | (`height_cm` is captured but record-only — drop or keep, your call) |
| `case.levels_measured` | levels present in `measurements` | C3–C7 |
| `case.triage_badge` | derive (rule below) | |
| `case.{case_id,status,modality,...}` | EEP envelope | you own these |
| `job` | EEP job tracker | you own |
| `report.{impression,findings}` | **derive from the flagged interpretation rows** | one impression line per `status=="outside_reference"` row, `traceable_to=[measurement]`, using the row's `caveat` text — exactly as your fixtures show |

**triage_badge rule (proposed; contract said TBD):** `urgent` if any **non-quality** interpretation row
has `status=="outside_reference"`; else `review` if any `review_only` row carries a clinical
`report.flags` entry; else `none`. (Quality flags via `isQualityFlag()` never escalate.)

## 4) AGE / SEX CAVEAT (must surface honestly in the UI)
For our EXISTING demo MRIs we often do NOT have patient age/sex. When `sex` is null, interpretation uses
the **sex-neutral** dural-sac cut (10 mm) — correct in logic, not patient-specific. **Height is never
used by any cervical threshold** (no such norm exists) — collect it record-only or skip. Wording to show:
*"Demographic-adjusted thresholds apply when age/sex are provided; with patient data absent, sex-neutral
defaults are used. Clinical accuracy of demographic-adjusted findings will be confirmed once cases with
complete patient data are available."*

## 5) CROSS-REFERENCE CASES (verify the link renders MY values)
I ran the full pipeline locally on 2 cases. After you link, render these two and confirm the numbers
match mine EXACTLY (same code → same values). These are the link's acceptance test:

**A) sub-amu01 — healthy control (Spine-Generic), patient age 28 / sex M / height 176**
- canal_AP (mm): C3 14.9 · C4 14.6 · C5 14.8 · C6 14.5 · C7 15.3   (min 14.5)
- SAC (mm): C3 6.7 · C4 6.5 · C5 7.1 · C6 7.2 · C7 8.6
- Cobb C3–C7: **+16.7°** (lordotic) · vb_hahp min 0.80 (borderline at C5)
- **0 clinical flags** · triage_badge expected: `none`

**B) mmcsd-csm-002 — symptomatic CSM (MMCSD), patient age 53 / sex null (sex-neutral)**
- canal_AP (mm): C3 11.8 · C4 11.5 · C5 10.5 · C6 **10.0** · C7 11.1   (min 10.0)
- SAC (mm): C3 4.9 · C4 4.6 · C5 3.7 · C6 **3.4** · C7 5.0
- Cobb C3–C7: **+4.3°** (straightened — CSM loses lordosis)
- **1 clinical flag**: `dural_sac_AP_min` = 10.0 mm → stenosis_provisional · triage_badge expected: `urgent`

The clinical contrast (healthy: open canal + lordotic; CSM: narrowed canal/SAC + straightened) is the
demo story — make sure your render preserves it.

## 6) WHAT HAPPENS AFTER YOU LINK
Andrew will render these 2 cases through your UI → send the 2 reports back here → **I re-run the pipeline
locally and cross-reference every value against your rendered report** to confirm the link is correct.
Then the 2 frontend-rendered reports + the 2 MRIs go to a radiologist. (I also have the raw `run_all`
JSON for both cases as the ground-truth — `radiologist_demo/report_*.json` — happy to share.)

## 7) NOTES / GOTCHAS
- Read thresholds/citations/caveats FROM the response (your contract.ts already says this) — every
  interpretation row carries its own `caveat` + the catalog citation is in `services/interpretation/
  thresholds.py`.
- `pfirrmann_grade` (disc signal) needs `raw_path`; it's the one component that skips without grayscale,
  and we've shown disc signal is a documented non-discriminator anyway — don't gate the report on it.
- G3 (canal/cord/SAC) runs SCT live in the deployed env; locally I injected it from precomputed SCT CSVs,
  so my cross-ref values for G3 are real SCT output.
═══════════════════════════════════════════════════════════════════════════════
