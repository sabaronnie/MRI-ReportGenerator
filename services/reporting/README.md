# Reporting Service

This package is the report-generation layer that sits after interpretation.

Planned responsibilities:

- normalize interpreted findings into report sections
- render HTML
- render PDF or another submission-friendly artifact

Current v1 implementation:

- `builder.py` consumes the post-interpretation handoff contract and emits a
  normalized report document for renderers
- `render_html.py` and `render_pdf.py` remain lightweight scaffolds for now

Input contract:

- Reporting should consume the post-interpretation JSON contract documented in
  [`../interpretation/REPORTING_HANDOFF_CONTRACT.md`](../interpretation/REPORTING_HANDOFF_CONTRACT.md).
- Reporting should derive findings tables, impression bullets, and final renderable
  artifacts from that payload rather than depending directly on measurement-component
  internals.

Current output document shape from `build_report_document(...)`:

- `report_version`
- `source_contract_version`
- `title`
- `case`
- `summary`
- `findings`
- `impression`
- `quality_notes`
- `disclaimers`
- `metadata`
- `appendix`
