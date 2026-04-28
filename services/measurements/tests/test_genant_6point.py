"""Unit tests for the 6-point Genant pipeline using a synthetic segmentation.

Builds a 3D label volume with rectangular vertebra bodies and adjacent discs of known
geometry, then asserts the pipeline recovers the AP width and SI heights to within
voxel-quantization error.
"""

from __future__ import annotations

import nibabel as nib
import numpy as np
import pytest

from services.measurements.context import load_context
from services.measurements.geometric import genant_6point


@pytest.fixture
def synthetic_seg(tmp_path):
    """One-vertebra synthetic segmentation: C3 body 20×18mm with discs above/below."""
    LR, PA, IS = 25, 60, 50
    seg = np.zeros((LR, PA, IS), dtype=np.int16)
    spacing = 1.0  # 1 mm-iso

    lr_c, pa_c, is_c = LR // 2, PA // 2, IS // 2
    body_lr = slice(lr_c - 5, lr_c + 6)        # 11 voxels in LR
    body_pa = slice(pa_c - 10, pa_c + 10)      # 20 voxels in PA → 20 mm AP width
    body_is = slice(is_c - 9, is_c + 9)        # 18 voxels in IS → 18 mm SI height
    seg[body_lr, body_pa, body_is] = 13        # C3

    # Posterior arch + spinous process — same vertebra label, posterior of disc AP range.
    arch_pa = slice(body_pa.start - 10, body_pa.start - 2)
    seg[body_lr, arch_pa, body_is] = 13

    # C2-C3 disc (label 63) above the body, AP-aligned with body.
    seg[body_lr, body_pa, body_is.stop:body_is.stop + 4] = 63
    # C3-C4 disc (label 64) below the body.
    seg[body_lr, body_pa, body_is.start - 4:body_is.start] = 64

    # Canal (label 2) — narrow midline strip behind the arch, on three central LR slices.
    canal_pa = slice(arch_pa.start - 6, arch_pa.start - 2)
    for s in (lr_c - 1, lr_c, lr_c + 1):
        seg[s, canal_pa, :] = 2

    affine = np.diag([spacing, spacing, spacing, 1.0])
    p = tmp_path / "step2_output.nii.gz"
    nib.save(nib.Nifti1Image(seg, affine), str(p))
    return p


def test_recovers_ap_width_and_si_heights(synthetic_seg):
    ctx = load_context(synthetic_seg)
    result = genant_6point.compute(ctx)

    assert "C3" in result.measurements["AP_width"]
    ap_width = result.measurements["AP_width"]["C3"]
    h_anterior = result.measurements["H_anterior"]["C3"]
    h_middle = result.measurements["H_middle"]["C3"]
    h_posterior = result.measurements["H_posterior"]["C3"]

    # 20mm body, top/bottom strips at 15% → corners at the actual edges (0 and 19 → 19 mm span).
    # Heights similar (~17 mm at 1 mm-iso; the 18-voxel span produces a 17-mm corner-to-corner distance).
    assert ap_width == pytest.approx(19.0, abs=1.0)
    assert h_anterior == pytest.approx(17.0, abs=1.0)
    assert h_middle == pytest.approx(17.0, abs=1.0)
    assert h_posterior == pytest.approx(17.0, abs=1.0)


def test_pathology_flags_clean_on_synthetic(synthetic_seg):
    ctx = load_context(synthetic_seg)
    result = genant_6point.compute(ctx)
    flags = result.flags
    assert flags["wedge_fracture"]["C3"] is False
    assert flags["biconcave_fracture"]["C3"] is False
    assert flags["tilt_outlier"]["C3"] is False
    # 20-mm AP_width is on the upper edge of the normative band [12, 22] → not flagged.
    assert flags["ap_width_outlier"]["C3"] is False


def test_corners_are_real_body_pixels(synthetic_seg):
    """Edge-strip extrema must land on actual body voxels, not bbox vertices."""
    ctx = load_context(synthetic_seg)
    result = genant_6point.compute(ctx)
    corners_voxel = result.intermediate["corners_voxel"]["C3"]
    seg = ctx.seg_data
    for name, (lr, pa, is_) in corners_voxel.items():
        assert seg[lr, pa, is_] == 13, f"{name} at voxel ({lr},{pa},{is_}) is not on body"
