"""Group 4 endpoint-precision comparison on 12 healthy necks: three cervical-Cobb methods.

For each Spine-Generic healthy neck, compute the C2-C7 / C3-C7 / mid / C6-C7 Cobb three ways:
  (ENDPLATE) fit the line to SPINEPS' own endplate voxels  -> cervical_alignment.spineps_endplate_cobb_angle
  (corpus)   fit the line to the SPINEPS corpus (label 49)  -> cervical_alignment.spineps_cobb_angle
  (canal-cut) vertebra body anterior to the TSS canal       -> cervical_alignment.cobb_angle

No radiologist ground truth exists for these healthy necks, so this measures PRECISION (spread
across the cohort) + COVERAGE (levels measurable, esp. C7), NOT accuracy. The ENDPLATE method
(Option C1, found via the research workflow) fits the validated Wang-2023 line to the real endplate
voxels SPINEPS already outputs, and beats the other two on every span. Run: `python run_spineps_alignment.py`.
"""
import glob
import os
import re

import nibabel as nib
import numpy as np

from cervical_alignment import cobb_angle, spineps_cobb_angle, spineps_endplate_cobb_angle

SPINEPS_DIR = os.path.expanduser("~/dev/group5-proto/out_sg_spineps")
TSS_DIR = os.path.expanduser("~/dev/group5-proto/out_sg")

# (label, SPINEPS top instance, SPINEPS bottom instance, TSS top label, TSS bottom label)
PAIRS = [
    ("C2-C7", 2, 7, 12, 17),   # full span incl. both endpoints
    ("C3-C7", 3, 7, 13, 17),
    ("C3-C5", 3, 5, 13, 15),   # mid-cervical
    ("C6-C7", 6, 7, 16, 17),   # the problem endpoint segment
]


def _subject(path):
    m = re.search(r"(sub-[A-Za-z0-9]+)", os.path.basename(path))
    return m.group(1) if m else None


def _load(path):
    img = nib.load(path)
    return (np.asarray(img.dataobj),
            nib.aff2axcodes(img.affine),
            tuple(float(z) for z in img.header.get_zooms()[:3]))


def _stat(vals):
    ok = [v for v in vals if v is not None]
    if not ok:
        return f"--            (0/{len(vals)})"
    return f"{np.mean(ok):+5.1f} +/- {np.std(ok):4.1f}  ({len(ok)}/{len(vals)})"


def main():
    subs = sorted({_subject(f) for f in glob.glob(f"{SPINEPS_DIR}/sub-*_seg-vert_msk.nii.gz")})
    rows = {p[0]: {"ep": [], "corpus": [], "cc": []} for p in PAIRS}

    for sub in subs:
        spine_f = f"{SPINEPS_DIR}/{sub}_mod-T2w_seg-spine_msk.nii.gz"
        vert_f = f"{SPINEPS_DIR}/{sub}_mod-T2w_seg-vert_msk.nii.gz"
        tss_f = f"{TSS_DIR}/{sub}_T2w_step2.nii.gz"
        if not (os.path.exists(spine_f) and os.path.exists(vert_f) and os.path.exists(tss_f)):
            continue
        S, ax_s, z_s = _load(spine_f)
        V, _, _ = _load(vert_f)
        T, ax_t, z_t = _load(tss_f)
        for name, sp_t, sp_b, cc_t, cc_b in PAIRS:
            rows[name]["ep"].append(spineps_endplate_cobb_angle(V, ax_s, z_s, sp_t, sp_b))
            rows[name]["corpus"].append(spineps_cobb_angle(S, V, ax_s, z_s, sp_t, sp_b))
            rows[name]["cc"].append(cobb_angle(T, ax_t, z_t, cc_t, cc_b))

    print("=== Cobb precision on 12 healthy necks: mean +/- SD (coverage) -- lower SD = more precise ===")
    print("(lordosis-positive; supine MRI, no GT -> read spread + coverage, not absolute accuracy)\n")
    print(f"{'span':<8}{'ENDPLATE (C1)':>24}{'corpus':>24}{'canal-cut':>24}")
    for name, *_ in PAIRS:
        print(f"{name:<8}{_stat(rows[name]['ep']):>24}{_stat(rows[name]['corpus']):>24}{_stat(rows[name]['cc']):>24}")


if __name__ == "__main__":
    main()
