"""HTML rendering helpers for structured reports."""


def render_report_html(document: dict) -> str:
    title = document.get("case") or "Cervical Spine MRI Analysis Report"
    return f"<html><body><h1>{title}</h1></body></html>"
