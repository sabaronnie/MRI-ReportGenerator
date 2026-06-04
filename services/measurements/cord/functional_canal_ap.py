"""Phase 3.1 - Functional canal / dural-sac AP diameter via SCT.

This component intentionally measures the soft-tissue canal space rather than a
true osseous canal. It segments the dural-sac / canal space with SCT's
`sc_canal_t2` model, then uses `sct_process_segmentation -perslice 1` to obtain
angle-corrected AP diameters slice-by-slice. For each vertebral level, the
reported value is the narrowest *stable* AP diameter, defined as the minimum
3-slice rolling median within that level.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from ..context import ComponentResult, MeasurementContext, MeasurementError
from ..sct import SCTError, ShapeMetricRow, run_deepseg, run_process_segmentation


NAME = "functional_canal_ap"
DEPENDS_ON: list[str] = []

LEVELS = {
    2: "C2",
    3: "C3",
    4: "C4",
    5: "C5",
    6: "C6",
    7: "C7",
}
LOW_CONFIDENCE_SLICE_COUNT = 3


@dataclass(frozen=True)
class _LevelSliceMetric:
    slice_index: int
    raw_ap_mm: float
    stable_ap_mm: float


def compute(ctx: MeasurementContext, prior_results: dict[str, Any] | None = None) -> ComponentResult:
    if ctx.raw_path is None:
        raise MeasurementError(
            "functional_canal_ap requires a raw/iso MRI path; upload must include input_iso.nii.gz"
        )
    if ctx.levels_path is None:
        raise MeasurementError(
            "functional_canal_ap requires TotalSpineSeg step1_levels.nii.gz for vertebral-level mapping"
        )

    try:
        with tempfile.TemporaryDirectory(prefix="mri-canal-ap-") as tmpdir:
            work_dir = Path(tmpdir)
            canal_seg = run_deepseg("sc_canal_t2", ctx.raw_path, work_dir / "deepseg")
            rows = run_process_segmentation(
                canal_seg,
                discfile=ctx.levels_path,
                output_csv=work_dir / "functional_canal_ap.csv",
                vert="2:7",
                perslice=True,
            )
    except SCTError as e:
        raise MeasurementError(str(e)) from e

    grouped = _group_by_level(rows)
    if not grouped:
        raise MeasurementError("SCT produced no per-slice canal AP rows for cervical levels C2-C7")

    measurements = {"dural_sac_AP_min": {}}
    intermediate = {
        "focal_slice": {},
        "focal_raw_ap_mm": {},
        "slice_metrics": {},
    }
    flags = {
        "dural_sac_low_confidence": {},
    }

    for level_num in sorted(grouped):
        level_name = LEVELS[level_num]
        summary = _select_narrowest_stable(grouped[level_num])
        measurements["dural_sac_AP_min"][level_name] = round(summary.stable_ap_mm, 3)
        intermediate["focal_slice"][level_name] = summary.slice_index
        intermediate["focal_raw_ap_mm"][level_name] = round(summary.raw_ap_mm, 3)
        intermediate["slice_metrics"][level_name] = [
            {
                "slice_index": row.slice_index,
                "raw_ap_mm": round(row.raw_ap_mm, 3),
                "stable_ap_mm": round(row.stable_ap_mm, 3),
            }
            for row in grouped[level_num]
        ]
        flags["dural_sac_low_confidence"][level_name] = len(grouped[level_num]) < LOW_CONFIDENCE_SLICE_COUNT

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={
            "levels": [LEVELS[n] for n in sorted(grouped)],
            "method": "SCT sc_canal_t2 + sct_process_segmentation perslice + 3-slice stable minimum",
            "measurement_name": "dural_sac_AP_min",
        },
    )


def _group_by_level(rows: list[ShapeMetricRow]) -> dict[int, list[_LevelSliceMetric]]:
    grouped: dict[int, list[_LevelSliceMetric]] = {}
    for row in rows:
        if row.vertebral_level not in LEVELS or row.slice_index is None:
            continue
        raw_ap = row.metrics.get("diameter_AP")
        if raw_ap is None:
            continue
        grouped.setdefault(row.vertebral_level, []).append(
            _LevelSliceMetric(
                slice_index=row.slice_index,
                raw_ap_mm=raw_ap,
                stable_ap_mm=raw_ap,
            )
        )

    for level, level_rows in grouped.items():
        level_rows.sort(key=lambda r: r.slice_index)
        smoothed = []
        raw_values = [r.raw_ap_mm for r in level_rows]
        for idx, row in enumerate(level_rows):
            lo = max(0, idx - 1)
            hi = min(len(level_rows), idx + 2)
            stable = float(median(raw_values[lo:hi]))
            smoothed.append(
                _LevelSliceMetric(
                    slice_index=row.slice_index,
                    raw_ap_mm=row.raw_ap_mm,
                    stable_ap_mm=stable,
                )
            )
        grouped[level] = smoothed
    return grouped


def _select_narrowest_stable(rows: list[_LevelSliceMetric]) -> _LevelSliceMetric:
    if not rows:
        raise MeasurementError("cannot select narrowest canal AP from an empty level row set")
    return min(rows, key=lambda row: (row.stable_ap_mm, row.raw_ap_mm, row.slice_index))
