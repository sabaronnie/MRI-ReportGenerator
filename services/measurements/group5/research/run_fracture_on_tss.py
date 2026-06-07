"""Run 5.2 fracture morphometry on a TotalSpineSeg FULL-mode segmentation.

Input: a TSS `step2_output` .nii.gz (per-vertebra CANONICAL labels) -- file or folder.
For each cervical vertebra it measures 6-point Ha/Hm/Hp on that vertebra's own
mid-sagittal slice, classifies Genant-style deformity, and compares the C3-C7 height
distribution to published cervical norms. Pure numpy + nibabel: lightweight, LOCAL,
no GPU/nnU-Net (segmentation itself runs on Colab GPU -- see colab/group5/colab_segment_tss_fracture.ipynb).

TSS canonical labels (from inference.py iterative_label):
  cord=1, canal=2, C1=11 C2=12 C3=13 C4=14 C5=15 C6=16 C7=17, T1=21.., sacrum=50, discs 63-100.
Cervical caveat: C1/C2 (atlas/odontoid) are structurally unique -> measured but EXCLUDED
from the norm comparison; thresholds are thoracolumbar-derived (refine to cervical later).

Usage:  python run_fracture_on_tss.py <step2_output.nii.gz | folder> [more ...]
"""
import glob
import sys

import nibabel as nib
import numpy as np

from ..vertebral_fracture import (
    COHORT_HAHP_MEAN,
    COHORT_HAHP_SD,
    cervical_deformity_flag,
    classify_genant,
    extract_body_via_canal,
    measure_vertebra,
)

CERVICAL = {11: "C1", 12: "C2", 13: "C3", 14: "C4", 15: "C5", 16: "C6", 17: "C7"}
CANAL_LABEL = 2                                     # TSS spinal-canal label (for body/arch cut)
EXCLUDE = {11, 12}                                  # C1/C2 excluded from norm comparison
# Cervical Ha/Hp SCREEN norm = OUR measured Spine-Generic HEALTHY cohort (0.94 +/- 0.13),
# single-sourced from vertebral_fracture. This REPLACES the debunked 0.97 +/- 0.02 phantom
# (which traced only to Sorci 2024, an osteoporotic cohort). The healthy range is supported by
# triangulation -- NOT a like-for-like MRI comparator, none exists: Tan 2004 (PMC3476578),
# Lee 2012 (PMC3393857), Kaur 2025 (cadaver, posterior>anterior ~0.90). VB SI height vs AP
# depth reconciliation: Chen 2013 (PMC3859485) + Nell 2019 (PMC6764695) (height ~10-14mm =
# SI axis we measure; ~15-18mm = AP depth, a DIFFERENT dimension).
NORM_RATIO, NORM_RATIO_SD = COHORT_HAHP_MEAN, COHORT_HAHP_SD   # 0.94 +/- 0.13 (healthy cohort)
NORM_HT, NORM_HT_SD = 11.4, 1.1                     # cervical VB SI height (mm)
SCREEN_Z = 2.0                                      # screen flags Ha/Hp < mean - z*sd (~0.68);
                                                    # specificity policy, a team/AUBMC decision


def resolve_inputs(args):
    if not args:
        # default: any step2_output produced under the proto dir
        return sorted(glob.glob("tss_*/**/step2_output/*.nii.gz", recursive=True))
    files = []
    for a in args:
        files += sorted(glob.glob(f"{a}/*.nii.gz")) if not a.endswith(".nii.gz") else [a]
    return files


def run_one(path):
    seg = nib.load(path)
    d = np.asarray(seg.dataobj)
    d = np.rint(d).astype(int)
    axcodes = nib.aff2axcodes(seg.affine)
    zooms = seg.header.get_zooms()[:3]
    print(f"\n=== {path}")
    print(f"    shape {seg.shape}  axcodes {axcodes}  zooms "
          f"{tuple(round(float(z), 2) for z in zooms)} mm")

    present = [lbl for lbl in CERVICAL if np.any(d == lbl)]
    if not present:
        print("    no cervical vertebra labels (11-17) found -- is this a step2_output?")
        return [], []
    present.sort()                                  # C1 -> C7

    canal = d == CANAL_LABEL                         # TSS canal (label 2) -> body/arch cut
    if not canal.any():
        print("    WARNING: no canal label (2) -- falling back to morphological body isolation "
              "(less accurate; expect posterior bias).")

    rows = []
    for lbl in present:
        vert = d == lbl
        # Anatomical body isolation: keep the part anterior to the spinal canal, then measure.
        body = extract_body_via_canal(vert, canal, axcodes) if canal.any() else vert
        h = measure_vertebra(body, axcodes, zooms, isolate_body=not canal.any())
        rows.append((lbl, h))

    # crush reference = median posterior height of the C3-C7 bodies we actually measured
    body_hp = [h["Hp"] for lbl, h in rows if lbl not in EXCLUDE and h["Hp"] > 0]
    ref_post = float(np.median(body_hp)) if body_hp else None

    ratios, heights, flags = [], [], []
    for lbl, h in rows:
        g = classify_genant(h, ref_post=ref_post)          # standard medical Genant grade
        r = h["Ha"] / h["Hp"] if h["Hp"] else float("nan")
        # The SCREEN decision uses the data-driven cervical flag (not the over-flagging Genant
        # 20% rule, which is thoracolumbar-derived). z-score shown so borderlines stay visible.
        scr = cervical_deformity_flag(r, z=SCREEN_Z) if not np.isnan(r) else {"flagged": False, "zscore": float("nan")}
        flag = "  <-- SCREEN FLAG (physician review)" if scr["flagged"] else ""
        excl = "  (excluded from norms)" if lbl in EXCLUDE else ""
        print(f"    {CERVICAL[lbl]:>2}: Ha={h['Ha']:5.1f} Hm={h['Hm']:5.1f} Hp={h['Hp']:5.1f} mm"
              f" | Ha/Hp={r:4.2f} (z={scr['zscore']:+4.1f}) | genant {g['type']:9s} g{g['grade']}"
              f"{flag}{excl}")
        if lbl not in EXCLUDE and not np.isnan(r):
            ratios.append(r)
            heights.append(h["Hp"])
            flags.append(scr["flagged"])
    return ratios, heights, flags


def main():
    files = resolve_inputs(sys.argv[1:])
    if not files:
        print("No segmentation files found. Pass TSS step2_output .nii.gz path(s).")
        return
    all_ratios, all_heights, all_flags = [], [], []
    for f in files:
        r, h, fl = run_one(f)
        all_ratios += r
        all_heights += h
        all_flags += fl

    if all_ratios:
        rr, hh, ff = np.array(all_ratios), np.array(all_heights), np.array(all_flags)
        n_flag = int(ff.sum())
        print(f"\n=== VS CERVICAL NORMS (C3-C7, n={len(rr)} vertebrae across {len(files)} case(s))")
        print(f"    Ha/Hp     measured median {np.median(rr):.2f}  "
              f"(healthy-cohort norm {NORM_RATIO}+/-{NORM_RATIO_SD})")
        print(f"    VB height measured median {np.median(hh):.1f} mm (norm {NORM_HT}+/-{NORM_HT_SD} mm)")
        print(f"    Ha/Hp range [{rr.min():.2f}, {rr.max():.2f}] | "
              f"height range [{hh.min():.1f}, {hh.max():.1f}] mm")
        print(f"    SCREEN flag rate (z={SCREEN_Z}, threshold Ha/Hp<{NORM_RATIO - SCREEN_Z*NORM_RATIO_SD:.2f}): "
              f"{n_flag}/{len(rr)} = {100*n_flag/len(rr):.0f}%  "
              f"(on HEALTHY input this is the false-positive rate)")


if __name__ == "__main__":
    main()
