"""Unit tests for input_handler. Use synthetic NIfTI only — no patient data."""

from __future__ import annotations

import numpy as np
import nibabel as nib
import pytest

from services.segmentation.input_handler import InputError, prepare_nifti


def _sagittal_affine(spacing=(3.0, 0.7, 0.7)):
    """Affine whose first axis is L (sagittal-dominant in canonical RAS terms)."""
    a = np.diag([-spacing[0], spacing[1], spacing[2], 1.0])
    return a


def _make_nifti(path, shape=(20, 256, 256), spacing=(3.0, 0.7, 0.7), affine=None, ndim=3):
    rng = np.random.RandomState(0)
    if ndim == 4:
        data = rng.rand(*shape, 5).astype(np.float32) * 1000
    else:
        data = rng.rand(*shape).astype(np.float32) * 1000
    nib.save(nib.Nifti1Image(data, affine if affine is not None else _sagittal_affine(spacing)), str(path))
    return path


def test_passthrough_sagittal_nifti(tmp_path):
    p = _make_nifti(tmp_path / "scan.nii.gz")
    md = prepare_nifti(p, tmp_path / "work")
    assert md.nifti_path == p.resolve()
    assert md.shape == (20, 256, 256)
    assert md.voxel_spacing_mm == pytest.approx((3.0, 0.7, 0.7), rel=1e-6)
    assert md.canonical_axes[0] in ("L", "R")


def test_rejects_coronal_orientation(tmp_path):
    # Coronal-dominant: first axis is A/P, not L/R.
    a = np.zeros((4, 4))
    a[0, 1] = 0.7
    a[1, 0] = 3.0
    a[2, 2] = 0.7
    a[3, 3] = 1.0
    p = _make_nifti(tmp_path / "scan.nii.gz", affine=a)
    with pytest.raises(InputError, match="not sagittal-dominant"):
        prepare_nifti(p, tmp_path / "work")


def test_rejects_too_small(tmp_path):
    p = _make_nifti(tmp_path / "scan.nii.gz", shape=(5, 64, 64))
    with pytest.raises(InputError, match="too small"):
        prepare_nifti(p, tmp_path / "work")


def test_rejects_4d(tmp_path):
    p = _make_nifti(tmp_path / "scan.nii.gz", shape=(20, 256, 256), ndim=4)
    with pytest.raises(InputError, match="3D"):
        prepare_nifti(p, tmp_path / "work")


def test_rejects_nonexistent(tmp_path):
    with pytest.raises(InputError, match="not found"):
        prepare_nifti(tmp_path / "missing.nii.gz", tmp_path / "work")


def test_rejects_degenerate_intensity(tmp_path):
    # All-zero volume — still 3D, correct shape, but degenerate intensity.
    affine = _sagittal_affine()
    data = np.zeros((20, 256, 256), dtype=np.float32)
    p = tmp_path / "scan.nii.gz"
    nib.save(nib.Nifti1Image(data, affine), str(p))
    with pytest.raises(InputError, match="degenerate intensity"):
        prepare_nifti(p, tmp_path / "work")
