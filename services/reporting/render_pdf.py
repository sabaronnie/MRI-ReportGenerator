"""PDF rendering for structured reports.

The clinical variant is a real, branded PDF (fpdf2 — see pdf_report.py). The
technical/report variants remain HTML-bytes scaffolds for a future engine.
"""

from __future__ import annotations

from .pdf_report import build_clinical_pdf
from .render_html import (
    render_report_html,
    render_technical_report_html,
)


def render_clinical_report_pdf(document: dict) -> bytes:
    """Render the clinician-facing report as a real, branded PDF."""
    return build_clinical_pdf(document)


def render_technical_report_pdf(document: dict) -> bytes:
    """Return the HTML bytes that the eventual technical PDF engine should consume."""
    html = document.get("technical_html") or render_technical_report_html(document)
    return html.encode("utf-8")


def render_report_pdf(document: dict) -> bytes:
    """Backward-compatible alias for the technical/explainability variant."""
    html = document.get("html") or render_report_html(document)
    return html.encode("utf-8")
