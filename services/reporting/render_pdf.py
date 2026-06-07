"""PDF rendering scaffold for structured reports."""

from .render_html import render_report_html


def render_report_pdf(document: dict) -> bytes:
    """Placeholder PDF renderer until the final backend is wired.

    For now, this returns the print-ready HTML bytes that the eventual PDF engine
    would consume. Once a real HTML-to-PDF backend is chosen, this function
    should swap the final line for the renderer invocation.
    """
    html = document.get("html") or render_report_html(document)
    return html.encode("utf-8")
