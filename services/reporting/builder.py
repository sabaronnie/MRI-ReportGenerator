"""Helpers for converting interpreted findings into a report-friendly document."""


def build_report_document(payload: dict) -> dict:
    """Return a thin normalized document scaffold for downstream rendering."""
    return {
        "case": payload.get("case"),
        "impression": payload.get("impression", []),
        "findings": payload.get("findings", []),
        "metadata": payload.get("metadata", {}),
    }
