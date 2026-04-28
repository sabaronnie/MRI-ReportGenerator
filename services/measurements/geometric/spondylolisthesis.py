"""Phase 3A.3 — spondylolisthesis (vertebral slippage) + Meyerding grading.

Reads PI corner of the upper vertebra and PS corner of the lower vertebra from
the cervical body morphometry component's intermediate output and computes the
AP-axis displacement in canonical-RAS mm. Operates entirely in canonical RAS so
axis 1 is anatomically anterior — no per-case affine introspection is required.

References: plans/phase-3a-geometric-measurements.md §3A.3
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError


NAME = "spondylolisthesis"
DEPENDS_ON = ["cervical_body_morphometry"]

LEVEL_ORDER = ["C2", "C3", "C4", "C5", "C6", "C7", "T1"]
NEUTRAL_THRESHOLD_MM = 1.0
SPONDY_PRESENT_THRESHOLD_MM = 2.0
SUPINE_CAVEAT = (
    "Measured on supine MRI — functional radiographs may show greater slip "
    "(Lattig 2012; Segebarth 2015)."
)


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    producer = prior_results.get("cervical_body_morphometry") or prior_results.get("genant_6point")
    if producer is None:
        raise MeasurementError(
            "spondylolisthesis requires `cervical_body_morphometry` in prior_results — "
            "register it as a DEPENDS_ON producer in the orchestrator."
        )

    corners_voxel = producer.intermediate.get("corners_voxel", {})
    ap_widths = producer.measurements.get("AP_width", {})
    spacing_pa_mm = float(ctx.voxel_spacing_mm[1])

    present = [n for n in LEVEL_ORDER if corners_voxel.get(n)]
    pairs = list(zip(present[:-1], present[1:]))

    slips: dict[str, float] = {}
    pcts: dict[str, float] = {}
    grades: dict[str, str] = {}
    directions: dict[str, str] = {}
    report_lines: dict[str, str] = {}
    flags_present: dict[str, bool] = {}

    for upper, lower in pairs:
        pair_key = f"{upper}-{lower}"
        upper_pi = corners_voxel.get(upper, {}).get("PI")
        lower_ps = corners_voxel.get(lower, {}).get("PS")
        if upper_pi is None or lower_ps is None:
            continue

        slip_mm = float((upper_pi[1] - lower_ps[1]) * spacing_pa_mm)
        ap_w = float(ap_widths.get(lower, float("nan")))

        if not np.isfinite(ap_w) or ap_w <= 0:
            grade = "?"
            pct = float("nan")
            grade_text = f"grade unknown ({lower} AP_width unavailable)"
        else:
            pct = abs(slip_mm) / ap_w * 100.0
            grade = _meyerding_grade(pct)
            grade_text = f"Grade {grade}, {pct:.1f}% of {lower} AP_width"

        if abs(slip_mm) < NEUTRAL_THRESHOLD_MM:
            direction = "neutral"
        elif slip_mm > 0:
            direction = "anterolisthesis"
        else:
            direction = "retrolisthesis"

        slips[pair_key] = slip_mm
        pcts[pair_key] = pct
        grades[pair_key] = grade
        directions[pair_key] = direction
        flags_present[pair_key] = abs(slip_mm) >= SPONDY_PRESENT_THRESHOLD_MM
        report_lines[pair_key] = (
            f"{upper} on {lower}: {abs(slip_mm):.2f} mm {direction} "
            f"({grade_text}). {SUPINE_CAVEAT}"
        )

    return ComponentResult(
        measurements={
            "spondy_slip_mm": slips,
            "spondy_pct_of_lower_AP": pcts,
        },
        intermediate={},
        flags={
            "spondylolisthesis_present": flags_present,
        },
        metadata={
            "spondy_meyerding_grade": grades,
            "spondy_direction": directions,
            "spondy_report_lines": report_lines,
            "spondy_caveat": SUPINE_CAVEAT,
            "pairs_evaluated": [f"{u}-{l}" for u, l in pairs],
        },
    )


def _meyerding_grade(pct: float) -> str:
    """Meyerding 1932 classification by % slip of the lower vertebra's AP width."""
    if pct < 25:  return "I"
    if pct < 50:  return "II"
    if pct < 75:  return "III"
    if pct < 100: return "IV"
    return "V"
