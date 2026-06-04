"""Phase 3.3 - Space Available for Cord (SAC), derived from 3.1 + 3.2."""

from __future__ import annotations

from typing import Any

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .cord_ap import NAME as CORD_AP_NAME
from .functional_canal_ap import NAME as FUNCTIONAL_CANAL_AP_NAME


NAME = "sac"
DEPENDS_ON = [FUNCTIONAL_CANAL_AP_NAME, CORD_AP_NAME]

HIGH_RISK_THRESHOLD_MM = 3.0


def compute(ctx: MeasurementContext, prior_results: dict[str, Any] | None = None) -> ComponentResult:
    if prior_results is None:
        raise MeasurementError("sac requires prior functional_canal_ap and cord_ap results")

    canal = prior_results.get(FUNCTIONAL_CANAL_AP_NAME)
    cord = prior_results.get(CORD_AP_NAME)
    if canal is None or cord is None:
        raise MeasurementError("sac depends on functional_canal_ap and cord_ap")

    canal_ap = canal.measurements.get("dural_sac_AP_min", {})
    cord_ap = cord.measurements.get("cord_AP", {})
    canal_slices = canal.intermediate.get("focal_slice", {})
    cord_slices = cord.intermediate.get("source_slice", {})

    shared_levels = sorted(set(canal_ap) & set(cord_ap))
    if not shared_levels:
        raise MeasurementError("sac found no shared cervical levels between functional_canal_ap and cord_ap")

    measurements = {"SAC": {}}
    intermediate = {
        "focal_slice": {},
        "canal_ap_mm": {},
        "cord_ap_mm": {},
    }
    flags = {
        "sac_high_risk": {},
        "sac_slice_misaligned": {},
    }

    for level in shared_levels:
        sac_mm = float(canal_ap[level]) - float(cord_ap[level])
        measurements["SAC"][level] = round(sac_mm, 3)
        intermediate["focal_slice"][level] = canal_slices.get(level)
        intermediate["canal_ap_mm"][level] = float(canal_ap[level])
        intermediate["cord_ap_mm"][level] = float(cord_ap[level])
        flags["sac_high_risk"][level] = sac_mm < HIGH_RISK_THRESHOLD_MM
        flags["sac_slice_misaligned"][level] = canal_slices.get(level) != cord_slices.get(level)

    return ComponentResult(
        measurements=measurements,
        intermediate=intermediate,
        flags=flags,
        metadata={
            "levels": shared_levels,
            "method": "same-slice subtraction of dural_sac_AP_min and focal cord_AP",
            "measurement_name": "SAC",
            "high_risk_threshold_mm": HIGH_RISK_THRESHOLD_MM,
        },
    )
