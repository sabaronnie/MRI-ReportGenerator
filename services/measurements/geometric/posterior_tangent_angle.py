"""Phase 4.4 - Posterior tangent angle as a secondary / cross-check metric."""

from __future__ import annotations

from typing import Any

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .c3c7_cobb_angle import (
    LOWER_LEVEL,
    UPPER_LEVEL,
    _line_angle_deg,
    _normalize_deg,
    _require_corners,
)


NAME = "posterior_tangent_angle"
DEPENDS_ON = ["cervical_body_morphometry", "c3c7_cobb_angle"]


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    producer = prior_results.get("cervical_body_morphometry")
    if producer is None:
        raise MeasurementError(
            "posterior_tangent_angle requires `cervical_body_morphometry` in prior_results — "
            "register it as a DEPENDS_ON producer in the orchestrator."
        )

    cobb_component = prior_results.get("c3c7_cobb_angle")
    if cobb_component is None:
        raise MeasurementError("posterior_tangent_angle depends on c3c7_cobb_angle")

    corners_voxel = producer.intermediate.get("corners_voxel", {})
    upper = _require_corners(corners_voxel, UPPER_LEVEL, ("PS", "PI"))
    lower = _require_corners(corners_voxel, LOWER_LEVEL, ("PS", "PI"))

    spacing_pa_mm = float(ctx.voxel_spacing_mm[1])
    spacing_si_mm = float(ctx.voxel_spacing_mm[2])

    angle_c3 = _line_angle_deg(upper["PS"], upper["PI"], spacing_pa_mm, spacing_si_mm)
    angle_c7 = _line_angle_deg(lower["PS"], lower["PI"], spacing_pa_mm, spacing_si_mm)
    # Same clinical sign convention as the Cobb component: positive = lordosis.
    tangent_deg = _normalize_deg(angle_c3 - angle_c7)

    cobb_deg = cobb_component.measurements.get("Cobb_C3_C7", {}).get("C3-C7")
    if cobb_deg is None:
        raise MeasurementError("c3c7_cobb_angle produced no C3-C7 Cobb value")
    divergence_deg = abs(float(cobb_deg) - tangent_deg)

    return ComponentResult(
        measurements={
            "posterior_tangent_C3_C7": {
                "C3-C7": round(tangent_deg, 3),
            }
        },
        intermediate={
            "posterior_wall_angle_deg": {
                UPPER_LEVEL: round(angle_c3, 3),
                LOWER_LEVEL: round(angle_c7, 3),
            },
            "posterior_wall_voxel": {
                UPPER_LEVEL: {"PS": tuple(upper["PS"]), "PI": tuple(upper["PI"])},
                LOWER_LEVEL: {"PS": tuple(lower["PS"]), "PI": tuple(lower["PI"])},
            },
        },
        flags={},
        metadata={
            "method": "signed angle difference of C3 and C7 posterior walls (PS->PI) in global PA-SI frame",
            "levels": [UPPER_LEVEL, LOWER_LEVEL],
            "sign_convention": "lordosis_positive_kyphosis_negative",
            "cobb_reference_deg": {"C3-C7": float(cobb_deg)},
            "cobb_divergence_deg": {"C3-C7": round(divergence_deg, 3)},
            "assessement": (
                "Secondary / cross-check metric. Large divergence from Cobb may reflect "
                "corner-fit instability, endplate-definition instability, or local vertebral shape irregularity."
            ),
        },
    )
