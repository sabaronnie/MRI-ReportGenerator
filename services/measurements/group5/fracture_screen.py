"""Group 5.2 vertebral-body compression/deformity screen as a measurement component.

This adapts the validated Group 5 vertebral-body screen to the measurements IEP so the
output joins the same report/interpretation path as the other measurement groups.
"""

from __future__ import annotations

import nibabel as nib

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .flags_contract import build_flags_contract
from .vertebral_fracture import (
    cervical_deformity_flag,
    classify_genant,
    extract_body_via_canal,
    measure_vertebra,
    vertebra_axes_from_orientation,
)

NAME = "group5_fracture_screen"
DEPENDS_ON: list[str] = []

_CERVICAL = {13: "C3", 14: "C4", 15: "C5", 16: "C6", 17: "C7"}
_CANAL_LABEL = 2


def compute(ctx: MeasurementContext, prior: dict[str, ComponentResult] | None = None) -> ComponentResult:
    """Compute the Group 5 cervical Ha/Hp compression screen from the current segmentation."""
    seg = ctx.seg_data
    if seg.ndim != 3:
        raise MeasurementError("Group 5 fracture screen requires a 3D segmentation volume")

    axcodes = nib.aff2axcodes(ctx.seg_affine)
    zooms = ctx.voxel_spacing_mm
    vertebra_axes_from_orientation(axcodes)  # validates coverage of AP/SI/LR

    canal = seg == _CANAL_LABEL
    measurements = {"vb_hahp_ratio": {}}
    flags = {"vb_compression_screen_positive": {}}
    genant_grade: dict[str, int] = {}
    genant_type: dict[str, str] = {}
    heights_by_level: dict[str, dict[str, float]] = {}
    fracture_levels: list[tuple[str, dict[str, float]]] = []

    for label in sorted(lbl for lbl in _CERVICAL if (seg == lbl).any()):
        vert = seg == label
        body = extract_body_via_canal(vert, canal, axcodes) if canal.any() else vert
        heights = measure_vertebra(body, axcodes, zooms, isolate_body=not canal.any())
        if heights["Hp"] <= 0:
            continue

        level = _CERVICAL[label]
        ratio = float(heights["Ha"] / heights["Hp"])
        screen = cervical_deformity_flag(ratio)
        genant = classify_genant(heights)

        measurements["vb_hahp_ratio"][level] = round(ratio, 3)
        flags["vb_compression_screen_positive"][level] = bool(screen["flagged"])
        genant_grade[level] = int(genant["grade"])
        genant_type[level] = str(genant["type"])
        heights_by_level[level] = {
            "Ha": round(float(heights["Ha"]), 3),
            "Hm": round(float(heights["Hm"]), 3),
            "Hp": round(float(heights["Hp"]), 3),
        }
        fracture_levels.append((level, heights))

    if not measurements["vb_hahp_ratio"]:
        raise MeasurementError("Group 5 fracture screen could not measure any cervical vertebral bodies")

    contract = build_flags_contract(
        case_id=ctx.seg_path.name if ctx.seg_path is not None else "case",
        fracture_levels=fracture_levels,
        myelomalacia=None,
    )
    return ComponentResult(
        measurements=measurements,
        intermediate={},
        flags=flags,
        metadata={
            "levels": sorted(measurements["vb_hahp_ratio"].keys()),
            "heights_mm": heights_by_level,
            "genant_grade": genant_grade,
            "genant_type": genant_type,
            "group5_contract": contract,
            "group5_scope_note": (
                "Vertebral-body compression/deformity screen integrated into the measurements "
                "service; myelomalacia remains contract-only until lesion-mask ingestion is wired."
            ),
        },
    )
