# Phase 1 — Input Handling

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

### 1.1 Accept DICOM folder or NIfTI file

**Method:** Detect input type from path (single `.nii.gz` / `.nii` file → direct use; folder → assume DICOM series). For DICOM input, convert with `dcm2niix` (MIT-licensed, cross-platform, used by the Duke paper itself for their published NIfTI data).

**Code asset:** `dcm2niix` binary ([rordenlab/dcm2niix](https://github.com/rordenlab/dcm2niix)). Invoke via `subprocess` or use the Python wrapper `dcm2niix-python`.

**Reference implementation:** Duke CSpineSeg repo has `dicom_nifti_dcm2niix.py` ([JikaiZ/CSpineSeg](https://github.com/JikaiZ/CSpineSeg)) that does exactly this — we adapt it directly rather than write from scratch.

**Why not pydicom alone:** dcm2niix correctly handles slice ordering, gantry tilt, diffusion metadata, and produces canonical NIfTI orientation (LPI/RAS) that downstream tools expect. Hand-rolled pydicom pipelines get these details wrong.

### 1.2 Sagittal orientation detection

**Method:** Read NIfTI affine (`nibabel`), determine which axis is left-right (sagittal normal). Reject the input if the scan is not sagittal-dominant. Optionally reorient to canonical RAS using `nibabel.as_closest_canonical` to standardize axes for downstream code.

**Code asset:** `nibabel` (pure Python, BSD). Approx. 30 lines.

**Caveat:** Some cervical MRIs include both sagittal and axial series in the same study. The pipeline explicitly rejects non-sagittal series; it doesn't try to auto-pick the sagittal one from a mixed DICOM folder. dcm2niix will convert all series; we select by matching DICOM `SeriesDescription` (e.g. contains "sag" and "T2", excludes "T1" / "STIR" unless user overrides). Duke filtered by the same heuristic ("sag T2" in StudyDescription).

### 1.3 Voxel spacing extraction

**Method:** Pull `pixdim` from the NIfTI header. Store as `(spacing_x, spacing_y, spacing_z)` in mm. Every measurement output in mm multiplies pixel distances by the appropriate spacing.

**Critical:** Every measurement must be reported in **physical units (mm, degrees)**, never in pixels. A 2D rotated-rectangle side in pixels is meaningless across scans. We propagate `spacing_x` and `spacing_y` from this step through every downstream module.

### 1.4 Input QC / fail-fast gate

**Method:** Run a small set of pre-flight checks before calling segmentation:

- Image dimensions reasonable (≥ 10 slices in sagittal axis, each ≥ 128×128)
- Voxel spacing finite and positive
- Intensity range non-degenerate (not all zeros, not uniform)
- No more than 20% of voxels are NaN
- Image is actually 3D (not 4D fMRI timeseries accidentally loaded)

Failures produce a clear error message and early exit. This prevents 8-minute segmentation runs on garbage inputs.

**Code asset:** Custom, ~50 lines of numpy.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
