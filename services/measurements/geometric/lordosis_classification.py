"""Phase 4.2 - Derived lordosis classification from C3-C7 Cobb angle."""

from __future__ import annotations

from typing import Any

from ..context import ComponentResult, MeasurementContext, MeasurementError
from .c3c7_cobb_angle import NAME as C3C7_COBB_NAME


NAME = "lordosis_classification"
DEPENDS_ON = [C3C7_COBB_NAME]

KYPHOTIC_THRESHOLD_DEG = 0.0
LOW_LORDOSIS_THRESHOLD_DEG = 10.0
SUPINE_CAVEAT = (
    "Approximate classification only: derived from C3-C7 Cobb on supine MRI. "
    "Published normative thresholds are usually C2-C7 standing radiograph values "
    "and therefore read more lordotic than this pipeline."
)


def compute(ctx: MeasurementContext, prior_results: dict[str, Any]) -> ComponentResult:
    cobb_component = prior_results.get(C3C7_COBB_NAME)
    if cobb_component is None:
        raise MeasurementError("lordosis_classification depends on c3c7_cobb_angle")

    cobb_value = cobb_component.measurements.get("Cobb_C3_C7", {}).get("C3-C7")
    if cobb_value is None:
        raise MeasurementError("c3c7_cobb_angle produced no C3-C7 Cobb value")

    label = _classify(float(cobb_value))
    is_approximate = label != "kyphotic"

    return ComponentResult(
        measurements={},
        intermediate={},
        flags={
            "lordosis_classification_approximate": {
                "C3-C7": is_approximate,
            }
        },
        metadata={
            "lordosis_classification": {
                "C3-C7": label,
            },
            "cobb_source_deg": {
                "C3-C7": float(cobb_value),
            },
            "classification_thresholds_deg": {
                "kyphotic_lt": KYPHOTIC_THRESHOLD_DEG,
                "low_lordosis_lt": LOW_LORDOSIS_THRESHOLD_DEG,
            },
            "classification_caveat": SUPINE_CAVEAT,
        },
    )


def _classify(cobb_deg: float) -> str:
    if cobb_deg < KYPHOTIC_THRESHOLD_DEG:
        return "kyphotic"
    if cobb_deg < LOW_LORDOSIS_THRESHOLD_DEG:
        return "straightened / low lordosis"
    return "lordotic"
