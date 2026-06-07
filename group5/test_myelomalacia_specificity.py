"""Group 5.1 — SCIseg healthy-specificity check.

We ADOPTED SCIseg (sct_deepseg lesion_sci_t2) as the myelomalacia engine. Its sensitivity
rests on its published validation; what WE must show for our pipeline is SPECIFICITY on
healthy cords -- Andrew's detector-accuracy criterion: "on healthy, it flags nothing."

This scores SCIseg LESION masks (run on the 12 healthy Spine-Generic cords) by lesion burden
(voxel count + mm^3, anisotropy-safe via the affine zooms) and reports the cohort
false-positive rate. A clinically-meaningful minimum lesion volume is a tunable parameter
(tiny single-voxel specks should not count as a lesion flag), mirroring the 5.2 screen.
"""
import numpy as np

from myelomalacia_specificity import lesion_burden, healthy_specificity


def test_lesion_burden_empty_mask_is_zero():
    b = lesion_burden(np.zeros((10, 10, 10), bool), zooms=(0.8, 0.8, 0.8))
    assert b["voxels"] == 0
    assert b["volume_mm3"] == 0.0
    assert b["largest_component_mm3"] == 0.0


def test_lesion_burden_volume_is_anisotropy_safe():
    # 2x3x4 = 24 voxels; anisotropic spacing -> volume = 24 * (0.5*0.5*4.0) = 24 mm^3
    m = np.zeros((8, 8, 8), bool)
    m[1:3, 1:4, 1:5] = True
    b = lesion_burden(m, zooms=(0.5, 0.5, 4.0))
    assert b["voxels"] == 24
    assert abs(b["volume_mm3"] - 24 * (0.5 * 0.5 * 4.0)) < 1e-9


def test_lesion_burden_largest_component_ignores_smaller_speck():
    # two disconnected blobs: largest_component_mm3 reflects only the bigger one
    m = np.zeros((20, 20, 20), bool)
    m[2:4, 2:4, 2:4] = True          # 8-voxel speck
    m[10:14, 10:14, 10:14] = True    # 64-voxel lesion
    b = lesion_burden(m, zooms=(1.0, 1.0, 1.0))
    assert b["voxels"] == 8 + 64
    assert b["largest_component_mm3"] == 64.0


def test_healthy_specificity_all_empty_is_zero_fp():
    # the success criterion: SCIseg flags NOTHING on healthy -> FP rate 0
    cases = [(f"sub{i}", np.zeros((10, 10, 10), bool), (0.8, 0.8, 0.8)) for i in range(12)]
    r = healthy_specificity(cases)
    assert r["n"] == 12
    assert r["n_flagged"] == 0
    assert r["fp_rate"] == 0.0
    assert all(c["flagged"] is False for c in r["per_case"])


def test_healthy_specificity_min_volume_threshold_filters_specks():
    big = np.zeros((20, 20, 20), bool); big[5:10, 5:10, 5:10] = True   # 125 mm^3 @ iso 1mm
    speck = np.zeros((20, 20, 20), bool); speck[5:6, 5:6, 5:7] = True   # 2 mm^3
    cases = [("big", big, (1.0, 1.0, 1.0)), ("speck", speck, (1.0, 1.0, 1.0))]
    # with a 10 mm^3 clinical floor: big flags, speck does not -> FP rate 1/2
    r = healthy_specificity(cases, min_lesion_mm3=10.0)
    flagged = {c["case_id"]: c["flagged"] for c in r["per_case"]}
    assert flagged["big"] is True
    assert flagged["speck"] is False
    assert r["fp_rate"] == 0.5


def test_healthy_specificity_reports_per_case_burden():
    m = np.zeros((20, 20, 20), bool); m[5:10, 5:10, 5:10] = True
    r = healthy_specificity([("c1", m, (1.0, 1.0, 1.0))])
    pc = r["per_case"][0]
    assert pc["case_id"] == "c1"
    assert pc["volume_mm3"] == 125.0
    assert pc["largest_component_mm3"] == 125.0
