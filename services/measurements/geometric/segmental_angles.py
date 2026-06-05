"""Phase 4.3 - Segmental angles from reused cervical body morphometry corners."""

from __future__ import annotations

from typing import Any

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .c3c7_cobb_angle import _line_angle_deg, _normalize_deg, _require_corners


NAME = "segmental_angles"
DEPENDS_ON = ["cervical_body_morphometry"]

SEGMENT_PAIRS = [
    ("C3", "C4"),
    ("C4", "C5"),
    ("C5", "C6"),
    ("C6", "C7"),
]


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    producer = prior_results.get("cervical_body_morphometry")
    if producer is None:
        raise MeasurementError(
            "segmental_angles requires `cervical_body_morphometry` in prior_results — "
            "register it as a DEPENDS_ON producer in the orchestrator."
        )

    corners_voxel = producer.intermediate.get("corners_voxel", {})
    spacing_pa_mm = float(ctx.voxel_spacing_mm[1])
    spacing_si_mm = float(ctx.voxel_spacing_mm[2])

    segmental: dict[str, float] = {}
    intermediate = {
        "upper_inferior_endplate_angle_deg": {},
        "lower_superior_endplate_angle_deg": {},
    }

    for upper_level, lower_level in SEGMENT_PAIRS:
        try:
            upper = _require_corners(corners_voxel, upper_level, ("AI", "PI"))
            lower = _require_corners(corners_voxel, lower_level, ("AS", "PS"))
        except MeasurementError:
            continue

        upper_angle = _line_angle_deg(upper["AI"], upper["PI"], spacing_pa_mm, spacing_si_mm)
        lower_angle = _line_angle_deg(lower["AS"], lower["PS"], spacing_pa_mm, spacing_si_mm)
        seg_angle = _normalize_deg(upper_angle - lower_angle)

        pair_key = f"{upper_level}-{lower_level}"
        segmental[pair_key] = round(seg_angle, 3)
        intermediate["upper_inferior_endplate_angle_deg"][pair_key] = round(upper_angle, 3)
        intermediate["lower_superior_endplate_angle_deg"][pair_key] = round(lower_angle, 3)

    if not segmental:
        raise MeasurementError("segmental_angles found no valid adjacent C3-C7 pairs with reusable corners")

    return ComponentResult(
        measurements={"segmental_angle": segmental},
        intermediate=intermediate,
        flags={},
        metadata={
            "pairs": list(segmental.keys()),
            "method": "signed angle difference of upper inferior endplate (AI->PI) and lower superior endplate (AS->PS) in global PA-SI frame",
            "sign_convention": "lordosis_positive_kyphosis_negative",
        },
    )
