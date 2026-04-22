# Phase 6 — Report Generation

**Owner:** TBD
**Reviewer:** TBD
**Status:** v1 content imported — under team review
**Last updated:** 2026-04-22 by Andrew (initial import from master_plan_v1.md)

---

## What a reviewer should check

- Does the method chosen actually work on Duke's segmentation masks?
- Are the alternatives rejected for the right reasons?
- Is any repo/reference missing? Add it if so.
- Does anything here conflict with another phase? Flag it.
- Is anything unclear? Mark it as an open question at the bottom.

---

### 6.1 Per-level findings table

**Method:** The report's primary content is a table indexed by cervical level, with columns for every measurement plus severity tags. Example row:

| Level | VB AP | VB SI (mid) | Disc SI | DHI | Canal AP | Cord AP | SAC | Torg-Pavlov | Cobb (seg.) |
|---|---|---|---|---|---|---|---|---|---|
| C5 | 19.2 mm | 14.0 mm | 4.2 mm | 0.30 ⚠ | **9.8 mm** ⚠⚠ | 7.1 mm | **2.7 mm** ⚠⚠ | 0.51 ⚠ | −2° |

Severity rendered as text annotations (*normal / mild / moderate / severe / critical*) or color where supported.

### 6.2 Overall impressions section

**Method:** Rule-based text generation from the syndrome flags in 4.3. Templates like:

- "Most stenotic level: C5 (canal AP 9.8 mm — severe)."
- "SAC reduced to 2.7 mm at C5, suggesting cord compression risk."
- "C2–C7 Cobb angle −2° — loss of lordosis on supine MRI (note: supine imaging typically under-measures lordosis vs standing radiographs)."
- "Pattern consistent with possible cervical myelopathy at C5; clinical correlation required."

Each statement is traceable back to the specific measurement that triggered it.

### 6.3 Annotated figure

**Method:** Render the chosen mid-sagittal slice with overlays:
- Rotated rectangles for each vertebra (color-coded by label)
- Disc masks
- Canal boundary
- Cord (from SCT, projected onto sagittal)
- Lines showing Cobb angle measurement
- Level labels (C2, C3, …)

Output as PNG embedded in the final PDF.

**Code asset:** `matplotlib` with `nilearn` overlay utilities. ~150 lines.

### 6.4 Report format

**Method:**
- Primary output: **PDF** (self-contained, universal). Generated via `reportlab` or `weasyprint` from HTML template.
- Secondary output: **DOCX** via `python-docx` for editability.
- Template: radiology report convention — Findings (per-level table) → Impressions (rule-generated summary) → Appendix (methodology, caveats, thresholds used).

**Mandatory disclaimers included in every report:**
- "This is a research tool, not a medical device. Not for clinical diagnosis."
- "Measurements acquired on supine MRI; functional radiographs may differ."
- "Demographic percentiles are relative to a clinical cohort (Duke CSpineSeg), not healthy volunteers."
- Where applicable: "Signal-based anomalies flagged for physician review only; not a diagnosis."

**Code asset:** Custom templating, ~200 lines.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
