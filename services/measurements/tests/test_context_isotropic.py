"""Unit tests for the isotropic-input guard in context.load_context.

Normal path: a 1 mm isotropic segmentation (what TotalSpineSeg `--iso` produces)
passes through untouched. Guard path: a non-isotropic mask is resampled to 1 mm
isotropic with nearest-neighbour interpolation, preserving integer labels.
"""

from __future__ import annotations

import nibabel as nib
import numpy as np
import pytest

from services.measurements.context import TARGET_ISO_MM, load_context


def _block_seg(shape, spacing, label=13):
    """A small labelled block centred in a volume, saved with the given spacing."""
    LR, PA, IS = shape
    seg = np.zeros((LR, PA, IS), dtype=np.int16)
    seg[LR // 2 - 3:LR // 2 + 3, PA // 2 - 8:PA // 2 + 8, IS // 2 - 7:IS // 2 + 7] = label
    affine = np.diag([spacing[0], spacing[1], spacing[2], 1.0])
    return nib.Nifti1Image(seg, affine)


def _oblique_block_seg(shape, spacing, label=13, tilt_deg=10.0):
    LR, PA, IS = shape
    seg = np.zeros((LR, PA, IS), dtype=np.int16)
    seg[LR // 2 - 3:LR // 2 + 3, PA // 2 - 8:PA // 2 + 8, IS // 2 - 7:IS // 2 + 7] = label

    theta = np.deg2rad(tilt_deg)
    rot_x = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(theta), -np.sin(theta)],
            [0.0, np.sin(theta), np.cos(theta)],
        ],
        dtype=np.float64,
    )
    affine = np.eye(4, dtype=np.float64)
    affine[:3, :3] = rot_x @ np.diag(spacing)
    return nib.Nifti1Image(seg, affine)


def test_isotropic_input_is_passthrough(tmp_path):
    path = tmp_path / "step2_output.nii.gz"
    nib.save(_block_seg((25, 60, 50), (1.0, 1.0, 1.0)), str(path))

    ctx = load_context(path)

    assert ctx.voxel_spacing_mm == pytest.approx((1.0, 1.0, 1.0))
    assert ctx.manifest["resampled_to_isotropic"] is None
    assert ctx.seg_data.shape == (25, 60, 50)
    assert 13 in ctx.manifest["labels_present"]
    assert ctx.manifest["geometry_standardized"] is None


def test_anisotropic_input_is_resampled_to_iso(tmp_path):
    path = tmp_path / "step2_output.nii.gz"
    # Thick LR slices (3 mm), fine in-plane (0.5 mm) — typical raw sagittal T2.
    nib.save(_block_seg((10, 120, 100), (3.0, 0.5, 0.5)), str(path))

    ctx = load_context(path)

    assert ctx.voxel_spacing_mm == pytest.approx((TARGET_ISO_MM,) * 3, abs=1e-3)
    rec = ctx.manifest["resampled_to_isotropic"]
    assert rec is not None
    assert rec["from_spacing_mm"] == [3.0, 0.5, 0.5]
    assert rec["to_spacing_mm"] == [1.0, 1.0, 1.0]
    # Nearest-neighbour resampling must preserve the label, not blend it away.
    assert 13 in ctx.manifest["labels_present"]
    assert set(np.unique(ctx.seg_data)).issubset({0, 13})


def test_oblique_input_is_standardized_before_iso_guard(tmp_path):
    path = tmp_path / "step2_output.nii.gz"
    nib.save(_oblique_block_seg((25, 60, 50), (1.0, 1.0, 1.0)), str(path))

    ctx = load_context(path)

    record = ctx.manifest["geometry_standardized"]
    assert record is not None
    assert record["max_oblique_deg"] > 5.0
    off_diag = ctx.seg_affine[:3, :3] - np.diag(np.diag(ctx.seg_affine[:3, :3]))
    assert np.max(np.abs(off_diag)) < 1e-3
    assert 13 in ctx.manifest["labels_present"]
