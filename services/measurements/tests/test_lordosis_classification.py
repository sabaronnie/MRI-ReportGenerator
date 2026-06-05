"""Tests for the derived lordosis classification component."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import ComponentResult, MeasurementContext, MeasurementError
from services.measurements.geometric import lordosis_classification


def _ctx() -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((1, 1, 1), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=(1.0, 1.0, 1.0),
    )


def _prior(cobb_deg: float) -> dict[str, ComponentResult]:
    return {
        "c3c7_cobb_angle": ComponentResult(
            measurements={"Cobb_C3_C7": {"C3-C7": cobb_deg}},
            intermediate={},
            flags={},
            metadata={},
        )
    }


def test_requires_cobb_dependency():
    with pytest.raises(MeasurementError, match="depends on c3c7_cobb_angle"):
        lordosis_classification.compute(_ctx(), {})


def test_kyphotic_is_only_hard_category():
    result = lordosis_classification.compute(_ctx(), _prior(-2.0))
    assert result.metadata["lordosis_classification"]["C3-C7"] == "kyphotic"
    assert result.flags["lordosis_classification_approximate"]["C3-C7"] is False


def test_low_lordosis_and_lordotic_are_marked_approximate():
    low = lordosis_classification.compute(_ctx(), _prior(5.0))
    assert low.metadata["lordosis_classification"]["C3-C7"] == "straightened / low lordosis"
    assert low.flags["lordosis_classification_approximate"]["C3-C7"] is True

    lordotic = lordosis_classification.compute(_ctx(), _prior(18.0))
    assert lordotic.metadata["lordosis_classification"]["C3-C7"] == "lordotic"
    assert lordotic.flags["lordosis_classification_approximate"]["C3-C7"] is True
