# Phase 2 — Segmentation

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

### 2.1 TotalSpineSeg (primary segmenter)

**Method:** Use the published pre-trained model from [neuropoly/totalspineseg](https://github.com/neuropoly/totalspineseg). Invoke via the `totalspineseg` CLI on the input NIfTI, read the `step2_output` folder for the final segmentation. Key points:

- Use `--iso` flag — resamples to 1mm isotropic for consistent geometric measurement downstream
- Use `step2_output` (final labels), not `step1_output` (which is pre-iterative-labeling)
- Read `step1_levels` as a bonus: single-voxel canal-centerline markers at each IVD level (useful for feeding into SCT later)

**Label map (from TotalSpineSeg README / `tss_map.json`):**

```
  1    spinal_cord          (⚠ not validated for compression — we use SCT instead for cord work)
  2    spinal_canal
 11    vertebrae_C1
 12    vertebrae_C2
 13    vertebrae_C3
 14    vertebrae_C4
 15    vertebrae_C5
 16    vertebrae_C6
 17    vertebrae_C7
 21    vertebrae_T1  (often present in cervical FOV)
 63    disc_C2_C3
 64    disc_C3_C4
 65    disc_C4_C5
 66    disc_C5_C6
 67    disc_C6_C7
 71    disc_C7_T1
```

**Rationale for choosing TotalSpineSeg over alternatives:**

| Alternative | Why rejected |
|---|---|
| Duke's own nnU-Net model (from their paper) | Binary only — no per-level labeling. We would have to build our own connected-components labeling; TotalSpineSeg already solved this. |
| SPINEPS ([Möller 2025](https://doi.org/10.1007/s00330-024-11155-y)) | Excellent whole-spine model, but focus is lumbar + thoracic, and cervical-specific validation is thinner. Also not actively maintained vs TotalSpineSeg. |
| Train our own nnU-Net on Duke | 3.5 TB disk + 32 GB RAM + weeks of training. No value-add over TotalSpineSeg for cervical. |

**Code asset:** [neuropoly/totalspineseg](https://github.com/neuropoly/totalspineseg) — install with `pip install totalspineseg[nnunetv2]`. Fully open-source (LGPLv3).

**Reference:** Warszawer et al. 2025, ISMRM. Citation tag `warszawer2025totalspineseg`.

### 2.2 Spinal Cord Toolbox (cord segmenter + compression)

**Method:** TotalSpineSeg's cord output is explicitly flagged in their README as "not validated for CSA measurements, nor tested on cases involving spinal cord compressions." For all cord measurements we invoke [Spinal Cord Toolbox](https://github.com/spinalcordtoolbox/spinalcordtoolbox):

- `sct_deepseg -task seg_sc_contrast_agnostic -i <input.nii.gz>` — validated cord segmentation (works on T1, T2, T2*, etc.)
- Feed TotalSpineSeg's `step1_levels` file in as disc-level labels for SCT (it expects single-voxel labels at disc levels, which is exactly what step1_levels provides)
- Call `sct_compute_compression` and `sct_detect_compression` downstream (Phase 3B)

**Rationale:** Both TotalSpineSeg and SCT come from the same lab (Cohen-Adad's neuropoly at Polytechnique Montréal). SCT is the canonical tool for cord morphometry — >200 published studies use it. Rolling our own cord segmentation would fail clinical review.

**Code asset:** [spinalcordtoolbox/spinalcordtoolbox](https://github.com/spinalcordtoolbox/spinalcordtoolbox) — LGPLv3. Install via their launcher script.

### 2.3 Mid-sagittal slice selection

**Method:** For each sagittal slice index *i* in the TotalSpineSeg output volume, count the number of voxels belonging to any vertebra label (11–17, plus 21 if present). Choose the slice with the maximum vertebra pixel count. This is the team's pre-existing decision, confirmed in conversation.

**Concretely:**
```python
vertebra_labels = {11, 12, 13, 14, 15, 16, 17, 21}
def select_mid_sagittal(seg_volume):
    mask = np.isin(seg_volume, list(vertebra_labels))
    # sagittal axis assumed to be axis 0 after reorient; adjust if needed
    vertebra_counts = mask.sum(axis=(1, 2))
    return int(np.argmax(vertebra_counts))
```

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Center-of-mass along LR axis | Biased by any off-midline disc or osteophyte mass |
| Canal-centerline midline | Canal can be off-midline in scoliosis; unreliable |
| Max canal-label pixels | Canal is often continuous across several sagittal slices; no sharp peak |

The "max vertebra pixels" rule peaks sharply at the true midline because vertebral bodies are widest in their own mid-sagittal plane. Confirmed as the team's preferred method.

**Caveat to surface in QC:** If the argmax is flat (e.g. 3+ slices with near-identical counts), report that and pick the median of the tied set. If the argmax is within 2 slices of the volume edge, reject the case — the FOV is wrong.

**Code asset:** Custom, ~15 lines.

### 2.4 Segmentation QC

**Method:** Before any measurement runs, validate the segmentation output:

- All cervical vertebrae expected (C2–C7) present as distinct labels
- All cervical discs expected (C2/3 through C6/7) present
- No catastrophic label mismatches (e.g. C7 directly neighbouring C2 — indicates a label skip)
- Canal mask is continuous (single connected component) across sagittal extent covering C2–C7
- Cord mask (SCT) is a single connected component

Failures flag the case for manual review rather than silently producing bad measurements. This is essential for Duke's 1,255-case bulk run — we need to know which cases the pipeline couldn't handle.

**Code asset:** Custom, ~100 lines (scipy.ndimage.label + sanity rules).

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
