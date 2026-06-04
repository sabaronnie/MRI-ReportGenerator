# Group 5 — signal-based abnormal-finding detection (Andrew)

Detects abnormal findings the geometric groups (1–4) don't: cord signal (myelomalacia),
vertebral-body deformity (fracture), and tumor. Developed standalone in `~/dev/group5-proto`
(outside the repo, to keep the heavy imaging data off git) and imported here.

> **Data is NOT in git.** All NIfTI/DICOM (Duke, Spine-Generic, RSNA) live locally / on Drive
> and are `.gitignore`d. Segmentation (TotalSpineSeg / SCIseg) runs on Colab GPU; only the
> lightweight measurement code runs locally.

## 5.2 — Vertebral fracture (validated)
- `vertebral_fracture.py` — the core. Pipeline: isolate the vertebral **body** by cutting at the
  spinal **canal** (`extract_body_via_canal`) → PCA tilt-orient + endplate-line heights
  (`endplate_line_heights`) → 6-point Ha/Hm/Hp + `classify_genant`. Tilt- and taper-robust.
- `test_vertebral_fracture.py` — 25 tests (run: `pytest group5/`).
- `run_fracture_on_tss.py` — measure on a TotalSpineSeg `step2_output` (vertebrae + canal).
- `run_fracture_on_rsna.py` + `download_rsna.py` — RSNA-2022 fracture-label validation harness.
- `downsample_to_duke_res.py` — resolution control (0.8mm → 4mm) used in the healthy validation.

**Validation status (2026-06-04):** healthy Ha/Hp **0.94** (median 0.92, Spine-Generic n=60) lands
inside the verified healthy range **0.88–0.95** (Tan 2004 / Lee 2012 / Kaur 2025, cadaver, post>ant);
Duke DCM **0.85** sits below → real degeneration. Resolution ruled out (native 0.8mm ≈ downsampled
4mm). VB height 10.8mm ∈ healthy SI-height (≠ AP depth 15–18mm). **TODO:** replace the placeholder
thoracolumbar cutoff (0.80) + unsourced norm (0.97±0.02) with the cohort-derived flag
(≈ mean−2SD ≈ 0.68); cite Tan 2004 / Lee 2012 / Chen 2013 / Nell 2019.

## 5.1 — Myelomalacia (cord T2 hyperintensity)
- Decision: **adopt SCIseg** (`sct_deepseg lesion_sci_t2`, in Spinal Cord Toolbox) as the engine —
  simple intensity thresholds can't separate lesion from normal cord variation.
- `myelomalacia.py` — interpretable hand-rolled baseline (Weber CSF-ratio + local-window).
- `test_myelomalacia.py`, `compare_to_sciseg.py` — baseline tests + agreement-vs-SCIseg harness.

## Colab notebooks (GPU segmentation)
- `colab_segment_tss_fracture.ipynb`, `colab_segment_spinegeneric.ipynb` — TotalSpineSeg (full mode).
- `colab_segment_duke.ipynb` — SCIseg (5.1).

## 5.3 tumor / 5.4 scar
5.3 (mass) not started — narrow "flag for review" scope, no public labeled data. 5.4 (post-surgical
scar) deferred — needs gadolinium-enhanced sequences, out of scope; documented as a limitation.
