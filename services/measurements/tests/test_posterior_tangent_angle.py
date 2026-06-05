"""Tests for the posterior tangent cross-check component."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import ComponentResult, MeasurementContext, MeasurementError
from services.measurements.geometric import posterior_tangent_angle


def _ctx(spacing=(1.0, 1.0, 1.0)) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((1, 1, 1), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=spacing,
    )


def _prior(corners_voxel: dict, cobb_deg: float) -> dict[str, ComponentResult]:
    return {
        "cervical_body_morphometry": ComponentResult(
            measurements={},
            intermediate={"corners_voxel": corners_voxel},
            flags={},
            metadata={},
        ),
        "c3c7_cobb_angle": ComponentResult(
            measurements={"Cobb_C3_C7": {"C3-C7": cobb_deg}},
            intermediate={},
            flags={},
            metadata={},
        ),
    }


def test_parallel_posterior_walls_give_zero():
    result = posterior_tangent_angle.compute(
        _ctx(),
        _prior(
            {
                "C3": {"PS": (0.0, 0.0, 30.0), "PI": (0.0, 0.0, 20.0)},
                "C7": {"PS": (0.0, 2.0, 50.0), "PI": (0.0, 2.0, 40.0)},
            },
            cobb_deg=0.0,
        ),
    )
    assert result.measurements["posterior_tangent_C3_C7"]["C3-C7"] == pytest.approx(0.0)
    assert result.metadata["cobb_divergence_deg"]["C3-C7"] == pytest.approx(0.0)


def test_positive_sign_matches_cobb_convention():
    result = posterior_tangent_angle.compute(
        _ctx(),
        _prior(
            {
                "C3": {"PS": (0.0, 0.0, 30.0), "PI": (0.0, 0.0, 20.0)},   # vertical
                "C7": {"PS": (0.0, 5.0, 50.0), "PI": (0.0, 0.0, 40.0)},   # tilted
            },
            cobb_deg=26.565,
        ),
    )
    assert result.measurements["posterior_tangent_C3_C7"]["C3-C7"] == pytest.approx(26.565, abs=1e-3)
    assert result.metadata["cobb_divergence_deg"]["C3-C7"] == pytest.approx(0.0, abs=1e-3)


def test_missing_dependencies_raise():
    with pytest.raises(MeasurementError, match="cervical_body_morphometry"):
        posterior_tangent_angle.compute(_ctx(), {})
