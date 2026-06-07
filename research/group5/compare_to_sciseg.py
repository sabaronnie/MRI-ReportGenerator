"""Batch validation: our detectors vs SCIseg lesion masks (silver-standard reference).

Run after unzipping the Colab masks into ~/dev/group5-proto/out/. For each case we
have a local T2 (data/duke_batch/) + SCIseg cord + lesion masks (out/).
  - positives  = cases where SCIseg found a lesion
  - sensitivity = of positives, how many our detector flagged a nearby level
  - negatives  = no SCIseg lesion -> our flags there are false positives

Compares TWO detectors:
  - median  (detect_cord_signal_abnormality): per-level cord median vs neighbors
  - bright  (detect_focal_hyperintensity):    per-level cord p90 vs cord baseline

Lightweight (numpy), local. Usage: python compare_to_sciseg.py [out_dir] [t2_dir]
"""
import glob
import os
import sys

import nibabel as nib
import nibabel.processing as nibproc
import numpy as np

from .myelomalacia import detect_cord_signal_abnormality, detect_focal_hyperintensity

TOL = 3


def si_axis(affine):
    for i, c in enumerate(nib.aff2axcodes(affine)):
        if c in ("S", "I"):
            return i
    raise ValueError("no S/I axis")


def to_grid(src, ref):
    same = (src.shape == ref.shape
            and nib.aff2axcodes(src.affine) == nib.aff2axcodes(ref.affine))
    return src if same else nibproc.resample_from_to(src, ref, order=0)


def levels_of(mask_bool, axis):
    return {L for L in range(mask_bool.shape[axis]) if mask_bool.take(L, axis=axis).any()}


def find_one(patterns):
    for p in patterns:
        hits = glob.glob(p)
        if hits:
            return hits[0]
    return None


def caught(ref_levels, flag_levels):
    return any(abs(L - o) <= TOL for L in ref_levels for o in flag_levels)


def main(out_dir, t2_dir):
    rows = []
    agg = {"median": {"pos_caught": 0, "fp": 0}, "bright": {"pos_caught": 0, "fp": 0}}
    n_pos = n_neg = 0

    for t2 in sorted(glob.glob(f"{t2_dir}/*.nii.gz")):
        base = os.path.basename(t2)[:-7]
        lesf = find_one([f"{out_dir}/{base}*lesion*.nii.gz"])
        cordf = find_one([f"{out_dir}/{base}*sc_seg*.nii.gz", f"{out_dir}/{base}*_seg.nii.gz"])
        if not lesf or not cordf:
            continue
        img = nib.load(t2)
        mri = img.get_fdata()
        axis = si_axis(img.affine)
        cordb = to_grid(nib.load(cordf), img).get_fdata() > 0.5
        lesb = to_grid(nib.load(lesf), img).get_fdata() > 0.5

        ref = levels_of(lesb, axis)
        med = {f["level"] for f in detect_cord_signal_abnormality(
            mri, cordb.astype(int), level_axis=axis, threshold_ratio=1.3)}
        bri = {f["level"] for f in detect_focal_hyperintensity(
            mri, cordb.astype(int), level_axis=axis, percentile=90, threshold_ratio=1.4)}

        if ref:
            n_pos += 1
            cm, cb = caught(ref, med), caught(ref, bri)
            agg["median"]["pos_caught"] += cm
            agg["bright"]["pos_caught"] += cb
            rows.append((base, "POS", len(ref), "caught" if cm else "MISS",
                         "caught" if cb else "MISS"))
        else:
            n_neg += 1
            agg["median"]["fp"] += len(med)
            agg["bright"]["fp"] += len(bri)
            rows.append((base, "neg", 0, f"{len(med)}fp", f"{len(bri)}fp"))

    print(f"cases compared: {len(rows)}  |  SCIseg positives: {n_pos}  |  negatives: {n_neg}\n")
    for name in ("median", "bright"):
        sens = agg[name]["pos_caught"] / n_pos if n_pos else float("nan")
        fpc = agg[name]["fp"] / n_neg if n_neg else float("nan")
        print(f"{name:7s}: sensitivity {agg[name]['pos_caught']}/{n_pos} = {sens:.2f}  |  "
              f"false-positive levels/negative = {fpc:.1f}")
    print(f"\n{'case':36s} {'truth':5s} {'median':7s} {'bright':7s}")
    for base, lab, nref, m, b in rows:
        tag = f"{lab}({nref})" if lab == "POS" else lab
        print(f"  {base[:34]:34s} {tag:6s} {m:7s} {b:7s}")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "/Users/andrew/dev/group5-proto/out"
    t2_dir = sys.argv[2] if len(sys.argv) > 2 else "/Users/andrew/dev/group5-proto/data/duke_batch"
    main(out_dir, t2_dir)
