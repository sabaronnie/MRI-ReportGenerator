"""Phase 4.1 - C3-C7 Cobb angle from existing body-morphometry corners.

Reuses `cervical_body_morphometry` corner landmarks:
    - inferior endplate of C3 = AI -> PI
    - inferior endplate of C7 = AI -> PI

Important: the computation uses `corners_voxel * voxel_spacing_mm` in the common
canonical-RAS frame. It must never use `corners_mm`, which live in each
vertebra's local PCA frame and are therefore not directly comparable across
levels.
"""

from __future__ import annotations

import math
from typing import Any

from ..context import ComponentResult, MeasurementContext, MeasurementError


NAME = "c3c7_cobb_angle"
DEPENDS_ON = ["cervical_body_morphometry"]

UPPER_LEVEL = "C3"
LOWER_LEVEL = "C7"
REQUIRED_CORNERS = ("AI", "PI")


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    producer = prior_results.get("cervical_body_morphometry")
    if producer is None:
        raise MeasurementError(
            "c3c7_cobb_angle requires `cervical_body_morphometry` in prior_results — "
            "register it as a DEPENDS_ON producer in the orchestrator."
        )

    corners_voxel = producer.intermediate.get("corners_voxel", {})
    upper = _require_endplate(corners_voxel, UPPER_LEVEL)
    lower = _require_endplate(corners_voxel, LOWER_LEVEL)

    spacing_pa_mm = float(ctx.voxel_spacing_mm[1])
    spacing_si_mm = float(ctx.voxel_spacing_mm[2])

    angle_c3 = _line_angle_deg(upper["AI"], upper["PI"], spacing_pa_mm, spacing_si_mm)
    angle_c7 = _line_angle_deg(lower["AI"], lower["PI"], spacing_pa_mm, spacing_si_mm)
    # With canonical-RAS coordinates, PA increases anteriorly and the reused line
    # direction is AI -> PI (anterior -> posterior). In that convention, the raw
    # geometric difference is the opposite of the desired clinical sign. Flip it
    # here so lordosis is positive and kyphosis is negative.
    cobb_deg = _normalize_deg(angle_c3 - angle_c7)

    return ComponentResult(
        measurements={
            "Cobb_C3_C7": {
                "C3-C7": round(cobb_deg, 3),
            }
        },
        intermediate={
            "endplate_angle_deg": {
                UPPER_LEVEL: round(angle_c3, 3),
                LOWER_LEVEL: round(angle_c7, 3),
            },
            "inferior_endplate_voxel": {
                UPPER_LEVEL: {"AI": tuple(upper["AI"]), "PI": tuple(upper["PI"])},
                LOWER_LEVEL: {"AI": tuple(lower["AI"]), "PI": tuple(lower["PI"])},
            },
        },
        flags={},
        metadata={
            "method": "signed angle difference of C3 and C7 inferior endplates (AI->PI) in global PA-SI frame",
            "levels": [UPPER_LEVEL, LOWER_LEVEL],
            "sign_convention": "lordosis_positive_kyphosis_negative",
        },
    )


def _require_endplate(corners_voxel: dict[str, Any], level: str) -> dict[str, tuple[float, float, float]]:
    level_corners = corners_voxel.get(level)
    if not level_corners:
        raise MeasurementError(f"c3c7_cobb_angle requires corners for {level}")
    missing = [name for name in REQUIRED_CORNERS if level_corners.get(name) is None]
    if missing:
        raise MeasurementError(f"c3c7_cobb_angle missing corners for {level}: {missing}")
    return level_corners


def _line_angle_deg(
    anterior_corner: tuple[float, float, float],
    posterior_corner: tuple[float, float, float],
    spacing_pa_mm: float,
    spacing_si_mm: float,
) -> float:
    """Angle of AI->PI in the global PA-SI plane."""
    dpa = (posterior_corner[1] - anterior_corner[1]) * spacing_pa_mm
    dsi = (posterior_corner[2] - anterior_corner[2]) * spacing_si_mm
    return math.degrees(math.atan2(dsi, dpa))


def _normalize_deg(angle_deg: float) -> float:
    """Normalize a signed line-angle difference to [-180, 180)."""
    normalized = (angle_deg + 180.0) % 360.0 - 180.0
    # Prefer +180 over -180 for symmetric edge cases.
    if normalized == -180.0:
        return 180.0
    return normalized
