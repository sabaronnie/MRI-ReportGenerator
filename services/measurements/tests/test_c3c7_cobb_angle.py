"""Tests for the C3-C7 Cobb angle component.

The component now fits ENDPLATE LINES to the C3 and C7 bodies (canal-cut isolation + Theil-Sen line
fit) directly on the segmentation, replacing the 2-corner AI->PI method (Wang 2023: line-fit
ICC 0.97 vs four-corner 0.75; J7-J12). It no longer depends on cervical_body_morphometry corners.
"""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import MeasurementContext, MeasurementError
from services.measurements.geometric import c3c7_cobb_angle


def _ctx(seg, spacing=(1.0, 1.0, 1.0)) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=seg.astype(np.int32),
        seg_affine=np.eye(4),               # canonical RAS -> axcodes ('R','A','S')
        voxel_spacing_mm=spacing,
    )


def _two_levels(c3_is=(24, 36), c7_is=(4, 16), pa=(18, 30)) -> np.ndarray:
    # canonical RAS (LR, PA, IS): bodies anterior (high PA), spinal canal posterior (low PA).
    seg = np.zeros((6, 34, 40), dtype=np.int32)
    seg[1:5, pa[0]:pa[1], c7_is[0]:c7_is[1]] = 17    # C7 (lower / low SI)
    seg[1:5, pa[0]:pa[1], c3_is[0]:c3_is[1]] = 13    # C3 (upper / high SI)
    seg[1:5, 8:14, 4:36] = 2                          # spinal canal (TSS label 2)
    return seg


def test_parallel_bodies_give_near_zero_cobb():
    result = c3c7_cobb_angle.compute(_ctx(_two_levels()), {})
    assert "Cobb_C3_C7" in result.measurements
    assert abs(result.measurements["Cobb_C3_C7"]["C3-C7"]) < 5.0


def test_returns_lordosis_positive_sign_convention():
    result = c3c7_cobb_angle.compute(_ctx(_two_levels()), {})
    assert result.metadata["sign_convention"] == "lordosis_positive_kyphosis_negative"


def test_unmeasurable_when_c7_absent_raises():
    seg = _two_levels()
    seg[seg == 17] = 0                      # drop C7 entirely
    with pytest.raises(MeasurementError):
        c3c7_cobb_angle.compute(_ctx(seg), {})
