"""Group 5.1 — run the SCIseg healthy-specificity check on a folder of SCIseg lesion masks.

Input: a directory of SCIseg `*_lesion_seg.nii.gz` masks (produced on Colab by
colab/group5/colab_segment_duke.ipynb / sct_deepseg lesion_sci_t2). For each case it reports lesion burden
(voxels, mm^3, largest component) and the cohort false-positive rate at a strict (any voxel)
and a clinical-floor threshold. On the 12 HEALTHY Spine-Generic cords the goal is FP rate ~0
("on healthy, flags nothing").

Pure numpy + nibabel + scipy: local. SCIseg itself runs on Colab GPU (CPU inference is banned).

Usage:  python run_sciseg_specificity.py <dir_of_lesion_masks> [min_lesion_mm3]
"""
import glob
import sys

import nibabel as nib
import numpy as np

from services.measurements.group5.myelomalacia_specificity import healthy_specificity

# Clinical-floor default: ignore sub-clinical specks below this lesion volume when flagging.
# A tunable specificity policy (analogous to the 5.2 screen z); not a clinical claim.
DEFAULT_MIN_LESION_MM3 = 5.0


def load_cases(lesion_dir):
    cases = []
    for f in sorted(glob.glob(f"{lesion_dir}/*lesion*.nii.gz")):
        img = nib.load(f)
        mask = np.asarray(img.dataobj) > 0.5
        zooms = img.header.get_zooms()[:3]
        case_id = f.split("/")[-1].replace(".nii.gz", "")
        cases.append((case_id, mask, zooms))
    return cases


def main(lesion_dir, min_lesion_mm3):
    cases = load_cases(lesion_dir)
    if not cases:
        print(f"No *lesion*.nii.gz masks found in {lesion_dir}")
        return
    strict = healthy_specificity(cases, min_lesion_mm3=0.0)
    floor = healthy_specificity(cases, min_lesion_mm3=min_lesion_mm3)
    floor_flag = {c["case_id"]: c["flagged"] for c in floor["per_case"]}

    print(f"=== SCIseg lesion burden on {len(cases)} case(s) in {lesion_dir}")
    print(f"    {'case':40s} {'voxels':>7} {'vol mm3':>9} {'largest mm3':>11}  flag(floor)")
    for c in strict["per_case"]:
        print(f"    {c['case_id'][:40]:40s} {c['voxels']:>7} {c['volume_mm3']:>9.1f} "
              f"{c['largest_component_mm3']:>11.1f}  {'FLAG' if floor_flag[c['case_id']] else '.'}")
    print(f"\n    FP rate @ strict (any lesion voxel):      "
          f"{strict['n_flagged']}/{strict['n']} = {100*strict['fp_rate']:.0f}%")
    print(f"    FP rate @ floor (largest > {min_lesion_mm3:g} mm3): "
          f"{floor['n_flagged']}/{floor['n']} = {100*floor['fp_rate']:.0f}%")
    print("    (on HEALTHY cords the goal is ~0%; on patient cords nonzero is expected/correct)")


if __name__ == "__main__":
    lesion_dir = sys.argv[1] if len(sys.argv) > 1 else "out"
    min_mm3 = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MIN_LESION_MM3
    main(lesion_dir, min_mm3)
