"""Helpers for converting the interpretation handoff contract into a report document."""

from __future__ import annotations

from typing import Any

from services.interpretation import THRESHOLDS

REQUIRED_TOP_LEVEL_KEYS = (
    "contract_version",
    "case",
    "manifest",
    "components",
    "measurements",
    "flags",
    "interpretations",
    "report_context",
)


def build_report_document(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize the post-interpretation handoff contract into a report document.

    This is the reporting service's stable input boundary. It consumes the
    contract documented in `services/interpretation/REPORTING_HANDOFF_CONTRACT.md`
    and produces a renderer-friendly document with explicit sections for
    findings, quality notes, disclaimers, and appendix data.
    """
    _validate_payload(payload)

    interpreted_rows = list(payload["interpretations"].get("measurements", []))
    syndromes = list(payload["interpretations"].get("syndromes", []))
    components = dict(payload["components"])

    table_rows = [_build_table_row(row) for row in interpreted_rows]
    highlighted_rows = [row for row in table_rows if row["flag"]]
    quality_notes = _build_quality_notes(interpreted_rows, components)
    impression = _build_impression(syndromes, highlighted_rows)
    provenance = _build_provenance(interpreted_rows)
    case_header = _build_case_header(payload["case"])

    return {
        "report_version": "1.0",
        "source_contract_version": payload["contract_version"],
        "title": "Cervical Spine MRI Analysis Report",
        "case_header": case_header,
        "case": _normalize_case(payload["case"]),
        "summary": _build_summary(interpreted_rows, syndromes),
        "findings": {
            "table_rows": table_rows,
            "highlighted_measurements": highlighted_rows,
            "syndromes": syndromes,
        },
        "impression": impression,
        "quality_caveats": {
            "measurement_notes": [n for n in quality_notes if n["type"] == "measurement_quality"],
            "component_notes": [n for n in quality_notes if n["type"] == "component_error"],
            "general_caveats": _build_general_caveats(interpreted_rows, syndromes),
        },
        "quality_notes": quality_notes,
        "disclaimers": list(payload["report_context"].get("disclaimers", [])),
        "metadata": {
            "modality": payload["report_context"].get("modality"),
            "report_language": payload["report_context"].get("report_language"),
            "include_appendix": bool(payload["report_context"].get("include_appendix", True)),
        },
        "appendix": {
            "manifest": dict(payload["manifest"]),
            "provenance": provenance,
            "raw_data": {
                "components": components,
                "measurements": dict(payload["measurements"]),
                "flags": dict(payload["flags"]),
            },
        },
    }


def _validate_payload(payload: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in payload]
    if missing:
        raise ValueError(f"reporting payload missing required top-level keys: {', '.join(sorted(missing))}")

    interpretations = payload["interpretations"]
    if not isinstance(interpretations, dict):
        raise ValueError("reporting payload field `interpretations` must be an object")

    for key in ("measurements", "syndromes"):
        if key not in interpretations:
            raise ValueError(f"reporting payload field `interpretations.{key}` is required")


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    patient_context = dict(case.get("patient_context") or {})
    source_file = dict(case.get("source_file") or {})
    return {
        "job_id": case.get("job_id"),
        "case_id": case.get("case_id"),
        "submitted_at": case.get("submitted_at"),
        "patient_context": {
            "sex": patient_context.get("sex"),
            "age_years": patient_context.get("age_years"),
            "height_cm": patient_context.get("height_cm"),
        },
        "source_file": {
            "filename": source_file.get("filename"),
        },
    }


def _build_case_header(case: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_case(case)
    patient_context = normalized["patient_context"]
    parts = []
    if patient_context.get("sex"):
        parts.append(str(patient_context["sex"]).title())
    if patient_context.get("age_years") is not None:
        parts.append(f'{patient_context["age_years"]} years')
    if patient_context.get("height_cm") is not None:
        parts.append(f'{patient_context["height_cm"]} cm')

    return {
        "title": "Cervical Spine MRI Analysis Report",
        "case_id": normalized.get("case_id"),
        "job_id": normalized.get("job_id"),
        "submitted_at": normalized.get("submitted_at"),
        "source_filename": normalized["source_file"].get("filename"),
        "patient_summary": ", ".join(parts) if parts else None,
        "patient_context": patient_context,
    }


def _build_summary(rows: list[dict[str, Any]], syndromes: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {
        "within_reference": 0,
        "outside_reference": 0,
        "review_only": 0,
        "not_interpretable": 0,
    }
    for row in rows:
        status = row.get("status")
        if status in status_counts:
            status_counts[status] += 1

    return {
        "measurement_row_count": len(rows),
        "flagged_measurement_count": sum(1 for row in rows if row.get("flag")),
        "syndrome_count": len(syndromes),
        "status_counts": status_counts,
    }


def _build_table_row(row: dict[str, Any]) -> dict[str, Any]:
    measurement_key = str(row.get("measurement"))
    spec = THRESHOLDS.get(measurement_key)
    return {
        "measurement": measurement_key,
        "display_name": spec.clinical_name if spec is not None else _prettify_key(measurement_key),
        "level": row.get("level"),
        "value": row.get("value"),
        "unit": row.get("unit"),
        "status": row.get("status"),
        "severity": row.get("severity"),
        "flag": bool(row.get("flag")),
        "quality_flags": list(row.get("quality_flags", [])),
        "caveat": row.get("caveat"),
        "citation": spec.citation if spec is not None else None,
        "tag": spec.tag if spec is not None else None,
    }


def _build_impression(
    syndromes: list[dict[str, Any]],
    highlighted_rows: list[dict[str, Any]],
) -> list[str]:
    bullets: list[str] = []

    for syndrome in syndromes:
        level = syndrome.get("level")
        advisory = syndrome.get("advisory")
        if advisory:
            bullets.append(f"{level}: {advisory}" if level else str(advisory))

    for row in highlighted_rows:
        display_name = row.get("display_name") or row.get("measurement")
        level = row.get("level")
        value = row.get("value")
        unit = row.get("unit") or ""
        severity = row.get("severity")

        value_str = _format_value(value, unit)
        if severity:
            bullets.append(f"{level}: {display_name} {value_str} ({severity}).")
        else:
            bullets.append(f"{level}: {display_name} {value_str}.")

    # Preserve order but drop duplicates if a syndrome/advisory and a measurement
    # happen to generate the same sentence.
    return list(dict.fromkeys(bullets))


def _build_quality_notes(
    interpreted_rows: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    for row in interpreted_rows:
        quality_flags = list(row.get("quality_flags", []))
        if quality_flags:
            notes.append(
                {
                    "type": "measurement_quality",
                    "measurement": row.get("measurement"),
                    "level": row.get("level"),
                    "quality_flags": quality_flags,
                    "caveat": row.get("caveat"),
                }
            )

    for component_name, component_data in components.items():
        if component_data.get("status") == "error":
            notes.append(
                {
                    "type": "component_error",
                    "component": component_name,
                    "error": component_data.get("error"),
                }
            )

    return notes


def _build_general_caveats(
    interpreted_rows: list[dict[str, Any]],
    syndromes: list[dict[str, Any]],
) -> list[str]:
    caveats: list[str] = []

    for row in interpreted_rows:
        caveat = row.get("caveat")
        if caveat:
            caveats.append(str(caveat))

    for syndrome in syndromes:
        caveat = syndrome.get("caveat")
        if caveat:
            caveats.append(str(caveat))

    return list(dict.fromkeys(caveats))


def _build_provenance(interpreted_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in interpreted_rows:
        key = str(row.get("measurement"))
        if key in seen:
            continue
        seen.add(key)
        spec = THRESHOLDS.get(key)
        provenance.append(
            {
                "measurement": key,
                "display_name": spec.clinical_name if spec is not None else _prettify_key(key),
                "citation": spec.citation if spec is not None else None,
                "tag": spec.tag if spec is not None else None,
                "caveat": spec.modality_caveat if spec is not None else None,
                "provenance_note": spec.provenance_note if spec is not None else None,
            }
        )

    return provenance


def _prettify_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _format_value(value: Any, unit: str) -> str:
    if value is None:
        return "unavailable"
    return f"{value} {unit}".strip()
