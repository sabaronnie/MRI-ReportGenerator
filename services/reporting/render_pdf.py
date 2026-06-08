"""PDF rendering scaffolds for structured reports."""

from __future__ import annotations

from .render_html import (
    render_clinical_report_html,
    render_report_html,
    render_technical_report_html,
)


def render_clinical_report_pdf(document: dict) -> bytes:
    """Return the HTML bytes that the eventual clinical PDF engine should consume."""
    html = document.get("clinical_html") or render_clinical_report_html(document)
    return html.encode("utf-8")


def render_technical_report_pdf(document: dict) -> bytes:
    """Return the HTML bytes that the eventual technical PDF engine should consume."""
    html = document.get("technical_html") or render_technical_report_html(document)
    return html.encode("utf-8")


def render_report_pdf(document: dict) -> bytes:
    """Backward-compatible alias for the technical/explainability variant."""
    html = document.get("html") or render_report_html(document)
    return html.encode("utf-8")
