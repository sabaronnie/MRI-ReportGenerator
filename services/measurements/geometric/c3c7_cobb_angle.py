"""Phase 4.1 - C3-C7 Cobb angle from ENDPLATE-LINE fits on the segmentation.

Fits straight lines (Theil-Sen) to the C3 and C7 inferior endplates after canal-cut body isolation,
and takes the angle between them (lordosis-positive). This replaces the previous 2-corner AI->PI
method, which depended on cervical_body_morphometry corners that were unstable on real lordotic necks
(project J6-J12; Wang 2023 found line-fit ICC 0.97 vs four-corner 0.75). The C6/C7 endpoint-precision
upgrade is `_endplate_cobb.spineps_endplate_cobb_angle` (fits SPINEPS endplate voxels), available once
the SPINEPS instance mask is plumbed into the measurement context.

The `_line_angle_deg` / `_normalize_deg` / `_require_corners` helpers below are retained because
`segmental_angles` and `posterior_tangent_angle` still import them.
"""

from __future__ import annotations

import math
from typing import Any

import nibabel as nib

from ..context import ComponentResult, MeasurementContext, MeasurementError
from ._endplate_cobb import cobb_angle, spineps_endplate_cobb_angle


NAME = "c3c7_cobb_angle"
# Self-contained: fits endplate LINES on the segmentation directly (no morphometry-corner dependency).
DEPENDS_ON: list[str] = []

C3_LABEL = 13
C7_LABEL = 17
CANAL_LABEL = 2

# SPINEPS instance numbers for C3 and C7 (the function adds the endplate-voxel offset internally).
C3_INSTANCE = 3
C7_INSTANCE = 7

UPPER_LEVEL = "C3"
LOWER_LEVEL = "C7"
REQUIRED_CORNERS = ("AI", "PI")

_CANAL_CUT_METHOD = (
    "endplate-LINE fit (Theil-Sen) to the canal-cut C3 and C7 bodies; Cobb = angle "
    "between the two inferior-endplate lines (Wang 2023: line-fit ICC 0.97 vs "
    "four-corner 0.75; project J7-J12). Replaces the 2-corner AI->PI method."
)
_SPINEPS_METHOD = (
    "SPINEPS endplate-VOXEL line fit (Option C1): Cobb = angle between the C3 and C7 inferior "
    "endplate sheets read directly from the SPINEPS instance mask. Best C6/C7 endpoint precision "
    "(project J12: C6-C7 SD 5.9 vs canal-cut 18.5 deg). Preferred when seg-vert is present."
)


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    """C3-C7 Cobb (lordosis-positive). Prefers the SPINEPS endplate-voxel method when a seg-vert
    mask is plumbed into the context (best endpoint precision); otherwise fits endplate LINES on
    the canal-cut C3 and C7 bodies."""
    cobb_deg = None
    method = _CANAL_CUT_METHOD

    if ctx.seg_vert_data is not None:
        sp = spineps_endplate_cobb_angle(
            ctx.seg_vert_data,
            ctx.seg_vert_axcodes,
            ctx.seg_vert_zooms,
            C3_INSTANCE,
            C7_INSTANCE,
        )
        if sp is not None and sp == sp:          # measurable (not None / NaN)
            cobb_deg = sp
            method = _SPINEPS_METHOD

    if cobb_deg is None:                          # no seg-vert, or SPINEPS endplate unmeasurable
        axcodes = nib.aff2axcodes(ctx.seg_affine)
        cobb_deg = cobb_angle(
            ctx.seg_data,
            axcodes,
            ctx.voxel_spacing_mm,
            top_label=C3_LABEL,
            bottom_label=C7_LABEL,
            canal_label=CANAL_LABEL,
        )

    if cobb_deg is None:
        raise MeasurementError(
            "c3c7_cobb_angle: C3 or C7 inferior endplate is not measurable from the segmentation "
            "(missing level, or endplate orientation unreliable -- e.g. C7 obscured at the "
            "cervicothoracic junction)."
        )

    return ComponentResult(
        measurements={"Cobb_C3_C7": {"C3-C7": round(float(cobb_deg), 3)}},
        intermediate={},
        flags={},
        metadata={
            "method": method,
            "levels": [UPPER_LEVEL, LOWER_LEVEL],
            "sign_convention": "lordosis_positive_kyphosis_negative",
            "supine_caveat": (
                "Supine MRI; compare to standing-radiograph norms with care. C6/C7 endpoint precision "
                "is best with the SPINEPS endplate-voxel upgrade (spineps_endplate_cobb_angle)."
            ),
        },
    )


def _require_corners(
    corners_voxel: dict[str, Any],
    level: str,
    required: tuple[str, ...],
) -> dict[str, tuple[float, float, float]]:
    level_corners = corners_voxel.get(level)
    if not level_corners:
        raise MeasurementError(f"c3c7_cobb_angle requires corners for {level}")
    missing = [name for name in required if level_corners.get(name) is None]
    if missing:
        raise MeasurementError(f"c3c7_cobb_angle missing corners for {level}: {missing}")
    return level_corners


def _require_endplate(corners_voxel: dict[str, Any], level: str) -> dict[str, tuple[float, float, float]]:
    return _require_corners(corners_voxel, level, REQUIRED_CORNERS)


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
