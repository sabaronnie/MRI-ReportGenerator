"""Helpers for converting the assessement handoff contract into a report document."""

from __future__ import annotations

from typing import Any

from services.assessement import THRESHOLDS

REQUIRED_TOP_LEVEL_KEYS = (
    "contract_version",
    "case",
    "manifest",
    "components",
    "measurements",
    "flags",
    "assessements",
    "report_context",
)


def build_report_document(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize the post-assessement handoff contract into a report document.

    This is the reporting service's stable input boundary. It consumes the
    contract documented in `services/assessement/REPORTING_HANDOFF_CONTRACT.md`
    and produces a renderer-friendly document with explicit sections for
    findings, quality notes, disclaimers, and appendix data.
    """
    _validate_payload(payload)

    assessed_rows = list(payload["assessements"].get("measurements", []))
    syndromes = list(payload["assessements"].get("syndromes", []))
    components = dict(payload["components"])

    table_rows = [_build_table_row(row) for row in assessed_rows]
    highlighted_rows = [row for row in table_rows if row["flag"]]
    quality_notes = _build_quality_notes(assessed_rows, components)
    clinical_report = _build_clinical_report(
        payload=payload,
        table_rows=table_rows,
        syndromes=syndromes,
        components=components,
    )
    impression = list(clinical_report["impression"])
    provenance = _build_provenance(assessed_rows)
    case_header = _build_case_header(payload["case"])

    return {
        "report_version": "1.0",
        "source_contract_version": payload["contract_version"],
        "title": "Cervical Spine MRI Analysis Report",
        "case_header": case_header,
        "case": _normalize_case(payload["case"]),
        "summary": _build_summary(assessed_rows, syndromes),
        "clinical_report": clinical_report,
        "findings": {
            "table_rows": table_rows,
            "highlighted_measurements": highlighted_rows,
            "syndromes": syndromes,
        },
        "impression": impression,
        "quality_caveats": {
            "measurement_notes": [n for n in quality_notes if n["type"] == "measurement_quality"],
            "component_notes": [n for n in quality_notes if n["type"] == "component_error"],
            "general_caveats": _build_general_caveats(assessed_rows, syndromes),
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

    assessements = payload["assessements"]
    if not isinstance(assessements, dict):
        raise ValueError("reporting payload field `assessements` must be an object")

    for key in ("measurements", "syndromes"):
        if key not in assessements:
            raise ValueError(f"reporting payload field `assessements.{key}` is required")


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
        "exam": "MRI cervical spine",
        "technique": (
            "Automated research-use post-processing of sagittal cervical spine MRI "
            "including segmentation, measurement, assessement, and structured reporting."
        ),
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
        "not_assessable": 0,
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


def _build_clinical_report(
    *,
    payload: dict[str, Any],
    table_rows: list[dict[str, Any]],
    syndromes: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    findings_sections: list[dict[str, str]] = []

    alignment_section = _build_alignment_section(payload, components)
    if alignment_section is not None:
        findings_sections.append(alignment_section)

    clinical_rows = [row for row in table_rows if _is_clinically_reportable_row(row)]
    level_findings = _group_rows_by_level(clinical_rows)
    if level_findings:
        findings_sections.append(
            {
                "heading": "Level-Specific Findings",
                "body": " ".join(level_findings),
            }
        )

    if syndromes:
        findings_sections.append(
            {
                "heading": "Cord / Syndrome Pattern",
                "body": " ".join(_sentence_case(_build_impression(syndromes, []))),
            }
        )

    if not findings_sections:
        findings_sections.append(
            {
                "heading": "Findings",
                "body": (
                    "Within the scope of the current automated sagittal-MRI pipeline, "
                    "no reportable abnormal measurement was flagged."
                ),
            }
        )

    return {
        "exam": "MRI cervical spine",
        "technique": (
            "Automated analysis of sagittal cervical spine MRI. Research-use structured "
            "assessement only; not a substitute for radiologist review."
        ),
        "findings_sections": findings_sections,
        "findings_text": "\n\n".join(f"{section['heading']}: {section['body']}" for section in findings_sections),
        "impression": _build_clinical_impression(payload, clinical_rows, syndromes, components),
    }


def _build_quality_notes(
    assessed_rows: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    for row in assessed_rows:
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
    assessed_rows: list[dict[str, Any]],
    syndromes: list[dict[str, Any]],
) -> list[str]:
    caveats: list[str] = []

    for row in assessed_rows:
        caveat = row.get("caveat")
        if caveat:
            caveats.append(str(caveat))

    for syndrome in syndromes:
        caveat = syndrome.get("caveat")
        if caveat:
            caveats.append(str(caveat))

    return list(dict.fromkeys(caveats))


def _build_provenance(assessed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in assessed_rows:
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
    if isinstance(value, (int, float)):
        decimals = 2 if abs(value) < 2 else 1
        num = f"{value:.{decimals}f}"
    else:
        num = str(value)
    unit = "" if unit in (None, "", "unknown") else unit
    return f"{num} {unit}".strip()


def _build_alignment_section(
    payload: dict[str, Any],
    components: dict[str, dict[str, Any]],
) -> dict[str, str] | None:
    metadata = components.get("lordosis_classification", {}).get("metadata", {})
    label = (metadata.get("lordosis_classification") or {}).get("C3-C7")
    cobb = (payload.get("measurements", {}).get("Cobb_C3_C7") or {}).get("C3-C7")
    if label is None and cobb is None:
        return None

    pieces = []
    if label is not None:
        pieces.append(f"Cervical alignment is {label}.")
    if cobb is not None:
        pieces.append(f"C3-C7 Cobb angle measures {cobb:.1f} deg.")
    caveat = metadata.get("classification_caveat")
    if caveat:
        pieces.append(caveat)

    return {
        "heading": "Alignment",
        "body": " ".join(pieces),
    }


def _build_clinical_impression(
    payload: dict[str, Any],
    clinical_rows: list[dict[str, Any]],
    syndromes: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> list[str]:
    bullets: list[str] = []

    for syndrome in syndromes:
        advisory = syndrome.get("advisory")
        level = syndrome.get("level")
        if advisory:
            bullets.append(f"{level}: {advisory}" if level else str(advisory))

    top_rows = clinical_rows[:4]
    for row in top_rows:
        display_name = row.get("display_name") or row.get("measurement")
        level = row.get("level")
        severity = row.get("severity")
        value_str = _format_value(row.get("value"), row.get("unit") or "")
        if severity:
            bullets.append(f"{level}: {display_name} {value_str} ({severity}).")
        else:
            bullets.append(f"{level}: {display_name} {value_str}.")

    alignment_meta = components.get("lordosis_classification", {}).get("metadata", {})
    label = (alignment_meta.get("lordosis_classification") or {}).get("C3-C7")
    cobb = (payload.get("measurements", {}).get("Cobb_C3_C7") or {}).get("C3-C7")
    if label is not None:
        if cobb is not None:
            bullets.append(f"Alignment: {label}; C3-C7 Cobb angle {cobb:.1f} deg.")
        else:
            bullets.append(f"Alignment: {label}.")

    if not bullets:
        bullets.append(
            "Within the scope of the current automated sagittal-MRI pipeline, no reportable abnormality was flagged."
        )

    return list(dict.fromkeys(bullets))


def _is_clinically_reportable_row(row: dict[str, Any]) -> bool:
    return bool(row.get("flag")) and row.get("tag") != "quality"


def _group_rows_by_level(rows: list[dict[str, Any]]) -> list[str]:
    by_level: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_level.setdefault(str(row.get("level")), []).append(row)

    sentences: list[str] = []
    for level in sorted(by_level.keys()):
        level_rows = by_level[level]
        fragments = []
        for row in level_rows:
            display_name = row.get("display_name") or row.get("measurement")
            value_str = _format_value(row.get("value"), row.get("unit") or "")
            severity = row.get("severity")
            if severity:
                fragments.append(f"{display_name} {value_str} ({severity})")
            else:
                fragments.append(f"{display_name} {value_str}")
        if fragments:
            sentences.append(f"At {level}, " + "; ".join(fragments) + ".")
    return sentences


def _sentence_case(items: list[str]) -> list[str]:
    return [item[0].upper() + item[1:] if item else item for item in items]
