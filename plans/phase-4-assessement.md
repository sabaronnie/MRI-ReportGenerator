# Phase 4 — Interpretation

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

Interpretation turns raw measurements into flags, severity tags, and syndrome patterns. No new measurements are computed here.

### 4.1 Threshold tables from literature

**Method:** A central `thresholds.py` module defines threshold functions per measurement. Each threshold function returns `(severity, reference)` where severity ∈ {normal, mild, moderate, severe, critical}.

**Example for canal AP (from Phase 3A.7):**
```python
def canal_ap_severity(value_mm):
    if value_mm >= 13:  return ("normal",   "Ulbrich 2014, Thelen 2019")
    if value_mm >= 10:  return ("mild",     "Ulbrich 2014")
    if value_mm >= 7:   return ("moderate", "Ulbrich 2014")
    return ("severe",   "Ulbrich 2014")
```

**Source literature for all thresholds** (expanded in Appendix C):
- Canal AP: Ulbrich 2014 (Radiology), Thelen 2019 (PLOS One, SHIP)
- Vertebral body dimensions: Yukawa 2018, Thelen 2019 (SHIP)
- Torg-Pavlov ratio: Torg 1987; Pavlov 1987
- Cobb angle: Yukawa 2018 (N=1,200 asymptomatic), Martini 2021 (review) — adjusted for supine MRI vs standing radiographs per Yu 2021
- SAC: <3mm = high compression risk (Fehlings 2015, Nouri 2016)
- DHI: <0.3 cervical = narrowing (Farfan, Frobin)
- MSCC: normalized via SCT's built-in Valošek 2024 database

**Important:** Thresholds often originate from radiograph or CT studies. We explicitly annotate each with its source modality so the team can decide to recalibrate against Duke distributions later if needed.

### 4.2 Per-measurement flagging

**Method:** For every measurement in the merged result dict, call the corresponding threshold function, attach the severity tag and the literature reference. Output structure:

```python
{
  "canal_AP": {
    "C5": {"value_mm": 9.8, "severity": "severe", "ref": "Ulbrich 2014"},
    "C6": {"value_mm": 12.1, "severity": "mild", "ref": "Ulbrich 2014"},
    ...
  },
  ...
}
```

This structure is what the Report (Phase 6) renders.

### 4.3 Syndrome indicator flags (Group 6 consolidated)

**Myelopathy indicator** (flag as possible cervical myelopathy if all present):
- Canal AP < 10 mm at any level, AND
- SAC < 3 mm at same level, AND
- Cord signal anomaly (3C.1) at same level OR cord AP reduced > 2 SD vs adjacent levels

**Radiculopathy indicator** (more speculative; foraminal dimensions aren't measured directly in our pipeline):
- DHI reduced (< 0.3) at a level, AND
- Disc AP width > mean(VB_above_AP, VB_below_AP) + 2 mm (disc bulge signal)

Both are advisory only. The report says *"pattern consistent with possible myelopathy; clinical correlation required"*, never diagnostic.

**Code asset:** Custom rule engine, ~100 lines.

### 4.4 Demographic percentile comparison

**Method:** Two-track approach:

- **Cord measurements (3B.2, 3B.3, 3B.4):** Use SCT's `-normalize-hc` flag, which calls Valošek 2024's healthy-controls database with patient age and sex. Free infrastructure, published, cited. Nothing we build.

- **Vertebral/canal measurements (3A.*):** Build our own percentile curves from Duke CSpineSeg (N=1,232 with age + sex). Steps:
  1. Run the full Phase 3A pipeline over all 1,232 Duke cases
  2. Stratify by age decade (20–29, 30–39, 40–49, 50–59, 60–69, 70+) × sex
  3. For each (measurement, level, stratum), compute quantile regression or empirical percentiles (2.5th, 25th, 50th, 75th, 97.5th)
  4. Store as a JSON lookup table
  5. At inference, report each measurement as "X mm (N-th percentile for age-stratum Y)"

**Important honesty caveat:** Duke is a **clinical** cohort, not healthy volunteers. Many patients have pathology. So our percentile curves represent "the clinical cervical MRI population" rather than "healthy controls." This is documented in every output and is fine for relative comparison but does not replace the Valošek 2024 normative database that SCT uses for cord.

**Code asset:** Custom, ~300 lines (bulk-processing + percentile computation).

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
