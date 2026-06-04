"""Tests for the SCT-backed functional canal / dural-sac AP component."""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import MeasurementContext, MeasurementError
from services.measurements.cord import functional_canal_ap
from services.measurements.sct import ShapeMetricRow


def _ctx(tmp_path, *, raw=True, levels=True) -> MeasurementContext:
    raw_path = tmp_path / "input_iso.nii.gz" if raw else None
    levels_path = tmp_path / "step1_levels.nii.gz" if levels else None
    if raw_path is not None:
        raw_path.write_bytes(b"fake")
    if levels_path is not None:
        levels_path.write_bytes(b"fake")
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((5, 5, 5), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=(1.0, 1.0, 1.0),
        levels_path=levels_path,
        raw_path=raw_path,
    )


def test_requires_raw_and_levels(tmp_path):
    with pytest.raises(MeasurementError, match="raw/iso MRI"):
        functional_canal_ap.compute(_ctx(tmp_path, raw=False))
    with pytest.raises(MeasurementError, match="step1_levels"):
        functional_canal_ap.compute(_ctx(tmp_path, levels=False))


def test_reports_narrowest_stable_ap(monkeypatch, tmp_path):
    ctx = _ctx(tmp_path)

    monkeypatch.setattr(
        functional_canal_ap,
        "run_deepseg",
        lambda task, raw_path, output_dir: tmp_path / "canal_seg.nii.gz",
    )
    monkeypatch.setattr(
        functional_canal_ap,
        "run_process_segmentation",
        lambda *args, **kwargs: [
            ShapeMetricRow(slice_index=10, vertebral_level=5, metrics={"diameter_AP": 10.0}, raw={}),
            ShapeMetricRow(slice_index=11, vertebral_level=5, metrics={"diameter_AP": 8.0}, raw={}),
            ShapeMetricRow(slice_index=12, vertebral_level=5, metrics={"diameter_AP": 6.0}, raw={}),
            ShapeMetricRow(slice_index=13, vertebral_level=5, metrics={"diameter_AP": 8.0}, raw={}),
            ShapeMetricRow(slice_index=14, vertebral_level=5, metrics={"diameter_AP": 10.0}, raw={}),
            ShapeMetricRow(slice_index=20, vertebral_level=6, metrics={"diameter_AP": 9.0}, raw={}),
            ShapeMetricRow(slice_index=21, vertebral_level=6, metrics={"diameter_AP": 9.0}, raw={}),
        ],
    )

    result = functional_canal_ap.compute(ctx)

    assert result.measurements["dural_sac_AP_min"]["C5"] == pytest.approx(8.0)
    assert result.intermediate["focal_slice"]["C5"] == 12
    assert result.intermediate["focal_raw_ap_mm"]["C5"] == pytest.approx(6.0)
    assert result.flags["dural_sac_low_confidence"]["C5"] is False
    assert result.flags["dural_sac_low_confidence"]["C6"] is True
