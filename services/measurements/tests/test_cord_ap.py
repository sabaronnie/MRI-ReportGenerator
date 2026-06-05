"""Tests for the SCT-backed focal cord AP component."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import ComponentResult, MeasurementContext, MeasurementError
from services.measurements.cord import cord_ap
from services.measurements.sct import ShapeMetricRow


def _ctx(tmp_path, *, raw=True, levels=True) -> MeasurementContext:
    raw_path = tmp_path / "input_iso.nii.gz" if raw else None
    levels_path = tmp_path / "step1_levels.nii.gz" if levels else None
    cord_seg_path = tmp_path / "sct_spinalcord_seg.nii.gz"
    if raw_path is not None:
        raw_path.write_bytes(b"fake")
    if levels_path is not None:
        levels_path.write_bytes(b"fake")
    cord_seg_path.write_bytes(b"fake")
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((5, 5, 5), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=(1.0, 1.0, 1.0),
        levels_path=levels_path,
        raw_path=raw_path,
        sct_cord_seg_path=cord_seg_path,
    )


def _prior(focal_slices: dict[str, int]) -> dict[str, ComponentResult]:
    return {
        "functional_canal_ap": ComponentResult(
            measurements={"dural_sac_AP_min": {k: 1.0 for k in focal_slices}},
            intermediate={"focal_slice": focal_slices},
            flags={},
            metadata={},
        )
    }


def test_requires_dependency(tmp_path):
    with pytest.raises(MeasurementError, match="depends on functional_canal_ap"):
        cord_ap.compute(_ctx(tmp_path), {})


def test_aligns_to_focal_slice_and_uses_nearest_fallback(monkeypatch, tmp_path):
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        cord_ap,
        "run_process_segmentation",
        lambda *args, **kwargs: [
            ShapeMetricRow(slice_index=11, vertebral_level=5, metrics={"diameter_AP": 6.2}, raw={}),
            ShapeMetricRow(slice_index=12, vertebral_level=5, metrics={"diameter_AP": 6.0}, raw={}),
            ShapeMetricRow(slice_index=13, vertebral_level=5, metrics={"diameter_AP": 5.9}, raw={}),
            ShapeMetricRow(slice_index=20, vertebral_level=6, metrics={"diameter_AP": 5.5}, raw={}),
            ShapeMetricRow(slice_index=22, vertebral_level=6, metrics={"diameter_AP": 5.3}, raw={}),
        ],
    )

    result = cord_ap.compute(ctx, _prior({"C5": 12, "C6": 21}))

    assert result.measurements["cord_AP"]["C5"] == pytest.approx(6.0)
    assert result.intermediate["source_slice"]["C5"] == 12
    assert result.flags["cord_slice_misaligned"]["C5"] is False

    assert result.measurements["cord_AP"]["C6"] == pytest.approx(5.5)
    assert result.intermediate["source_slice"]["C6"] == 20
    assert result.intermediate["slice_delta"]["C6"] == 1
    assert result.flags["cord_slice_misaligned"]["C6"] is True


def test_uses_precomputed_sct_mask_without_raw(monkeypatch, tmp_path):
    ctx = _ctx(tmp_path, raw=False)
    monkeypatch.setattr(
        cord_ap,
        "run_process_segmentation",
        lambda *args, **kwargs: [
            ShapeMetricRow(slice_index=12, vertebral_level=5, metrics={"diameter_AP": 6.0}, raw={}),
        ],
    )

    result = cord_ap.compute(ctx, _prior({"C5": 12}))
    assert result.measurements["cord_AP"]["C5"] == pytest.approx(6.0)
