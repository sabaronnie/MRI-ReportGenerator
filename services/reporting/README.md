# Reporting Service

This package is the report-generation layer that sits after interpretation.

Planned responsibilities:

- normalize interpreted findings into report sections
- render HTML
- render PDF or another submission-friendly artifact

The current files are scaffolds so the final architecture is visible in the repo.

Input contract:

- Reporting should consume the post-interpretation JSON contract documented in
  [`../interpretation/REPORTING_HANDOFF_CONTRACT.md`](../interpretation/REPORTING_HANDOFF_CONTRACT.md).
- Reporting should derive findings tables, impression bullets, and final renderable
  artifacts from that payload rather than depending directly on measurement-component
  internals.
