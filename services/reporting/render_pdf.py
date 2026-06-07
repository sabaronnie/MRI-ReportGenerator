"""PDF rendering scaffold for structured reports."""


def render_report_pdf(document: dict) -> bytes:
    """Placeholder PDF renderer until the final backend is wired."""
    html = document.get("html", "")
    return html.encode("utf-8")
