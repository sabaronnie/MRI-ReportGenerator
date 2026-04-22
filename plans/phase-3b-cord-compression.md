# Phase 3B — Cord / Compression Measurements

**Owner:** TBD
**Reviewer:** TBD
**Status:** v1 content imported — under team review
**Last updated:** 2026-04-22 by Andrew (initial import from master_plan_v1.md)

---

## What a reviewer should check

- Does the method chosen actually work on Duke's segmentation masks?
- Are the alternatives rejected for the right reasons?
- Is any repo/reference missing? Add it if so.
- Does anything here conflict with another phase? Flag it.
- Is anything unclear? Mark it as an open question at the bottom.

---

### 3B — Cord / compression engine (SCT-based)

All 3B measurements use Spinal Cord Toolbox commands. Pipeline integration is via Python `subprocess` calls writing/reading NIfTI files.

#### 3B.1 Cord segmentation

**Method:** `sct_deepseg -task seg_sc_contrast_agnostic -i t2.nii.gz -o cord_seg.nii.gz`.

The contrast-agnostic model is their current recommended default (replaces earlier `sct_deepseg_sc`). Works across T1/T2/STIR. Outputs a 3D binary mask of the cord.

**Manual correction path:** For the Clinical Validation subset, SCT provides a web QC interface (`sct_qc`) that a radiologist can use to flag bad segmentations without having to run anything locally. Following the [Muhammad 2025 DCM pipeline](https://pmc.ncbi.nlm.nih.gov/articles/PMC12560734/) workflow: auto-segment, review via QC, manually correct outliers. They reported needing manual correction on 25% of compression cases vs 3% of controls — our expected rate.

**Code asset:** SCT (LGPLv3), full install.

#### 3B.2 Cord AP diameter + CSA

**Method:** `sct_process_segmentation -i cord_seg.nii.gz -vertfile levels.nii.gz -perlevel 1 -o cord_morph.csv`.

The `-vertfile` takes vertebral-level labels — we feed it TotalSpineSeg's `step1_levels` output (which is the canal centerline with single-voxel markers at each IVD level). `-perlevel 1` gives per-level outputs.

Output CSV columns we use: `MEAN(diameter_AP)`, `MEAN(area)`, `MEAN(diameter_RL)`, `MEAN(eccentricity)`, `MEAN(solidity)`.

**Why not compute AP diameter ourselves from the cord mask:** SCT does it correctly, including angle correction for tilted cord, and its values are citable and published. Rolling our own would invite clinical pushback.

**Code asset:** SCT command, wrapped in Python subprocess.

#### 3B.3 SAC (Space Available for Cord) — derived

**Method:** `SAC[level] = canal_AP[level] (from 3A.7) − cord_AP[level] (from 3B.2)`.

Per-level. SAC < 3 mm indicates high compression risk even if canal alone looks borderline.

**Code asset:** ~5 lines.

#### 3B.4 Maximum Spinal Cord Compression (MSCC) / Maximum Canal Compromise (MCC)

**Method:** `sct_compute_compression -i cord_seg.nii.gz -l compression_labels.nii.gz -vertfile levels.nii.gz -mode compression -metric diameter_AP -normalize-hc 1 -sex {M|F} -age [min max]`.

Returns MSCC: cord diameter at compression site compared to above and below (Miyanji 2007 formula). The `-normalize-hc` flag normalizes against the healthy controls database (Valošek 2024, *Imaging Neuroscience*), which is sex- and age-stratified. Pass patient sex and age from the Duke `Clinical_manifest` TSV.

**Caveat:** Requires `compression_labels.nii.gz` — a file pointing to the compression site. Two paths here:

- **Clinical mode:** radiologist clicks the compression site in QC UI (for the AUBMC validation subset)
- **Fully automated mode:** use `sct_detect_compression` (3B.5) to auto-detect, then feed its output into `sct_compute_compression`.

We implement fully automated mode by default.

**Code asset:** SCT commands chained.

**Reference:** Valošek et al. 2024, *Imaging Neuroscience* — the healthy-control normalization database that makes `-normalize-hc` work.

#### 3B.5 Automated compression detection

**Method:** `sct_detect_compression -s cord_seg.nii.gz -discfile step1_levels.nii.gz`.

Based on Horáková 2022 (*Quant Imaging Med Surg*) — sensitivity 87.3%, specificity 90.2% for cervical cord compression detection. Uses the compression ratio (CR = AP/RL) and its local derivative to find compression sites.

**Limitation:** Horáková paper only validated for C3/C4 through C6/C7 disc levels. We do not run it at C2/C3 or C7/T1 (per their paper). The tool itself enforces this.

**Code asset:** SCT command.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
