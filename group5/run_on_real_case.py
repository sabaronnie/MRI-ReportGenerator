"""Run the Group 5.1 detector on REAL Spine Generic cases (T1w + manual cord mask).

Usage: python run_on_real_case.py [subject ...]   (default: sub-perform)

Spine Generic is the SAME anatomy imaged on different scanners, so running across
subjects is really a cross-scanner robustness test: a healthy cord should produce
NO flags regardless of machine (the scale-invariance point in action).

Real-world detail handled here: the shipped mask is often on a different grid than
the image (different shape and/or flipped L/R axis), so we resample the mask into
the image's space before reading intensities.

NOTE: T1w (that's what ships with a cord mask). Mechanics are identical on T2w;
clinical meaning is not. This proves plumbing + specificity, not sensitivity
(Spine Generic has no pathology, so it can only ever show "no false alarms").
"""
import sys

import nibabel as nib
import nibabel.processing as nibproc
import numpy as np

from myelomalacia import detect_cord_signal_abnormality

BASE = "/Users/andrew/Desktop/AUB/Spring 26/EECE 503n/Project/data/spine-generic/data-single-subject"


def si_axis(affine):
    """Index of the superior-inferior (head->foot) axis = the per-level axis."""
    for i, code in enumerate(nib.aff2axcodes(affine)):
        if code in ("S", "I"):
            return i
    raise ValueError(f"no S/I axis found in {nib.aff2axcodes(affine)}")


def run(subject):
    img = nib.load(f"{BASE}/{subject}/anat/{subject}_T1w.nii.gz")
    seg = nib.load(f"{BASE}/derivatives/labels/{subject}/anat/{subject}_T1w_seg-manual.nii.gz")
    seg_on_img = nibproc.resample_from_to(seg, img, order=0)  # align grids
    mri = img.get_fdata()
    mask = (seg_on_img.get_fdata() > 0.5).astype(int)
    axis = si_axis(img.affine)
    flags = detect_cord_signal_abnormality(mri, mask, level_axis=axis, threshold_ratio=1.3)
    ref = float(np.median(mri[mask == 1]))
    print(f"{subject:18s} img={str(img.shape):18s} cord_vox={int(mask.sum()):7d} "
          f"ref_intensity={ref:9.1f} flags={len(flags)}")
    return flags


if __name__ == "__main__":
    subjects = sys.argv[1:] or ["sub-perform"]
    print("subject            image shape        cord voxels  ref intensity  false-alarms")
    print("-" * 84)
    total_flags = 0
    for s in subjects:
        total_flags += len(run(s))
    print("-" * 84)
    print(f"across {len(subjects)} scanner(s): {total_flags} false alarm(s) on healthy cords "
          f"({'clean' if total_flags == 0 else 'see above'})")
