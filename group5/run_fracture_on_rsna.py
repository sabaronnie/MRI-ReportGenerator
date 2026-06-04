"""Validate the 5.2 fracture detector against the RSNA-2022 Cervical Spine Fracture dataset.

RSNA-2022 (Kaggle / Radiology:AI 2023) ships, for a subset of studies, BOTH:
  - per-vertebra binary fracture labels in train.csv (columns C1..C7, plus patient_overall)
  - pixel-level vertebral SEGMENTATION masks as NIfTI (segmentations/<StudyUID>.nii),
    where voxel value 1..7 == C1..C7 (8..19 == T1..T12).

For each study that has BOTH a segmentation and a label row, this:
  1. loads the segmentation, derives axes from its orientation,
  2. for each cervical body C3..C7 (labels 3..7; C1/C2 excluded per the cervical caveat),
     isolates the vertebral BODY and measures 6-point Ha/Hm/Hp -> classify_genant -> flag,
  3. pairs (predicted flag, RSNA truth label) and reports sensitivity/specificity.

This gives a REAL fracture-flag accuracy number at scale (vs only 3 Duke MRI cases). It is
CT, so it validates the modality-independent Genant SHAPE logic, not MRI signal. Pure
numpy/nibabel/scipy -- lightweight, LOCAL, no GPU.

Usage:
  python run_fracture_on_rsna.py <RSNA_DIR>
    where RSNA_DIR contains  train.csv  and  segmentations/  (*.nii or *.nii.gz)
  python run_fracture_on_rsna.py <RSNA_DIR> --seg-dir <segs> --csv <labels.csv>
"""
import argparse
import csv
import glob
import os

import nibabel as nib
import numpy as np

from vertebral_fracture import classify_genant, fracture_confusion, measure_vertebra

# RSNA segmentation voxel value -> cervical level. C1=1..C7=7; measure C3-C7, exclude C1/C2.
RSNA_LEVEL = {3: "C3", 4: "C4", 5: "C5", 6: "C6", 7: "C7"}
EXCLUDE = {1, 2}                       # C1/C2 (atlas/odontoid) — not Genant-measurable


def parse_rsna_labels(csv_path):
    """train.csv -> {StudyInstanceUID: {1:0/1, ..., 7:0/1}} using the C1..C7 columns."""
    out = {}
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            uid = row.get("StudyInstanceUID") or row.get("study_id") or ""
            if not uid:
                continue
            out[uid] = {lvl: int(float(row[f"C{lvl}"])) for lvl in range(1, 8) if f"C{lvl}" in row}
    return out


def study_uid_from_path(path):
    base = os.path.basename(path)
    for ext in (".nii.gz", ".nii"):
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


def run(seg_dir, csv_path, verbose=True):
    labels = parse_rsna_labels(csv_path)
    seg_files = sorted(glob.glob(os.path.join(seg_dir, "*.nii*")))
    pairs, per_level = [], {v: [] for v in RSNA_LEVEL}
    matched = 0

    for f in seg_files:
        uid = study_uid_from_path(f)
        if uid not in labels:
            continue
        matched += 1
        seg = nib.load(f)
        d = np.rint(np.asarray(seg.dataobj)).astype(int)
        axcodes = nib.aff2axcodes(seg.affine)
        zooms = seg.header.get_zooms()[:3]
        truth = labels[uid]
        for lvl, name in RSNA_LEVEL.items():
            if lvl not in truth or not np.any(d == lvl):
                continue
            h = measure_vertebra(d == lvl, axcodes, zooms)          # isolate_body=True by default
            g = classify_genant(h)
            pred = g["grade"] >= 1
            t = bool(truth[lvl])
            pairs.append((pred, t))
            per_level[lvl].append((pred, t))
            if verbose and (pred or t):
                mark = "TP" if (pred and t) else "FP" if pred else "FN"
                print(f"  {uid[:18]}… {name}: {g['type']} grade {g['grade']} "
                      f"(Ha/Hp={h['Ha']/h['Hp']:.2f}) | truth={'fx' if t else 'ok'} -> {mark}")

    print(f"\nMatched {matched} studies with both segmentation + labels; "
          f"{len(pairs)} cervical vertebrae scored (C3-C7).")
    if not pairs:
        print("Nothing scored — check that seg filenames match StudyInstanceUID and labels exist.")
        return None

    c = fracture_confusion(pairs)
    sens = "n/a" if c["sensitivity"] is None else f"{c['sensitivity']*100:.1f}%"
    spec = "n/a" if c["specificity"] is None else f"{c['specificity']*100:.1f}%"
    print(f"\n=== 5.2 FRACTURE-FLAG VALIDATION vs RSNA-2022 expert labels ===")
    print(f"  TP={c['tp']} FP={c['fp']} TN={c['tn']} FN={c['fn']}  (n={c['n']})")
    print(f"  Sensitivity (fractures caught) = {sens}")
    print(f"  Specificity (healthy left alone) = {spec}")
    print(f"  Per level:")
    for lvl, name in RSNA_LEVEL.items():
        cl = fracture_confusion(per_level[lvl])
        if cl["n"]:
            s = "n/a" if cl["sensitivity"] is None else f"{cl['sensitivity']*100:.0f}%"
            print(f"    {name}: n={cl['n']:3d}  sens={s:>4}  (TP{cl['tp']} FP{cl['fp']} TN{cl['tn']} FN{cl['fn']})")
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rsna_dir", help="dir containing train.csv and segmentations/")
    ap.add_argument("--seg-dir", default=None)
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    seg_dir = a.seg_dir or os.path.join(a.rsna_dir, "segmentations")
    csv_path = a.csv or os.path.join(a.rsna_dir, "train.csv")
    run(seg_dir, csv_path)


if __name__ == "__main__":
    main()
