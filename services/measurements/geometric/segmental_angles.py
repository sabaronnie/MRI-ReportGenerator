"""Phase 4.3 - Segmental angles from ENDPLATE-LINE fits on the segmentation.

Per adjacent cervical pair, the angle between the upper vertebra's INFERIOR endplate and the lower
vertebra's SUPERIOR endplate (the disc-bounding endplates), each fit as a Theil-Sen LINE after
canal-cut body isolation. Replaces the previous 2-corner (AI->PI / AS->PS) method that depended on
unstable cervical_body_morphometry corners (project J6-J12). Lordosis-positive.
"""

from __future__ import annotations

from typing import Any

import nibabel as nib
import numpy as np

from ..context import ComponentResult, MeasurementContext, MeasurementError
from ._endplate_cobb import (
    LORDOSIS_SIGN,
    _reliable_tangent,
    _vertebra_endplate,
    cobb_from_tangents,
)


NAME = "segmental_angles"
# Self-contained: fits endplate lines on the segmentation directly (no morphometry-corner dependency).
DEPENDS_ON: list[str] = []

CANAL_LABEL = 2
# (upper name, lower name, upper TSS label, lower TSS label) for C3-C4 .. C6-C7
SEGMENT_PAIRS = [
    ("C3", "C4", 13, 14),
    ("C4", "C5", 14, 15),
    ("C5", "C6", 15, 16),
    ("C6", "C7", 16, 17),
]


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    seg = np.asarray(ctx.seg_data)
    axcodes = nib.aff2axcodes(ctx.seg_affine)
    canal = seg == CANAL_LABEL
    zooms = ctx.voxel_spacing_mm

    segmental: dict[str, float] = {}
    for upper_name, lower_name, upper_label, lower_label in SEGMENT_PAIRS:
        upper_el = _vertebra_endplate(seg, upper_label, canal, axcodes, zooms)
        lower_el = _vertebra_endplate(seg, lower_label, canal, axcodes, zooms)
        t_upper = _reliable_tangent(upper_el, prefer="inf")   # upper vertebra inferior endplate
        t_lower = _reliable_tangent(lower_el, prefer="sup")   # lower vertebra superior endplate
        if t_upper is None or t_lower is None:
            continue
        angle = LORDOSIS_SIGN * cobb_from_tangents(t_upper, t_lower)
        segmental[f"{upper_name}-{lower_name}"] = round(float(angle), 3)

    if not segmental:
        raise MeasurementError(
            "segmental_angles: no adjacent C3-C7 pair measurable from the segmentation"
        )

    return ComponentResult(
        measurements={"segmental_angle": segmental},
        intermediate={},
        flags={},
        metadata={
            "pairs": list(segmental.keys()),
            "method": (
                "endplate-LINE fit (Theil-Sen): angle between the upper vertebra's inferior endplate "
                "and the lower vertebra's superior endplate. Replaces the corner AI->PI / AS->PS method."
            ),
            "sign_convention": "lordosis_positive_kyphosis_negative",
        },
    )
