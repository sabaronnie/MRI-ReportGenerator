"""Group 5.1 — SCIseg healthy-specificity scorer.

SCIseg (sct_deepseg lesion_sci_t2) is the adopted myelomalacia engine. Its sensitivity rests
on its published validation (Naga Karthik 2024, Radiology AI, PMC11065035); what we validate
for OUR pipeline is SPECIFICITY on healthy cords -- "on healthy, it flags nothing" (Andrew's
detector-accuracy criterion). This module scores SCIseg lesion masks by lesion burden and
reports the cohort false-positive rate.

Lesion volume is anisotropy-safe (voxel count * product of the affine zooms, in mm). A tunable
minimum lesion volume (`min_lesion_mm3`) keeps tiny single-voxel specks from counting as a
flag -- the specificity analogue of the 5.2 screen's z policy; sweep it to report the FP/volume
trade-off. Pure numpy + scipy: local, no GPU (SCIseg itself runs on Colab).
"""
import numpy as np
from scipy import ndimage


def lesion_burden(lesion_mask, zooms):
    """Lesion burden of a SCIseg lesion mask: voxel count, total mm^3, largest-component mm^3.

    lesion_mask : 3D boolean (or 0/1) array -- SCIseg `*_lesion_seg.nii.gz`.
    zooms       : voxel spacing (mm) from the image header (anisotropy-safe).
    """
    m = np.asarray(lesion_mask, dtype=bool)
    voxel_mm3 = float(np.prod([float(z) for z in zooms[:3]]))
    voxels = int(m.sum())
    if voxels == 0:
        return {"voxels": 0, "volume_mm3": 0.0, "largest_component_mm3": 0.0}
    lab, n = ndimage.label(m)
    comp_voxels = np.bincount(lab.ravel())[1:]            # drop background
    return {
        "voxels": voxels,
        "volume_mm3": float(voxels * voxel_mm3),
        "largest_component_mm3": float(comp_voxels.max() * voxel_mm3),
    }


def healthy_specificity(cases, min_lesion_mm3=0.0):
    """False-positive rate of SCIseg lesion detection across HEALTHY cords.

    cases : list of (case_id, lesion_mask, zooms).
    min_lesion_mm3 : a case is flagged when its LARGEST lesion component exceeds this volume.
                     Default 0.0 -> any lesion voxel flags (strictest specificity test); raise
                     it to a clinical floor to ignore sub-clinical specks.

    Returns {"per_case":[{case_id, voxels, volume_mm3, largest_component_mm3, flagged}],
             "n", "n_flagged", "fp_rate"}.  On truly healthy input fp_rate is the false-positive
             rate; the goal is ~0.
    """
    per_case = []
    for case_id, lesion_mask, zooms in cases:
        b = lesion_burden(lesion_mask, zooms)
        flagged = bool(b["largest_component_mm3"] > min_lesion_mm3)
        per_case.append({"case_id": case_id, **b, "flagged": flagged})
    n = len(per_case)
    n_flagged = sum(c["flagged"] for c in per_case)
    return {
        "per_case": per_case,
        "n": n,
        "n_flagged": int(n_flagged),
        "fp_rate": (n_flagged / n) if n else float("nan"),
    }
