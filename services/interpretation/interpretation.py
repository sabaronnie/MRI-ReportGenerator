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


# Measurements whose cited normative comparison is age/sex-dependent. The note records HOW the
# demographic refines the reading; only `dural_sac_AP_min` currently changes the in-catalog band
# (sex-specific cut, Nell 2019 M10/F9). The rest carry the demographic for the report / external
# (SCT PAM50) normalisation. No cervical norm normalises by height -> height is record-only.
_DEMOGRAPHIC_MEASUREMENTS = {
    "dural_sac_AP_min": "sex-adjusted stenosis cut applied (Nell 2019, M<10/F<9 mm)",
    "cord_AP": "age/sex norm via SCT PAM50 (Valosek 2024, external)",
    "SAC": "compare to age/sex percentiles (Nell 2019)",
    "AP_width": "compare to age/sex percentiles (Nell 2019)",
}


def build_interpreted_measurements(
    report: dict[str, Any],
    measurement_sources: dict[str, str],
    flag_sources: dict[str, str],
    demographics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Wrap numeric measurement outputs in the standard interpretation container.

    Catalogued measurements (in `thresholds.THRESHOLDS`) get status/severity/flag from the cited
    threshold catalog via `classify`, sex-adjusted where a cited sex-specific cut exists; others
    fall back to the flag-only heuristic. `demographics` ({age, sex, height_cm}) is recorded per
    measurement in `demographics_used` where its cited norm is age/sex-dependent.
    """
    demographics = demographics or {}
    sex = demographics.get("sex")
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
                ev = classify(measurement_name, raw_value, sex=sex)
                status, severity, flag = ev.status, ev.severity, ev.flag
            else:
                status = "outside_reference" if has_pathology_flag else "review_only"
                severity = None
                flag = has_pathology_flag

            demographics_used = _demographics_used(measurement_name, demographics)

            interpreted.append(
                InterpretedMeasurement(
                    measurement=measurement_name,
                    level=str(level),
                    value=float(raw_value),
                    unit=_infer_unit(measurement_name),
                    status=status,
                    severity=severity,
                    flag=flag,
                    demographics_used=demographics_used,
                    quality_flags=quality_flags,
                    caveat=caveat,
                ).to_dict()
            )

    interpreted.sort(key=lambda row: (row["measurement"], row["level"]))
    return interpreted


def interpret_group5_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Interpret the Group 5 -> Group 6 findings contract (services/measurements/group5/flags_contract.py JSON).

    Maps each level's vertebral-body compression screen (Ha/Hp ratio) and, when assessed, its
    myelomalacia screen into the same InterpretedMeasurement container, driven by the catalog.
    Group 6 consumes the contract's JSON shape, not Group 5's code (they live on different
    branches). A not-assessed myelomalacia screen emits no row -- it is surfaced via the
    contract's `not_assessed` list in the report.
    """
    rows: list[dict[str, Any]] = []
    for level_entry in contract.get("levels", []):
        level = str(level_entry.get("level", ""))
        fracture = level_entry.get("fracture") or {}
        if "ratio" in fracture:
            ratio = fracture["ratio"]
            rows.append(_catalog_row("vb_hahp_ratio", level, ratio, classify("vb_hahp_ratio", ratio)))
        myelo = level_entry.get("myelomalacia") or {}
        if myelo.get("assessed") and myelo.get("present") is not None:
            present_val = 1.0 if myelo["present"] else 0.0
            rows.append(
                _catalog_row("myelomalacia", level, present_val, classify("myelomalacia", present_val))
            )
    rows.sort(key=lambda row: (row["measurement"], row["level"]))
    return rows


def _catalog_row(measurement: str, level: str, value: float, ev: Any) -> dict[str, Any]:
    """Build an InterpretedMeasurement row directly from a catalog ThresholdEval."""
    return InterpretedMeasurement(
        measurement=measurement,
        level=str(level),
        value=float(value),
        unit=ev.unit,
        status=ev.status,
        severity=ev.severity,
        flag=ev.flag,
        demographics_used={},
        quality_flags=[],
        caveat=ev.caveat,
    ).to_dict()


# Syndrome indicators (plan §4.3). PROVISIONAL combination rules -- advisory only, never a
# diagnosis. The exact combination logic + the radiculopathy evidence base are pending the
# Phase-4 research; these are documented placeholders flagged for review.
_MYELOPATHY_ADVISORY = (
    "pattern consistent with possible cervical myelopathy; clinical correlation required"
)
_RADICULOPATHY_ADVISORY = (
    "pattern that may relate to radiculopathy; foraminal dimensions are not measured on "
    "sagittal MRI, so this is weak -- clinical correlation required"
)


def detect_syndromes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Provisional syndrome-pattern indicators from interpreted rows (plan §4.3).

    PLACEHOLDER: advisory only, never diagnostic. The exact combination rules (and the
    radiculopathy evidence base on sagittal-only MRI) are pending the Phase-4 research, so each
    finding is marked `provisional` and carries a caveat.

    Myelopathy (provisional): canal narrowing (dural_sac_AP_min flagged) AND SAC high-risk AND a
    cord signal anomaly (myelomalacia flagged) at the same level.
    Radiculopathy (provisional, weaker): a disc bulge flagged with a disc-height-index signal at
    the same level -- DHI is currently a review-only gap, so this is a documented stub.
    """
    by_level: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        by_level.setdefault(str(r["level"]), {})[r["measurement"]] = r

    def flagged(level_map: dict[str, dict[str, Any]], name: str) -> bool:
        row = level_map.get(name)
        return bool(row and row.get("flag"))

    syndromes: list[dict[str, Any]] = []
    for level, m in by_level.items():
        if flagged(m, "dural_sac_AP_min") and flagged(m, "SAC") and flagged(m, "myelomalacia"):
            syndromes.append(
                {
                    "syndrome": "possible_myelopathy",
                    "level": level,
                    "status": "review_only",
                    "advisory": _MYELOPATHY_ADVISORY,
                    "contributing": ["dural_sac_AP_min", "SAC", "myelomalacia"],
                    "provisional": True,
                    "caveat": (
                        "Provisional combination rule (canal narrowing + SAC<3mm + cord signal); "
                        "exact rule pending Phase-4 research. Advisory only, never diagnostic."
                    ),
                }
            )
        if flagged(m, "posterior_bulge_mm") and "DHI" in m:
            syndromes.append(
                {
                    "syndrome": "possible_radiculopathy",
                    "level": level,
                    "status": "review_only",
                    "advisory": _RADICULOPATHY_ADVISORY,
                    "contributing": ["posterior_bulge_mm", "DHI"],
                    "provisional": True,
                    "caveat": (
                        "Provisional + WEAK: sagittal MRI does not measure foraminal dimensions "
                        "and DHI has no validated cervical cut. Pending Phase-4. Advisory only."
                    ),
                }
            )
    syndromes.sort(key=lambda s: (s["syndrome"], s["level"]))
    return syndromes


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


def _demographics_used(measurement_name: str, demographics: dict[str, Any]) -> dict[str, Any]:
    """Demographics that refine this measurement's reading (empty if none apply / none provided)."""
    note = _DEMOGRAPHIC_MEASUREMENTS.get(measurement_name)
    if note is None:
        return {}
    used = {k: demographics[k] for k in ("age", "sex") if demographics.get(k) is not None}
    if not used:
        return {}
    used["applies"] = note
    return used


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
