# Reporting Service

This package is the report-generation layer that sits after assessement.

Planned responsibilities:

- normalize assessed findings into report sections
- render HTML
- render PDF or another submission-friendly artifact

Current v1 implementation:

- `builder.py` consumes the post-assessement handoff contract and emits a
  normalized report document for renderers
- `render_html.py` renders two variants:
  - user-facing clinical/radiology-style report
  - technical/explainability report
- `render_pdf.py` exposes matching PDF entry points that currently return the
  print-ready HTML bytes their eventual PDF backend should consume

Input contract:

- Reporting should consume the post-assessement JSON contract documented in
  [`../assessement/REPORTING_HANDOFF_CONTRACT.md`](../assessement/REPORTING_HANDOFF_CONTRACT.md).
- Reporting should derive findings tables, impression bullets, and final renderable
  artifacts from that payload rather than depending directly on measurement-component
  internals.

Current output document shape from `build_report_document(...)`:

- `report_version`
- `source_contract_version`
- `title`
- `case_header`
- `case`
- `summary`
- `findings`
- `impression`
- `quality_caveats`
- `quality_notes`
- `disclaimers`
- `metadata`
- `appendix`

The normalized document model is intended to contain:

- a radiology-style main report (`clinical_report`)
- case header
- findings table rows
- impression bullets
- quality / caveat sections
- disclaimers
- a technical appendix / provenance section for explainability

Output variants:

- Clinical report:
  user-targeted PDF/HTML with findings, impression, and disclaimers only
- Technical report:
  explainability-targeted PDF/HTML with structured findings table, quality notes,
  threshold provenance, and raw structured data appendix
