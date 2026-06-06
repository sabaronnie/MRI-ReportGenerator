"""Group 4 endpoint-precision pilot: SPINEPS-corpus Cobb vs canal-cut Cobb on 12 healthy necks.

For each Spine-Generic healthy neck, compute Cobb angles two ways and print them side by side:
  (a) SPINEPS corpus body   = (seg-spine == 49) & (seg-vert == instance)   [cervical_alignment.spineps_cobb_angle]
  (b) canal-cut TSS body    = vertebra label anterior to the spinal canal  [cervical_alignment.cobb_angle]

No radiologist ground truth exists for these necks, so this measures PRECISION (spread across the
cohort) + COVERAGE (how many levels are measurable, esp. C7) -- NOT MAE (see J9). The canal-cut
method read C2-C7 with SD ~16 deg and 9/12 measurable; the goal of the SPINEPS corpus is a tighter
C2-C7 SD + better C7 coverage (the learned body/arch split avoids the C6/C7 mis-shaping at the
cervicothoracic junction). Run: `python run_spineps_alignment.py`.
"""
import glob
import os
import re

import nibabel as nib
import numpy as np

from cervical_alignment import cobb_angle, spineps_cobb_angle

SPINEPS_DIR = os.path.expanduser("~/dev/group5-proto/out_sg_spineps")
TSS_DIR = os.path.expanduser("~/dev/group5-proto/out_sg")

# (label, SPINEPS top instance, SPINEPS bottom instance, TSS top label, TSS bottom label)
PAIRS = [
    ("C2-C7", 2, 7, 12, 17),   # full span incl. both endpoints
    ("C3-C7", 3, 7, 13, 17),
    ("C3-C5", 3, 5, 13, 15),   # mid-cervical -- canal-cut was stable here (+2.2 +/- 6.7)
    ("C5-C7", 5, 7, 15, 17),
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


def _fmt(v):
    return "   --" if v is None else f"{v:+5.1f}"


def _stat(vals):
    ok = [v for v in vals if v is not None]
    if not ok:
        return f"--           (0/{len(vals)})"
    return f"{np.mean(ok):+5.1f} +/- {np.std(ok):4.1f}  ({len(ok)}/{len(vals)})"


def main():
    subs = sorted({_subject(f) for f in glob.glob(f"{SPINEPS_DIR}/sub-*_seg-vert_msk.nii.gz")})
    rows = {p[0]: {"sp": [], "cc": []} for p in PAIRS}

    header = f"{'subject':<18}" + "".join(f"{p[0] + ' SP/CC':>15}" for p in PAIRS)
    print(header)
    print("-" * len(header))
    for sub in subs:
        spine_f = f"{SPINEPS_DIR}/{sub}_mod-T2w_seg-spine_msk.nii.gz"
        vert_f = f"{SPINEPS_DIR}/{sub}_mod-T2w_seg-vert_msk.nii.gz"
        tss_f = f"{TSS_DIR}/{sub}_T2w_step2.nii.gz"
        if not (os.path.exists(spine_f) and os.path.exists(vert_f) and os.path.exists(tss_f)):
            print(f"{sub:<18}  (missing a mask -> skipped)")
            continue
        S, ax_s, z_s = _load(spine_f)
        V, _, _ = _load(vert_f)
        T, ax_t, z_t = _load(tss_f)
        cells = []
        for name, sp_t, sp_b, cc_t, cc_b in PAIRS:
            sp = spineps_cobb_angle(S, V, ax_s, z_s, sp_t, sp_b)
            cc = cobb_angle(T, ax_t, z_t, cc_t, cc_b)
            rows[name]["sp"].append(sp)
            rows[name]["cc"].append(cc)
            cells.append(f"{_fmt(sp)}/{_fmt(cc)}")
        print(f"{sub:<18}" + "".join(f"{c:>15}" for c in cells))

    print("\n=== summary: mean +/- SD over measurable levels (coverage = measurable/total) ===")
    print("(lordosis-positive; supine MRI, no GT -> read spread + coverage, not absolute accuracy)")
    for name, *_ in PAIRS:
        print(f"  {name:<7} SPINEPS  {_stat(rows[name]['sp'])}     canal-cut  {_stat(rows[name]['cc'])}")


if __name__ == "__main__":
    main()
