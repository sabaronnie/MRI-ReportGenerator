"""Tests for the C3-C7 Cobb angle component."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import ComponentResult, MeasurementContext, MeasurementError
from services.measurements.geometric import c3c7_cobb_angle


def _ctx(spacing=(1.0, 1.0, 1.0)) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((1, 1, 1), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=spacing,
    )


def _fake_body_morphometry(corners_voxel: dict) -> dict[str, ComponentResult]:
    return {
        "cervical_body_morphometry": ComponentResult(
            measurements={},
            intermediate={"corners_voxel": corners_voxel},
            flags={},
            metadata={},
        )
    }


def test_zero_cobb_for_parallel_endplates():
    prior = _fake_body_morphometry(
        {
            "C3": {"AI": (0.0, 10.0, 20.0), "PI": (0.0, 0.0, 20.0)},
            "C7": {"AI": (0.0, 12.0, 40.0), "PI": (0.0, 2.0, 40.0)},
        }
    )
    result = c3c7_cobb_angle.compute(_ctx(), prior)
    assert result.measurements["Cobb_C3_C7"]["C3-C7"] == pytest.approx(0.0)


def test_positive_lordosis_when_c7_more_tilted():
    prior = _fake_body_morphometry(
        {
            "C3": {"AI": (0.0, 10.0, 20.0), "PI": (0.0, 0.0, 20.0)},   # 0 deg
            "C7": {"AI": (0.0, 10.0, 40.0), "PI": (0.0, 0.0, 45.0)},   # +26.565 deg
        }
    )
    result = c3c7_cobb_angle.compute(_ctx(), prior)
    assert result.measurements["Cobb_C3_C7"]["C3-C7"] == pytest.approx(26.565, abs=1e-3)


def test_spacing_applied_in_common_frame():
    prior = _fake_body_morphometry(
        {
            "C3": {"AI": (0.0, 10.0, 20.0), "PI": (0.0, 0.0, 20.0)},
            "C7": {"AI": (0.0, 10.0, 40.0), "PI": (0.0, 0.0, 45.0)},
        }
    )
    result = c3c7_cobb_angle.compute(_ctx(spacing=(1.0, 2.0, 1.0)), prior)
    # dpa doubles to 20 mm, dsi stays 5 mm => atan2(5, -20) relative difference ~14.036 deg
    assert result.measurements["Cobb_C3_C7"]["C3-C7"] == pytest.approx(14.036, abs=1e-3)


def test_missing_corners_raise():
    prior = _fake_body_morphometry({"C3": {"AI": (0.0, 0.0, 0.0), "PI": (0.0, 1.0, 0.0)}})
    with pytest.raises(MeasurementError, match="corners for C7"):
        c3c7_cobb_angle.compute(_ctx(), prior)
