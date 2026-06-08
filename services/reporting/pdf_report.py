"""Branded clinical PDF for the cervical-spine report (fpdf2, pure-Python).

Consumes the normalized report document from `build_report_document` and lays out a
polished, print-ready clinical report: logo header, case + patient block, findings
narrative + table, impression, caveats, and disclaimers. No system dependencies.
"""

from __future__ import annotations

import os
import re
from typing import Any

from fpdf import FPDF

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_LOGO = os.path.join(_ASSETS, "logo.png")

# Brand palette (petrol teal) + neutrals.
TEAL = (17, 94, 103)
TEAL_SOFT = (235, 245, 246)
INK = (28, 33, 42)
MUTED = (112, 122, 132)
RULE = (214, 220, 224)
ROSE = (180, 45, 58)
ROSE_SOFT = (251, 238, 240)
AMBER = (164, 104, 12)

_STATUS = {
    "outside_reference": ("Flagged", ROSE, ROSE_SOFT),
    "review_only": ("Review", AMBER, (252, 247, 235)),
    "within_reference": ("Normal", (33, 120, 90), (236, 247, 242)),
    "not_interpretable": ("N/A", MUTED, (242, 244, 246)),
}

USABLE_W = 170.0  # A4 (210mm) minus 20mm margins each side


def _level_key(level: str) -> tuple[int, int]:
    """Order findings head-to-toe and keep all measurements at one level together.
    Single levels (C5) group as (5,0); adjacent disc/segmental pairs (C4-C5) slot
    just below their upper body as (4,1); global spans (Cobb C3-C7) sort to the end."""
    nums = [int(x) for x in re.findall(r"C(\d+)", level or "")]
    if not nums:
        return (99, 0)
    if len(nums) == 1:
        return (nums[0], 0)
    a, b = nums[0], nums[1]
    if b - a == 1:
        return (a, 1)
    return (98, a)


def _t(text: Any, limit: int | None = None) -> str:
    """Stringify + latin-1-safe (fpdf core fonts) + optional truncate."""
    s = "" if text is None else str(text)
    s = s.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.encode("latin-1", "replace").decode("latin-1")
    if limit and len(s) > limit:
        s = s[: limit - 1] + "."
    return s


class _Report(FPDF):
    def header(self) -> None:
        if os.path.exists(_LOGO):
            try:
                self.image(_LOGO, x=20, y=11, w=13)
            except Exception:
                pass
        self.set_xy(36, 12)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*INK)
        self.cell(0, 6, "Cervical MRI", ln=1)
        self.set_xy(36, 18.5)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, "REPORTING", ln=1)
        # right-aligned label
        self.set_xy(120, 14)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*TEAL)
        self.cell(70, 5, "CLINICAL REPORT", align="R")
        # teal rule
        self.set_draw_color(*TEAL)
        self.set_line_width(0.6)
        self.line(20, 27, 190, 27)
        self.set_y(33)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(20, self.get_y(), 190, self.get_y())
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.cell(140, 4, "Research-use structured interpretation - not a diagnosis. Clinical correlation required.")
        self.cell(30, 4, f"Page {self.page_no()}", align="R")

    # -- section helpers --
    def heading(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*TEAL)
        self.cell(0, 6, _t(text), ln=1)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(2)

    def body(self, text: str, size: float = 9.5, color=INK) -> None:
        self.set_x(20)
        self.set_font("Helvetica", "", size)
        self.set_text_color(*color)
        self.multi_cell(USABLE_W, 5, _t(text))

    def bullets(self, items: list, size: float = 9.5) -> None:
        self.set_font("Helvetica", "", size)
        for it in items:
            y0 = self.get_y()
            self.set_xy(20, y0)
            self.set_text_color(*TEAL)
            self.cell(5, 5, chr(149))  # bullet
            self.set_xy(25, y0)
            self.set_text_color(*INK)
            self.multi_cell(USABLE_W - 5, 5, _t(it))
            self.set_y(self.get_y() + 0.5)


def _kv_block(pdf: _Report, pairs: list[tuple[str, str]]) -> None:
    pdf.set_font("Helvetica", "", 9)
    y = pdf.get_y()
    for label, value in pairs:
        if not value:
            continue
        pdf.set_xy(20, y)
        pdf.set_text_color(*MUTED)
        pdf.cell(30, 5, _t(label))
        pdf.set_xy(52, y)
        pdf.set_text_color(*INK)
        pdf.multi_cell(USABLE_W - 32, 5, _t(value))
        y = pdf.get_y() + 0.5
    pdf.set_y(y)


def _summary_strip(pdf: _Report, summary: dict) -> None:
    counts = summary.get("status_counts", {}) or {}
    chips = [
        (f"{summary.get('measurement_row_count', 0)} measurements", TEAL_SOFT, TEAL),
        (f"{summary.get('flagged_measurement_count', 0)} flagged", ROSE_SOFT, ROSE),
        (f"{summary.get('syndrome_count', 0)} syndromes", (242, 244, 246), MUTED),
        (f"{counts.get('review_only', 0)} review-only", (252, 247, 235), AMBER),
    ]
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 8)
    x = 20
    for label, bg, fg in chips:
        w = pdf.get_string_width(label) + 8
        pdf.set_fill_color(*bg)
        pdf.set_text_color(*fg)
        pdf.set_xy(x, pdf.get_y())
        pdf.cell(w, 6, _t(label), align="C", fill=True)
        x += w + 4
    pdf.ln(9)


def _findings_table(pdf: _Report, rows: list[dict]) -> None:
    widths = [16, 86, 26, 42]
    headers = ["Level", "Measurement", "Value", "Status"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, _t(h))
    pdf.ln(6)
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    for r in rows:
        status = r.get("status", "")
        label, fg, bg = _STATUS.get(status, ("-", MUTED, (255, 255, 255)))
        y0 = pdf.get_y()
        if bg != (255, 255, 255):
            pdf.set_fill_color(*bg)
            pdf.rect(20, y0 - 0.5, USABLE_W, 6.5, style="F")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*INK)
        pdf.set_xy(20, y0)
        pdf.cell(widths[0], 6, _t(r.get("level", "-")))
        pdf.cell(widths[1], 6, _t(r.get("display_name") or r.get("measurement"), limit=58))
        val = r.get("value")
        unit = r.get("unit") or ""
        pdf.cell(widths[2], 6, _t(f"{val} {unit}".strip() if val is not None else "-"))
        pdf.set_text_color(*fg)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(widths[3], 6, _t(label))
        pdf.ln(6.5)
    pdf.set_text_color(*INK)


def build_clinical_pdf(document: dict) -> bytes:
    pdf = _Report(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 33, 20)
    pdf.add_page()

    ch = document.get("case_header", {}) or {}
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.multi_cell(USABLE_W, 8, _t(document.get("title") or ch.get("title") or "Cervical Spine MRI Analysis Report"))
    pdf.ln(1)

    _kv_block(pdf, [
        ("Case ID", ch.get("case_id", "")),
        ("Exam", ch.get("exam", "")),
        ("Patient", ch.get("patient_summary", "")),
        ("Submitted", ch.get("submitted_at", "")),
        ("Source", ch.get("source_filename", "")),
    ])
    _summary_strip(pdf, document.get("summary", {}) or {})

    clinical = document.get("clinical_report", {}) or {}
    sections = clinical.get("findings_sections") or []
    rows = (document.get("findings", {}) or {}).get("table_rows") or []

    pdf.heading("Findings")
    if sections:
        for s in sections:
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*INK)
            pdf.cell(0, 5, _t(s.get("heading", "")), ln=1)
            pdf.body(s.get("body", ""))
            pdf.ln(1.5)
    if rows:
        rows = sorted(rows, key=lambda r: _level_key(r.get("level", "")))
        pdf.ln(1)
        _findings_table(pdf, rows)

    impression = clinical.get("impression") or document.get("impression") or []
    if impression:
        pdf.heading("Impression")
        pdf.bullets(impression)

    caveats = (document.get("quality_caveats", {}) or {}).get("general_caveats") or []
    if caveats:
        pdf.heading("Quality & caveats")
        pdf.bullets(caveats, size=8.5)

    disclaimers = document.get("disclaimers") or []
    if disclaimers:
        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(*MUTED)
        for d in disclaimers:
            pdf.set_x(20)
            pdf.multi_cell(USABLE_W, 4, _t(d))

    out = pdf.output()
    return bytes(out)
