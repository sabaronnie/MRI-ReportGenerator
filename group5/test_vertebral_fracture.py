"""Group 5.2 — vertebral fracture detection via 6-point morphometry (Genant-style).

Measures anterior (Ha), middle (Hm), posterior (Hp) vertebral-body heights from a
single-vertebra mask on the mid-sagittal slice, then grades deformity by % height
loss (Genant et al. 1993, JBMR).

Cervical caveat: Genant is validated for T4-L4, not cervical; C1/C2 are excluded by
the caller; normal cervical Ha/Hp ~= 0.97, so the 20% loss rule clears normal easily.
"""
import numpy as np

from vertebral_fracture import (
    heights_from_sagittal_mask,
    classify_genant,
    vertebra_axes_from_orientation,
    mid_sagittal_index,
    measure_vertebra,
    extract_vertebral_body,
    extract_body_via_canal,
    endplate_line_heights,
    fracture_confusion,
)


def _wedge_volume_psr():
    """3D single-vertebra mask in P-S-R axes: anterior (low AP) shorter than posterior.
    6..10 voxels tall across AP, spanning 3 mid L-R slices."""
    vol = np.zeros((30, 16, 5), dtype=bool)
    for ap in range(6, 24):
        height = int(round(6 + (ap - 6) / 17.0 * 4))   # 6 (ant) .. 10 (post)
        vol[ap, 1:1 + height, 1:4] = True
    return vol


def test_rectangular_vertebra_has_uniform_heights():
    # 2D mid-sagittal mask: axis 0 = AP, axis 1 = SI. A rectangle -> Ha = Hm = Hp.
    mask = np.zeros((20, 12), dtype=bool)
    mask[5:15, 2:9] = True              # AP 5-14 (width 10), SI 2-8 (height 7 voxels)
    h = heights_from_sagittal_mask(mask, si_spacing=1.0)
    assert h["Ha"] == h["Hm"] == h["Hp"] == 7.0


def test_wedge_anterior_height_reduced_and_classified():
    # anterior (low AP) collapsed vs posterior (high AP) -> wedge deformity
    mask = np.zeros((30, 16), dtype=bool)
    for ap in range(6, 24):
        frac = (ap - 6) / 17.0              # 0 at anterior(low) -> 1 at posterior(high)
        height = int(round(6 + frac * 4))   # 6 voxels (ant) .. 10 (post)
        mask[ap, 1:1 + height] = True
    h = heights_from_sagittal_mask(mask, si_spacing=1.0, anterior="low")
    assert h["Ha"] < h["Hp"]               # anterior shorter
    g = classify_genant(h)
    assert g["type"] == "wedge"
    assert g["grade"] >= 1


def test_normal_vertebra_not_flagged():
    mask = np.zeros((20, 12), dtype=bool)
    mask[5:15, 2:9] = True                  # uniform -> no deformity
    g = classify_genant(heights_from_sagittal_mask(mask, si_spacing=1.0))
    assert g["grade"] == 0
    assert g["type"] == "normal"


def test_si_spacing_scales_height_to_mm():
    mask = np.zeros((20, 12), dtype=bool)
    mask[5:15, 2:9] = True                  # 7 voxels tall
    h = heights_from_sagittal_mask(mask, si_spacing=2.0)
    assert h["Hp"] == 14.0                  # 7 voxels * 2 mm


# --- orientation handling (TSS reorients to LPI; the input was P-S-R) ---------
# nibabel axcodes name the END each axis increases toward, so 'P' on an axis means
# index grows toward Posterior -> anterior is the LOW index of that axis.

def test_axes_from_input_PSR_orientation():
    ap, si, lr, anterior = vertebra_axes_from_orientation(("P", "S", "R"))
    assert (ap, si, lr) == (0, 1, 2)
    assert anterior == "low"


def test_axes_from_tss_LPI_orientation():
    ap, si, lr, anterior = vertebra_axes_from_orientation(("L", "P", "I"))
    assert (ap, si, lr) == (1, 2, 0)        # AP=axis1, SI=axis2, LR=axis0
    assert anterior == "low"


def test_axes_anterior_is_high_when_axis_points_anterior():
    ap, si, lr, anterior = vertebra_axes_from_orientation(("A", "S", "L"))
    assert ap == 0
    assert anterior == "high"


def test_axes_rejects_incomplete_orientation():
    import pytest
    with pytest.raises(ValueError):
        vertebra_axes_from_orientation(("A", "S", "S"))   # no L/R axis


def test_mid_sagittal_index_picks_largest_area_slice():
    # LR axis = 2; slice index 3 holds the most voxels -> the body's mid-sagittal slice.
    mask = np.zeros((6, 6, 5), dtype=bool)
    mask[1:3, 1:3, 1] = True                # 4 voxels at lr=1 (parasagittal)
    mask[0:5, 0:5, 3] = True                # 25 voxels at lr=3 (mid-body)
    assert mid_sagittal_index(mask, lr_axis=2) == 3


def test_measure_vertebra_wedge_in_PSR_volume():
    h = measure_vertebra(_wedge_volume_psr(), ("P", "S", "R"), zooms=(0.43, 0.5, 4.0))
    assert h["Ha"] < h["Hp"]                            # anterior wall collapsed
    g = classify_genant(h)
    assert g["type"] == "wedge" and g["grade"] >= 1     # detected as a wedge deformity


def test_measure_vertebra_is_orientation_invariant_LPI():
    # Same physical wedge in two frames (acquired P-S-R vs TSS's LPI) must measure the same.
    psr = measure_vertebra(_wedge_volume_psr(), ("P", "S", "R"), zooms=(0.43, 0.5, 4.0))
    vol_lpi = np.transpose(_wedge_volume_psr(), (2, 0, 1))
    lpi = measure_vertebra(vol_lpi, ("L", "P", "I"), zooms=(4.0, 0.43, 0.5))
    assert lpi["Ha"] < lpi["Hp"]
    assert abs(lpi["Ha"] - psr["Ha"]) <= 0.5            # orientation-invariant: same result
    assert abs(lpi["Hp"] - psr["Hp"]) <= 0.5


# --- vertebral-body isolation ------------------------------------------------
# RSNA & TSS masks are WHOLE-vertebra (body + posterior arch/spinous process).
# Genant morphometry needs only the BODY (anterior block). On the mid-sagittal slice
# the body (anterior) and spinous process (posterior) are separated by the canal gap,
# so the body is the connected component owning the anterior-most voxel.

def _body_plus_spinous_psr():
    """2D mid-sagittal slice, AP=axis0 (anterior=low). Body anterior, spinous posterior,
    separated by an AP gap (the spinal canal). Body is 8 voxels tall; spinous taller."""
    s = np.zeros((24, 16), dtype=bool)
    s[2:12, 3:11] = True       # BODY: AP 2-11 (anterior), SI 3-10 (8 voxels tall)
    s[16:22, 1:14] = True      # SPINOUS PROCESS: AP 16-21 (posterior), SI 1-13 (taller)
    return s


def test_extract_vertebral_body_drops_posterior_process():
    body = extract_vertebral_body(_body_plus_spinous_psr(), ap_axis=0, anterior="low")
    assert body[2:12, 3:11].all()          # body kept
    assert not body[16:22, :].any()        # spinous process removed


def test_extract_vertebral_body_anterior_high_orientation():
    # mirror the slice so the body is at HIGH AP indices
    s = _body_plus_spinous_psr()[::-1, :]
    body = extract_vertebral_body(s, ap_axis=0, anterior="high")
    assert not body[0:8, :].any()          # spinous (now low AP) removed
    assert body.sum() == 10 * 8            # only the 10x8 body remains


def test_extract_vertebral_body_single_component_unchanged():
    s = np.zeros((20, 12), dtype=bool)
    s[5:15, 2:9] = True                    # clean body only, one component
    body = extract_vertebral_body(s, ap_axis=0, anterior="low")
    assert np.array_equal(body, s)


def _fused_body_spinous_psr():
    """ONE connected blob (real-anatomy failure): body --thin pedicle neck-- spinous.
    AP=axis0 anterior=low. Body uniform 8 tall; spinous projects inferiorly, taller."""
    s = np.zeros((34, 26), dtype=bool)
    s[2:13, 3:11] = True       # BODY: AP 2-12 (anterior), SI 3-10 (8 tall), uniform
    s[12:15, 6:9] = True       # PEDICLE NECK: AP 12-14, SI 6-8 (thin, 3 tall)
    s[14:30, 9:23] = True      # SPINOUS: AP 14-29 (posterior), SI 9-22 (14 tall, inferior)
    return s


def test_extract_vertebral_body_severs_fused_spinous():
    s = _fused_body_spinous_psr()
    from scipy import ndimage
    assert ndimage.label(s)[1] == 1                 # it IS one connected blob (the bug trigger)
    body = extract_vertebral_body(s, ap_axis=0, anterior="low")
    assert not body[15:30, :].any()                 # spinous severed and dropped
    assert body[2:13, 3:11].sum() >= 0.8 * (11 * 8) # body substantially recovered


def test_extract_body_via_canal_cuts_at_canal_anterior_face():
    # TSS gives whole-vertebra + spinal CANAL. The body is everything anterior to the
    # canal. Synthetic (P-S-R: AP=axis0 anterior=low, SI=axis1, LR=axis2):
    #   vertebra = body (AP 2-12) + posterior arch (AP 18-28), one label, both present
    #   canal    = AP 13-17 (between body and arch)  ->  body must keep only AP<13.
    vert = np.zeros((32, 22, 6), dtype=bool)
    vert[2:13, 4:16, 1:5] = True        # BODY (anterior), 12 voxels tall, uniform
    vert[18:29, 8:13, 1:5] = True       # posterior ARCH (would fake a wedge if kept)
    canal = np.zeros((32, 22, 6), dtype=bool)
    canal[13:18, 4:16, 1:5] = True      # spinal canal, posterior to the body
    body = extract_body_via_canal(vert, canal, ("P", "S", "R"))
    assert not body[13:, :, :].any()    # everything at/behind the canal removed
    assert body[2:13, 4:16, 1:5].all()  # body fully retained
    h = measure_vertebra(body, ("P", "S", "R"), zooms=(0.43, 1.0, 4.0))
    assert classify_genant(h)["grade"] == 0          # clean uniform body -> not flagged
    assert abs(h["Ha"] - h["Hp"]) <= 1.0             # and Ha ~= Hp (no false wedge)


def test_extract_body_via_canal_no_canal_returns_vertebra():
    vert = np.zeros((10, 10, 3), dtype=bool); vert[2:6, 2:8, 1] = True
    out = extract_body_via_canal(vert, np.zeros_like(vert), ("P", "S", "R"))
    assert np.array_equal(out, vert)                 # no canal -> nothing to cut


# --- endplate-line measurement (PCA tilt-orient + fit sup/inf endplate lines) ----------
# This is the method that worked on real Duke T2 (per-vertebra Ha/Hp spread [0.77,1.01]
# vs [0.64,4.60] for the old image-axis edge measurement). Two behaviors it must have that
# the old method lacked: tilt-invariance and posterior-tail robustness.

def test_endplate_heights_uniform_rectangle_is_uniform():
    m = np.zeros((30, 20), dtype=bool)
    m[5:25, 4:16] = True                              # AP 5-24, SI 4-15 (12 tall, uniform)
    h = endplate_line_heights(m, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0, anterior="low")
    assert abs(h["Ha"] - h["Hp"]) <= 1.0
    assert abs(h["Ha"] - 12.0) <= 1.5                 # ~true thickness


def test_endplate_heights_tilt_invariant():
    # a UNIFORM body that is SHEARED (cervical tilt) must still read Ha ~= Hp ~= true thickness
    m = np.zeros((44, 44), dtype=bool)
    for ap in range(5, 32):
        sh = int((ap - 5) * 0.5)                      # shear -> tilted parallelogram
        m[ap, 6 + sh:18 + sh] = True                  # 12 tall, shifted in SI
    h = endplate_line_heights(m, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0, anterior="low")
    assert abs(h["Ha"] - h["Hp"]) <= 1.5              # tilt corrected -> uniform (the key behavior)
    assert 7.0 <= h["Ha"] <= 14.0                     # sensible perpendicular thickness, NOT shear-inflated
                                                      # (sheared 12-tall block -> perpendicular ~10.7)


def test_endplate_heights_wedge_detected():
    m = np.zeros((30, 20), dtype=bool)
    for ap in range(5, 25):
        ht = int(round(6 + (ap - 5) / 19.0 * 6))      # 6 (ant, low AP) -> 12 (post)
        m[ap, 4:4 + ht] = True
    h = endplate_line_heights(m, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0, anterior="low")
    assert h["Ha"] < h["Hp"]
    assert classify_genant(h)["grade"] >= 1


def test_endplate_heights_ignores_posterior_tail():
    # the real-data failure: a thin postero-inferior tail must NOT fake a deformity flag.
    # (With the old image-axis method this read Hp=2.1mm -> false crush. The thin-bin filter
    #  drops the tail from the endplate fit so it stays a non-flagged, sensible ratio.)
    m = np.zeros((34, 22), dtype=bool)
    m[2:24, 4:16] = True                              # body AP2-23, 12 tall
    m[24:31, 9:12] = True                             # thin posterior tail (3 tall)
    h = endplate_line_heights(m, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0, anterior="low")
    assert classify_genant(h)["grade"] == 0           # tail does NOT fake a fracture
    assert 0.80 <= h["Ha"] / h["Hp"] <= 1.30          # sensible ratio, not a collapsed wall


def test_measure_vertebra_no_false_wedge_on_fused_whole_vertebra():
    # The real RSNA false positive: fused body+spinous gave Ha=3.8/Hp=13.1 (false wedge),
    # because the WHOLE vertebra was measured (anterior window hit the body tip, posterior
    # ran down the spinous). After isolation the anterior window hits the real anterior
    # wall (Ha ~= body height) and the spinous is gone -> a uniform body is NOT flagged.
    # (A residual thin neck can shrink Hp, but that gives Ha>=Hp -> still no false wedge;
    #  it can only cost sensitivity, never cause a false positive.)
    vol = np.zeros((34, 26, 5), dtype=bool)
    vol[2:13, 3:11, 1:4] = True
    vol[12:15, 6:9, 1:4] = True
    vol[14:30, 9:23, 1:4] = True
    h = measure_vertebra(vol, ("P", "S", "R"), zooms=(0.43, 1.0, 4.0))
    assert classify_genant(h)["grade"] == 0         # uniform healthy body NOT flagged
    assert h["Ha"] >= 6.0                            # anterior wall now body-scale (was 3.8 tip)


def test_measure_vertebra_isolates_body_from_whole_vertebra():
    # Whole-vertebra 3D mask: a UNIFORM body (no wedge) + a tall posterior process.
    # Without isolation the process inflates Hp -> false wedge; with isolation Ha==Hp.
    vol = np.zeros((24, 16, 5), dtype=bool)
    vol[2:12, 3:11, 1:4] = True            # body: 8 voxels tall, uniform
    vol[16:22, 1:14, 1:4] = True           # spinous process: 13 voxels tall, posterior
    h = measure_vertebra(vol, ("P", "S", "R"), zooms=(0.43, 1.0, 4.0))
    assert abs(h["Ha"] - h["Hp"]) <= 1.0   # body only, uniform -> no false deformity
    assert classify_genant(h)["grade"] == 0


# --- validation scoring (predicted fracture flag vs expert label) ------------
# Each pair is (predicted_flag, truth_label). This turns the per-vertebra
# comparison against RSNA's labels into the sensitivity/specificity numbers.

def test_fracture_confusion_counts_and_rates():
    pairs = [(True, True), (True, True), (False, True),   # 2 TP, 1 FN
             (False, False), (False, False), (True, False)]  # 2 TN, 1 FP
    c = fracture_confusion(pairs)
    assert (c["tp"], c["fn"], c["tn"], c["fp"]) == (2, 1, 2, 1)
    assert c["sensitivity"] == 2 / 3        # TP / (TP+FN)
    assert c["specificity"] == 2 / 3        # TN / (TN+FP)
    assert c["n"] == 6


def test_fracture_confusion_handles_no_positives():
    # all-negative truth -> sensitivity undefined (None), specificity defined
    c = fracture_confusion([(False, False), (True, False)])
    assert c["sensitivity"] is None         # no real fractures to catch
    assert c["specificity"] == 1 / 2
    assert c["fp"] == 1
