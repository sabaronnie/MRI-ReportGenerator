"""Tests for the derived SAC component."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import ComponentResult, MeasurementContext, MeasurementError
from services.measurements.cord import sac


def _ctx() -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((1, 1, 1), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=(1.0, 1.0, 1.0),
    )


def _prior() -> dict[str, ComponentResult]:
    return {
        "functional_canal_ap": ComponentResult(
            measurements={"dural_sac_AP_min": {"C5": 8.0, "C6": 7.0}},
            intermediate={"focal_slice": {"C5": 12, "C6": 21}},
            flags={},
            metadata={},
        ),
        "cord_ap": ComponentResult(
            measurements={"cord_AP": {"C5": 5.2, "C6": 5.5}},
            intermediate={"source_slice": {"C5": 12, "C6": 20}},
            flags={},
            metadata={},
        ),
    }


def test_requires_dependencies():
    with pytest.raises(MeasurementError, match="depends on functional_canal_ap and cord_ap"):
        sac.compute(_ctx(), {})


def test_computes_same_slice_sac_and_flags_alignment():
    result = sac.compute(_ctx(), _prior())

    assert result.measurements["SAC"]["C5"] == pytest.approx(2.8)
    assert result.flags["sac_high_risk"]["C5"] is True
    assert result.flags["sac_slice_misaligned"]["C5"] is False

    assert result.measurements["SAC"]["C6"] == pytest.approx(1.5)
    assert result.flags["sac_high_risk"]["C6"] is True
    assert result.flags["sac_slice_misaligned"]["C6"] is True
