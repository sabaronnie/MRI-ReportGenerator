"""HTML rendering helpers for structured reports."""

from __future__ import annotations

import html
import json
from typing import Any


def render_clinical_report_html(document: dict[str, Any]) -> str:
    """Render the user-facing radiology-style report.

    This variant intentionally excludes raw structured data, threshold provenance,
    and the explainability appendix. It is the HTML that should back the
    user-targeted PDF.
    """
    case_header = dict(document.get("case_header") or {})
    clinical_report = dict(document.get("clinical_report") or {})
    summary = dict(document.get("summary") or {})
    findings_sections = list(clinical_report.get("findings_sections") or [])
    impression = list(document.get("impression") or [])
    disclaimers = list(document.get("disclaimers") or [])

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_escape(case_header.get("title") or document.get("title") or "Cervical Spine MRI Analysis Report")}</title>
    <style>{_base_css()}</style>
  </head>
  <body>
    <section class="page">
      <div class="eyebrow">Radiology-Style Summary</div>
      <h1>{_escape(case_header.get("title") or document.get("title") or "Cervical Spine MRI Analysis Report")}</h1>
      <div class="header-grid">
        {_meta_cell("Exam", clinical_report.get("exam"))}
        {_meta_cell("Technique", clinical_report.get("technique"))}
        {_meta_cell("Case ID", case_header.get("case_id"))}
        {_meta_cell("Submitted", case_header.get("submitted_at"))}
        {_meta_cell("Source File", case_header.get("source_filename"))}
        {_meta_cell("Patient Context", case_header.get("patient_summary"))}
        {_meta_cell("Summary", _render_summary(summary))}
      </div>

      <h2>Findings</h2>
      {_render_findings_sections(findings_sections)}

      <h2>Impression</h2>
      {_render_ordered_list(impression) if impression else "<p>No impression bullets generated.</p>"}

      <h2>Disclaimers</h2>
      {_render_unordered_list(disclaimers) if disclaimers else "<p>No disclaimers provided.</p>"}
    </section>
  </body>
</html>
"""


def render_technical_report_html(document: dict[str, Any]) -> str:
    """Render the explainability-focused technical report.

    This variant keeps the appendix, raw structured outputs, provenance, and
    quality notes for AI explainability and auditability.
    """
    case_header = dict(document.get("case_header") or {})
    clinical_report = dict(document.get("clinical_report") or {})
    findings = dict(document.get("findings") or {})
    quality_caveats = dict(document.get("quality_caveats") or {})
    appendix = dict(document.get("appendix") or {})
    summary = dict(document.get("summary") or {})

    findings_sections = list(clinical_report.get("findings_sections") or [])
    impression = list(document.get("impression") or [])
    disclaimers = list(document.get("disclaimers") or [])
    table_rows = list(findings.get("table_rows") or [])
    provenance = list(appendix.get("provenance") or [])
    raw_data = dict(appendix.get("raw_data") or {})

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_escape(case_header.get("title") or document.get("title") or "Cervical Spine MRI Analysis Report")} - Technical</title>
    <style>{_base_css()}</style>
  </head>
  <body>
    <section class="page">
      <div class="eyebrow">Automated Research Report</div>
      <h1>{_escape(case_header.get("title") or document.get("title") or "Cervical Spine MRI Analysis Report")}</h1>
      <div class="header-grid">
        {_meta_cell("Exam", clinical_report.get("exam"))}
        {_meta_cell("Technique", clinical_report.get("technique"))}
        {_meta_cell("Case ID", case_header.get("case_id"))}
        {_meta_cell("Job ID", case_header.get("job_id"))}
        {_meta_cell("Submitted", case_header.get("submitted_at"))}
        {_meta_cell("Source File", case_header.get("source_filename"))}
        {_meta_cell("Patient Context", case_header.get("patient_summary"))}
        {_meta_cell("Summary", _render_summary(summary))}
      </div>

      <h2>Findings</h2>
      {_render_findings_sections(findings_sections)}

      <h2>Impression</h2>
      {_render_ordered_list(impression) if impression else "<p>No impression bullets generated.</p>"}

      <h2>Disclaimers</h2>
      {_render_unordered_list(disclaimers) if disclaimers else "<p>No disclaimers provided.</p>"}
    </section>

    <section class="page">
      <div class="eyebrow">Technical Appendix</div>
      <h1>Explainability Appendix</h1>

      <h2>Structured Findings Table</h2>
      {_render_findings_table(table_rows)}

      <h2>Quality And Caveats</h2>
      {_render_quality_caveats(quality_caveats)}

      <h2>Threshold Provenance</h2>
      {_render_provenance_table(provenance)}

      <h2>Raw Structured Data</h2>
      {_render_raw_data(raw_data)}
    </section>
  </body>
</html>
"""


def render_report_html(document: dict[str, Any]) -> str:
    """Backward-compatible alias for the technical/explainability variant."""
    return render_technical_report_html(document)


def _base_css() -> str:
    return """
      :root {
        --ink: #162033;
        --muted: #566173;
        --line: #d7dee8;
        --panel: #f6f8fb;
        --accent: #12395b;
        --warn: #8a5a00;
        --flag: #7a1f1f;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: #eef2f7;
        color: var(--ink);
        font: 14px/1.45 "Georgia", "Times New Roman", serif;
      }
      .page {
        width: 8.5in;
        min-height: 11in;
        margin: 24px auto;
        background: white;
        padding: 0.7in 0.75in 0.8in;
        box-shadow: 0 18px 40px rgba(14, 30, 52, 0.14);
      }
      .page + .page {
        page-break-before: always;
      }
      .eyebrow {
        font: 600 11px/1.2 "Helvetica Neue", Arial, sans-serif;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 8px;
      }
      h1 {
        font: 700 24px/1.15 "Helvetica Neue", Arial, sans-serif;
        margin: 0 0 14px;
        color: var(--accent);
      }
      h2 {
        font: 700 13px/1.2 "Helvetica Neue", Arial, sans-serif;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin: 22px 0 8px;
        color: var(--accent);
      }
      h3 {
        font: 700 14px/1.2 "Helvetica Neue", Arial, sans-serif;
        margin: 16px 0 6px;
      }
      p {
        margin: 0 0 10px;
      }
      .header-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px 18px;
        padding: 14px 16px;
        background: linear-gradient(180deg, #fbfcfe 0%, #f2f6fb 100%);
        border: 1px solid var(--line);
        border-radius: 10px;
      }
      .meta-label {
        font: 600 10px/1.2 "Helvetica Neue", Arial, sans-serif;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 3px;
      }
      .meta-value {
        font: 14px/1.35 "Helvetica Neue", Arial, sans-serif;
      }
      .section-block {
        margin-top: 14px;
      }
      .section-body {
        white-space: pre-line;
      }
      ol {
        margin: 8px 0 0 20px;
        padding: 0;
      }
      li {
        margin: 0 0 6px;
      }
      ul {
        margin: 8px 0 0 18px;
        padding: 0;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
      }
      th, td {
        border: 1px solid var(--line);
        padding: 7px 8px;
        vertical-align: top;
        text-align: left;
      }
      th {
        background: var(--panel);
        font: 600 11px/1.2 "Helvetica Neue", Arial, sans-serif;
        letter-spacing: 0.05em;
        text-transform: uppercase;
      }
      .pill {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 999px;
        background: #edf2f7;
        font: 600 11px/1.2 "Helvetica Neue", Arial, sans-serif;
        color: var(--muted);
      }
      .pill-flag {
        background: #f9e8e8;
        color: var(--flag);
      }
      .pill-review {
        background: #fff5df;
        color: var(--warn);
      }
      .pill-within {
        background: #e6f5ea;
        color: #21623c;
      }
      .mono {
        font-family: "SFMono-Regular", Menlo, Consolas, monospace;
        font-size: 12px;
      }
      pre {
        margin: 8px 0 0;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid var(--line);
        background: #fbfcfe;
        overflow-x: auto;
        white-space: pre-wrap;
      }
      .small {
        color: var(--muted);
        font-size: 12px;
      }
      @media print {
        body { background: white; }
        .page {
          margin: 0;
          width: auto;
          min-height: auto;
          box-shadow: none;
          padding: 0.5in 0.6in 0.65in;
        }
      }
    """


def _render_findings_sections(sections: list[dict[str, Any]]) -> str:
    blocks = []
    for section in sections:
        heading = _escape(section.get("heading") or "Section")
        body = _escape(section.get("body") or "")
        blocks.append(
            f'<div class="section-block"><h3>{heading}</h3><p class="section-body">{body}</p></div>'
        )
    return "".join(blocks) or "<p>No findings sections generated.</p>"


def _render_ordered_list(items: list[str]) -> str:
    return "<ol>" + "".join(f"<li>{_escape(item)}</li>" for item in items) + "</ol>"


def _render_unordered_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_escape(item)}</li>" for item in items) + "</ul>"


def _render_findings_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No structured findings rows available.</p>"

    body = []
    for row in rows:
        pill = _status_pill(row.get("status"), row.get("severity"))
        qflags = ", ".join(row.get("quality_flags") or []) or "None"
        body.append(
            "<tr>"
            f"<td>{_escape(row.get('level'))}</td>"
            f"<td>{_escape(row.get('display_name'))}</td>"
            f"<td>{_escape(_format_value(row.get('value'), row.get('unit')))}</td>"
            f"<td>{pill}</td>"
            f"<td>{_escape(qflags)}</td>"
            f"<td>{_escape(row.get('caveat'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Level</th><th>Measurement</th><th>Value</th><th>Status</th><th>Quality Flags</th><th>Caveat</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _render_quality_caveats(section: dict[str, Any]) -> str:
    measurement_notes = list(section.get("measurement_notes") or [])
    component_notes = list(section.get("component_notes") or [])
    general_caveats = list(section.get("general_caveats") or [])

    parts = []
    if measurement_notes:
        items = [
            f"{note.get('level')}: {note.get('measurement')} [{', '.join(note.get('quality_flags') or [])}]"
            for note in measurement_notes
        ]
        parts.append("<h3>Measurement Notes</h3>" + _render_unordered_list(items))
    if component_notes:
        items = [f"{note.get('component')}: {note.get('error')}" for note in component_notes]
        parts.append("<h3>Component Notes</h3>" + _render_unordered_list(items))
    if general_caveats:
        parts.append("<h3>General Caveats</h3>" + _render_unordered_list([str(item) for item in general_caveats]))
    return "".join(parts) or "<p>No quality or caveat notes recorded.</p>"


def _render_provenance_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No provenance rows available.</p>"

    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{_escape(row.get('display_name'))}</td>"
            f"<td>{_escape(row.get('tag'))}</td>"
            f"<td class=\"small\">{_escape(row.get('citation'))}</td>"
            f"<td class=\"small\">{_escape(row.get('provenance_note'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Measurement</th><th>Tag</th><th>Citation</th><th>Note</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _render_raw_data(raw_data: dict[str, Any]) -> str:
    parts = []
    for key in ("components", "measurements", "flags"):
        value = raw_data.get(key)
        pretty = json.dumps(value, indent=2, sort_keys=True)
        parts.append(f"<h3>{_escape(key.title())}</h3><pre class=\"mono\">{html.escape(pretty)}</pre>")
    return "".join(parts)


def _meta_cell(label: Any, value: Any) -> str:
    return (
        "<div>"
        f"<div class=\"meta-label\">{_escape(label)}</div>"
        f"<div class=\"meta-value\">{_escape(value)}</div>"
        "</div>"
    )


def _render_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    return (
        f"{summary.get('measurement_row_count', 0)} rows, "
        f"{summary.get('flagged_measurement_count', 0)} flagged, "
        f"{summary.get('syndrome_count', 0)} syndromes"
    )


def _status_pill(status: Any, severity: Any) -> str:
    status_text = str(status or "unknown")
    severity_text = f" - {severity}" if severity else ""
    cls = "pill"
    if status_text == "outside_reference":
        cls += " pill-flag"
    elif status_text in {"review_only", "not_assessable"}:
        cls += " pill-review"
    elif status_text == "within_reference":
        cls += " pill-within"
    return f'<span class="{cls}">{_escape(status_text + severity_text)}</span>'


def _format_value(value: Any, unit: Any) -> str:
    if value is None:
        return "unavailable"
    unit = str(unit or "").strip()
    return f"{value} {unit}".strip()


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))
