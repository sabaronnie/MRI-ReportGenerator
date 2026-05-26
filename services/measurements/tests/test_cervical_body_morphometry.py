"""Unit tests for the cervical body morphometry component.

Builds a synthetic 3D segmentation with one rectangular cervical body and
adjacent discs, then checks that the component recovers the expected AP width
and three SI heights within voxel-quantization tolerance.
"""

from __future__ import annotations

import nibabel as nib
import pytest
import numpy as np

from services.measurements.context import load_context
from services.measurements.geometric import cervical_body_morphometry


@pytest.fixture
def synthetic_seg(tmp_path):
    LR, PA, IS = 25, 60, 50
    seg = np.zeros((LR, PA, IS), dtype=np.int16)
    spacing = 1.0

    lr_c, pa_c, is_c = LR // 2, PA // 2, IS // 2
    body_lr = slice(lr_c - 5, lr_c + 6)
    body_pa = slice(pa_c - 10, pa_c + 10)
    body_is = slice(is_c - 9, is_c + 9)
    seg[body_lr, body_pa, body_is] = 13  # C3

    arch_pa = slice(body_pa.start - 10, body_pa.start - 2)
    seg[body_lr, arch_pa, body_is] = 13

    seg[body_lr, body_pa, body_is.stop:body_is.stop + 4] = 63
    seg[body_lr, body_pa, body_is.start - 4:body_is.start] = 64

    canal_pa = slice(arch_pa.start - 6, arch_pa.start - 2)
    for s in (lr_c - 1, lr_c, lr_c + 1):
        seg[s, canal_pa, :] = 2

    path = tmp_path / "step2_output.nii.gz"
    nib.save(nib.Nifti1Image(seg, np.diag([spacing, spacing, spacing, 1.0])), str(path))
    return path


def test_recovers_ap_width_and_si_heights(synthetic_seg):
    """Sub-voxel refinement recovers the body's true physical size.

    The body is 20 voxels AP and 18 voxels SI at 1 mm-iso, i.e. 20 mm wide and
    18 mm tall. Voxel-centre extremes under-read by ~1 mm (the old 19/17 mm
    values); the sub-voxel boundary (SUBVOXEL_FACTOR) recovers within ~0.5 mm.
    """
    ctx = load_context(synthetic_seg)
    result = cervical_body_morphometry.compute(ctx)

    assert "C3" in result.measurements["AP_width"]
    assert result.measurements["AP_width"]["C3"] == pytest.approx(20.0, abs=0.5)
    assert result.measurements["H_anterior"]["C3"] == pytest.approx(18.0, abs=0.9)
    assert result.measurements["H_middle"]["C3"] == pytest.approx(18.0, abs=0.9)
    assert result.measurements["H_posterior"]["C3"] == pytest.approx(18.0, abs=0.9)


def test_flags_clean_on_synthetic(synthetic_seg):
    ctx = load_context(synthetic_seg)
    result = cervical_body_morphometry.compute(ctx)

    assert result.flags["ap_width_outlier"]["C3"] is False
    assert result.flags["tilt_outlier"]["C3"] is False
    assert result.flags["wedge_fracture"]["C3"] is False
    assert result.flags["biconcave_fracture"]["C3"] is False


def test_corners_lie_on_body_surface(synthetic_seg):
    """Sub-voxel corners are boundary points in original-voxel coordinates
    (floats), so each must round to within one voxel of an actual body voxel
    rather than drift into background or a neighbouring structure."""
    ctx = load_context(synthetic_seg)
    result = cervical_body_morphometry.compute(ctx)
    corners_voxel = result.intermediate["corners_voxel"]["C3"]
    body = ctx.seg_data == 13

    for name, (lr, pa, is_) in corners_voxel.items():
        lr_i, pa_i, is_i = int(round(lr)), int(round(pa)), int(round(is_))
        nbhd = body[
            max(lr_i - 1, 0):lr_i + 2,
            max(pa_i - 1, 0):pa_i + 2,
            max(is_i - 1, 0):is_i + 2,
        ]
        assert nbhd.any(), f"{name} at ({lr:.2f},{pa:.2f},{is_:.2f}) not within 1 voxel of body"
