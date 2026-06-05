"""Tests for segmental angles derived from reused body-morphometry corners."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import ComponentResult, MeasurementContext, MeasurementError
from services.measurements.geometric import segmental_angles


def _ctx(spacing=(1.0, 1.0, 1.0)) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((1, 1, 1), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=spacing,
    )


def _prior(corners_voxel: dict) -> dict[str, ComponentResult]:
    return {
        "cervical_body_morphometry": ComponentResult(
            measurements={},
            intermediate={"corners_voxel": corners_voxel},
            flags={},
            metadata={},
        )
    }


def test_parallel_endplates_give_zero_segmental_angle():
    result = segmental_angles.compute(
        _ctx(),
        _prior(
            {
                "C3": {"AI": (0.0, 10.0, 20.0), "PI": (0.0, 0.0, 20.0)},
                "C4": {"AS": (0.0, 10.0, 30.0), "PS": (0.0, 0.0, 30.0)},
            }
        ),
    )
    assert result.measurements["segmental_angle"]["C3-C4"] == pytest.approx(0.0)


def test_positive_segmental_angle_when_lower_endplate_more_tilted():
    result = segmental_angles.compute(
        _ctx(),
        _prior(
            {
                "C3": {"AI": (0.0, 10.0, 20.0), "PI": (0.0, 0.0, 20.0)},    # 0 deg
                "C4": {"AS": (0.0, 10.0, 30.0), "PS": (0.0, 0.0, 35.0)},    # +26.565 deg
            }
        ),
    )
    assert result.measurements["segmental_angle"]["C3-C4"] == pytest.approx(26.565, abs=1e-3)


def test_missing_pairs_are_skipped_but_empty_result_raises():
    with pytest.raises(MeasurementError, match="no valid adjacent"):
        segmental_angles.compute(_ctx(), _prior({"C3": {"AI": (0, 0, 0), "PI": (0, 1, 0)}}))
