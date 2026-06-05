"""Phase 3.2 - Spinal cord AP diameter via SCT, aligned to 3.1 focal slices."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...segmentation.sct_segmenter import SCTSegmentationError, run_sct_deepseg
from ..context import ComponentResult, MeasurementContext, MeasurementError
from ..sct import SCTError, ShapeMetricRow, run_process_segmentation
from .functional_canal_ap import LEVELS, NAME as FUNCTIONAL_CANAL_AP_NAME


NAME = "cord_ap"
DEPENDS_ON = [FUNCTIONAL_CANAL_AP_NAME]


@dataclass(frozen=True)
class _CordSliceMetric:
    slice_index: int
    raw_ap_mm: float


def compute(ctx: MeasurementContext, prior_results: dict[str, Any] | None = None) -> ComponentResult:
    if ctx.raw_path is None and ctx.sct_cord_seg_path is None:
        raise MeasurementError("cord_ap requires either a precomputed SCT cord mask or input_iso.nii.gz")
    if ctx.levels_path is None:
        raise MeasurementError("cord_ap requires TotalSpineSeg step1_levels.nii.gz for vertebral-level mapping")
    if prior_results is None or FUNCTIONAL_CANAL_AP_NAME not in prior_results:
        raise MeasurementError("cord_ap depends on functional_canal_ap focal slices")

    focal_slices = prior_results[FUNCTIONAL_CANAL_AP_NAME].intermediate.get("focal_slice", {})
    if not focal_slices:
        raise MeasurementError("functional_canal_ap produced no focal slices for cord_ap to align against")

    try:
        with tempfile.TemporaryDirectory(prefix="mri-cord-ap-") as tmpdir:
            work_dir = Path(tmpdir)
            cord_seg = ctx.sct_cord_seg_path
            if cord_seg is None:
                cord_seg = run_sct_deepseg("spinalcord", ctx.raw_path, work_dir / "deepseg")
            rows = run_process_segmentation(
                cord_seg,
                discfile=ctx.levels_path,
                output_csv=work_dir / "cord_ap.csv",
                vert="2:7",
                perslice=True,
            )
    except (SCTError, SCTSegmentationError) as e:
        raise MeasurementError(str(e)) from e

    grouped = _group_by_level(rows)
    if not grouped:
        raise MeasurementError("SCT produced no per-slice cord AP rows for cervical levels C2-C7")

    measurements = {"cord_AP": {}}
    intermediate = {
        "focal_slice": {},
        "source_slice": {},
        "slice_delta": {},
        "slice_metrics": {},
    }
    flags = {
        "cord_slice_misaligned": {},
        "cord_level_missing": {},
    }

    for level_name, focal_slice in focal_slices.items():
        level_num = _level_num(level_name)
        level_rows = grouped.get(level_num)
        if not level_rows:
            flags["cord_level_missing"][level_name] = True
            flags["cord_slice_misaligned"][level_name] = True
            continue

        chosen = _select_for_slice(level_rows, int(focal_slice))
        measurements["cord_AP"][level_name] = round(chosen.raw_ap_mm, 3)
        intermediate["focal_slice"][level_name] = int(focal_slice)
        intermediate["source_slice"][level_name] = chosen.slice_index
        intermediate["slice_delta"][level_name] = abs(chosen.slice_index - int(focal_slice))
        intermediate["slice_metrics"][level_name] = [
            {"slice_index": row.slice_index, "raw_ap_mm": round(row.raw_ap_mm, 3)}
            for row in level_rows
        ]
        flags["cord_level_missing"][level_name] = False
        flags["cord_slice_misaligned"][level_name] = chosen.slice_index != int(focal_slice)

    if not measurements["cord_AP"]:
        raise MeasurementError("cord_ap could not align any cervical levels to functional_canal_ap focal slices")

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={
            "levels": sorted(measurements["cord_AP"].keys()),
            "method": "SCT spinalcord + sct_process_segmentation perslice aligned to functional canal focal slice",
            "measurement_name": "cord_AP",
        },
    )


def _group_by_level(rows: list[ShapeMetricRow]) -> dict[int, list[_CordSliceMetric]]:
    grouped: dict[int, list[_CordSliceMetric]] = {}
    for row in rows:
        if row.vertebral_level not in LEVELS or row.slice_index is None:
            continue
        raw_ap = row.metrics.get("diameter_AP")
        if raw_ap is None:
            continue
        grouped.setdefault(row.vertebral_level, []).append(
            _CordSliceMetric(slice_index=row.slice_index, raw_ap_mm=raw_ap)
        )

    for level_rows in grouped.values():
        level_rows.sort(key=lambda r: r.slice_index)
    return grouped


def _select_for_slice(rows: list[_CordSliceMetric], focal_slice: int) -> _CordSliceMetric:
    return min(rows, key=lambda row: (abs(row.slice_index - focal_slice), row.slice_index))


def _level_num(level_name: str) -> int:
    for num, name in LEVELS.items():
        if name == level_name:
            return num
    raise MeasurementError(f"Unknown cervical level name from functional_canal_ap: {level_name}")
