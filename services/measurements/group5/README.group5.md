# Group 5 — signal/shape-based abnormal-finding screens (Andrew)

Legacy imported README snapshot from the original standalone Group 5 workspace. The actual code
now lives under `services/measurements/group5/`, and the original root `group5/` folder has been
removed.

Screens for abnormal findings the geometric groups (1–4) don't: vertebral-body deformity
(compression/fracture) and cord signal (myelomalacia). Outputs are **screens that flag findings
for physician review — never diagnoses.** Developed standalone in `~/dev/group5-proto` (outside
the repo, to keep heavy imaging data off git) and imported here.

Core runtime code that is now part of the pipeline lives under
[`services/measurements/group5/`](./). Research/support material from the old standalone layout is
now colocated in this same area under `research/` and `../tests/group5/`.

> **Data is NOT in git.** All NIfTI/DICOM (Duke, Spine-Generic, RSNA) live locally / on Drive and
> are `.gitignore`d. Segmentation (TotalSpineSeg / SCIseg) runs on Colab GPU; only the lightweight
> measurement code runs locally.

## Status (definition of done)
| Sub-part | What it does | Status |
|---|---|---|
| **5.2 Fracture** | vertebral-body compression/deformity screen | ✅ validated + calibrated + cited |
| **5.1 Myelomalacia** | cord T2-hyperintensity screen (SCIseg) | ✅ code/wiring; healthy-specificity run pending Colab |
| **5→6 contract** | the flags-JSON Group 6 consumes | ✅ emitter + end-to-end runner |
| **5.3 Tumor/mass** | — | ⛔ scoped out (see Limitations) |
| **5.4 Post-surgical scar** | — | ⛔ deferred (see Limitations) |

## End-to-end runner (Group 5 in one command)
- `run_group5_pipeline.py` — a TSS `step2` mask (+ optional SCIseg lesion mask) → the 5→6 flags JSON.
  Glues 5.2 + 5.1 + the contract; the only new logic (assembly loop + lesion→level mapping) is TDD'd.
  ```
  python run_group5_pipeline.py <step2.nii.gz> [--lesion <lesion_seg.nii.gz>] [--case-id ID] [-o out.json]
  # batch a whole cohort (pairs step2 <-> lesion masks by subject, one JSON per case):
  python run_group5_pipeline.py <step2_dir> [--lesion <lesion_dir>] -o <out_dir>
  ```
  Without `--lesion`, myelomalacia reads "not assessed"; with it, every level is assessed and flagged
  where the cord lesion overlaps that level's superior–inferior span.

## 5→6 output contract
- `flags_contract.py` — `build_flags_contract()` emits the per-level findings document Group 6 reads
  (fracture screen + myelomalacia + provenance/citations + `not_assessed` + caveats; no-diagnosis
  wording throughout). Shaped for `plans/phase-4-interpretation.md`. **v0.1 — pending team sign-off.**
- `test_flags_contract.py` — 7 tests.

## 5.2 — Vertebral compression/deformity screen (validated)
- `vertebral_fracture.py` — isolate the vertebral **body** at the spinal **canal** (`extract_body_via_canal`)
  → PCA tilt-orient + endplate-line heights (`endplate_line_heights`) → 6-point Ha/Hm/Hp.
  `classify_genant` = the medical Genant grade (unchanged standard). `cervical_deformity_flag` = the
  **data-driven cervical screen**: flags Ha/Hp < mean − z·SD off the measured healthy cohort
  (`COHORT_HAHP_MEAN=0.94, SD=0.13`), z=2.0 → ~0.68. `z` is an exposed specificity policy.
- `test_vertebral_fracture.py` — 30 tests. `run_fracture_on_tss.py` — measure on a TSS step2.
- `run_fracture_on_rsna.py` + `download_rsna.py` — RSNA-2022 harness. `downsample_to_duke_res.py` —
  resolution control used in the healthy validation.
- **Validation (2026-06-04/05):** healthy Ha/Hp **0.94** (median 0.92, Spine-Generic n=60) ∈ verified
  healthy range **0.88–0.95** (Tan 2004 / Lee 2012 / Kaur 2025); Duke DCM **0.85** below → real
  degeneration; resolution ruled out (0.8mm ≈ 4mm). Recalibrated norm + screen replaced the debunked
  0.97±0.02 / 0.80 cutoff → **healthy false-positive 17% → 0%**. z=2.0 confirmed by lit search (no
  cervical compression-fracture Ha/Hp data exists; SD is the lever). Cite Tan 2004 / Lee 2012 /
  Kaur 2025 + Chen 2013 / Nell 2019.
- **Scope honesty:** a vertebral-body **compression/deformity screen**, NOT a general fracture detector
  (RSNA-2022 showed ~zero power on non-compression fractures: odontoid/facet/arch). Per-vertebra SD
  wide (±0.13) → group/screening-level, coarse per body. Norm triangulated (no like-for-like MRI
  cervical comparator) → plausibility, not proof.

## 5.1 — Myelomalacia (cord T2 hyperintensity)
- Decision: **adopt SCIseg** (`sct_deepseg lesion_sci_t2`, in Spinal Cord Toolbox) as the engine —
  simple intensity thresholds can't separate lesion from normal cord variation. Sensitivity rests on
  SCIseg's published validation (Naga Karthik 2024, PMC11065035).
- `myelomalacia_specificity.py` — `lesion_burden()` (voxels + anisotropy-safe mm³ + largest component)
  and `healthy_specificity()` (cohort false-positive rate, tunable `min_lesion_mm3`). 6 tests.
- `run_sciseg_specificity.py` — score a folder of SCIseg lesion masks → FP rate.
- `myelomalacia.py` / `test_myelomalacia.py` / `compare_to_sciseg.py` — interpretable hand-rolled
  baseline (Weber CSF-ratio + local-window) + agreement-vs-SCIseg harness.
- **Pending:** run SCIseg on the 12 healthy Spine-Generic cords (Colab) → `run_sciseg_specificity.py`
  → confirm FP rate ~0% ("on healthy, flags nothing"); the masks then auto-pair into `run_group5_pipeline.py`.

## Scope & Limitations (5.3 and 5.4)
- **5.3 Tumor / intramedullary or extradural mass — SCOPED OUT (2026-06-05).** No public dataset pairs
  cervical T2 MRI with labeled tumor/mass annotations (confirmed across repeated dataset hunts), so a
  detector cannot be validated and would risk over-claiming on a clinical finding. Deliberately excluded
  from v1; the contract lists it under `not_assessed`. *Revisit only if labeled data (e.g. AUBMC) becomes
  available* — at which point the honest minimum is a "flag abnormal cord/canal signal region for physician
  review" screen with a healthy-specificity check, not a tumor classifier.
- **5.4 Post-surgical scar / fibrosis — DEFERRED (out of scope).** Distinguishing scar from recurrent
  disc/disease requires **gadolinium-enhanced (contrast) sequences**, which are not part of the project's
  sagittal-T2 input. Cannot be done on T2 alone → excluded; documented here and in the contract's
  `not_assessed`. Not revisitable without a contrast-enhanced acquisition.

## Colab notebooks (GPU segmentation)
These now live under [`colab/group5/`](../colab/group5/).

- `colab/group5/colab_segment_tss_fracture.ipynb`, `colab/group5/colab_segment_spinegeneric.ipynb` — TotalSpineSeg (full mode).
- `colab/group5/colab_sciseg_spinegeneric.ipynb` — SCIseg on the healthy cohort (5.1 specificity).
- `colab/group5/colab_segment_duke.ipynb` — SCIseg on Duke patients.
- `colab/group5/colab_spineps_spinegeneric.ipynb` — SPINEPS endplate-voxel alignment workflow.

## Run / test
- Interpreter: `~/dev/group5-proto/.venv/bin/python`. Tests: `pytest group5/` (run from repo root or the proto).
- Audit of the teammates' Groups 1–4 measurement code (with the verified research fixes):
  `AUDIT_groups1-4_measurements.md`.
