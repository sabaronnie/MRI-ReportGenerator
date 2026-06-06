"""Phase 4 interpretation scaffolding.

This module defines the standard per-measurement interpretation container used
by the measurement service. The first pass intentionally keeps the logic light:
it wraps existing numeric measurement outputs in a stable schema so threshold
rules can be added later without changing the API shape again.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .thresholds import THRESHOLDS, classify


# Substring markers that classify a flag as a QUALITY / caution flag (geometry or
# segmentation health) rather than a clinical abnormality. "outlier" and "unreliable" were
# added so tilt_outlier / ap_width_outlier / *_unreliable are treated as caution, not
# pathology (owner-confirmed -- see Ronnie's validation reply + groups_1_4_code_audit).
QUALITY_FLAG_MARKERS = (
    "low_confidence",
    "misaligned",
    "approximate",
    "resolution",
    "warning",
    "outlier",
    "unreliable",
)

UNIT_BY_MEASUREMENT = {
    "AP_width": "mm",
    "H_anterior": "mm",
    "H_middle": "mm",
    "H_posterior": "mm",
    "tilt_deg": "deg",
    "spondy_slip_mm": "mm",
    "spondy_pct_of_lower_AP": "%",
    "Cobb_C3_C7": "deg",
    "segmental_angle": "deg",
    "posterior_tangent_C3_C7": "deg",
    "dural_sac_AP_min": "mm",
    "cord_AP": "mm",
    "SAC": "mm",
    "disc_height_index": "ratio",
    "disc_AP_bulge": "mm",
    "disc_SI_height": "mm",
}


@dataclass(frozen=True)
class InterpretedMeasurement:
    measurement: str
    level: str
    value: float
    unit: str
    status: str
    severity: str | None
    flag: bool
    demographics_used: dict[str, Any]
    quality_flags: list[str]
    caveat: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_interpreted_measurements(
    report: dict[str, Any],
    measurement_sources: dict[str, str],
    flag_sources: dict[str, str],
) -> list[dict[str, Any]]:
    """Wrap numeric measurement outputs in the standard interpretation container.

    This is a Phase 4 scaffold, not the final threshold engine. Values with a
    known non-quality pathology flag are marked `outside_reference`; everything
    else remains `review_only` until a measurement-specific threshold rule is
    implemented.
    """
    components = report.get("components", {})
    flags = report.get("flags", {})
    interpreted: list[dict[str, Any]] = []

    for measurement_name, per_level in report.get("measurements", {}).items():
        component_name = measurement_sources.get(measurement_name)
        component_meta = components.get(component_name, {}).get("metadata", {})
        caveat = _extract_caveat(component_meta)

        for level, raw_value in per_level.items():
            quality_flags = _matching_flags(
                flags=flags,
                level=level,
                source_component=component_name,
                flag_sources=flag_sources,
                quality_only=True,
            )
            pathology_flags = _matching_flags(
                flags=flags,
                level=level,
                source_component=component_name,
                flag_sources=flag_sources,
                quality_only=False,
            )
            has_pathology_flag = any(flag_name not in quality_flags for flag_name in pathology_flags)

            # Catalogued measurements get status/severity/flag from the cited threshold
            # catalog (thresholds.py); its citation lives centrally there and is joined per
            # measurement by the report. Measurements not yet in the catalog fall back to the
            # prior flag-only heuristic.
            if measurement_name in THRESHOLDS:
                ev = classify(measurement_name, raw_value)
                status, severity, flag = ev.status, ev.severity, ev.flag
            else:
                status = "outside_reference" if has_pathology_flag else "review_only"
                severity = None
                flag = has_pathology_flag

            interpreted.append(
                InterpretedMeasurement(
                    measurement=measurement_name,
                    level=str(level),
                    value=float(raw_value),
                    unit=_infer_unit(measurement_name),
                    status=status,
                    severity=severity,
                    flag=flag,
                    demographics_used={},
                    quality_flags=quality_flags,
                    caveat=caveat,
                ).to_dict()
            )

    interpreted.sort(key=lambda row: (row["measurement"], row["level"]))
    return interpreted


def _matching_flags(
    *,
    flags: dict[str, dict[str, bool]],
    level: str,
    source_component: str | None,
    flag_sources: dict[str, str],
    quality_only: bool,
) -> list[str]:
    matched: list[str] = []
    for flag_name, per_level in flags.items():
        if str(level) not in per_level or not per_level[str(level)]:
            continue
        if source_component is not None and flag_sources.get(flag_name) != source_component:
            continue
        is_quality_flag = _is_quality_flag(flag_name)
        if quality_only and is_quality_flag:
            matched.append(flag_name)
        elif not quality_only and not is_quality_flag:
            matched.append(flag_name)
    return sorted(matched)


def _is_quality_flag(flag_name: str) -> bool:
    lowered = flag_name.lower()
    return any(marker in lowered for marker in QUALITY_FLAG_MARKERS)


def _extract_caveat(metadata: dict[str, Any]) -> str | None:
    for key, value in metadata.items():
        if key.endswith("_caveat") and isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _infer_unit(measurement_name: str) -> str:
    unit = UNIT_BY_MEASUREMENT.get(measurement_name)
    if unit is not None:
        return unit
    if measurement_name.endswith("_deg"):
        return "deg"
    if measurement_name.endswith("_mm"):
        return "mm"
    if "ratio" in measurement_name.lower():
        return "ratio"
    return "unknown"
