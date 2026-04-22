# Research Notes — Andrew — Groups 5 + 6

**Owner:** Andrew (`@andrew2119`)
**Scope:** Group 5 (signal-based abnormal finding detection) + Group 6 (clinical interpretation & report integration)
**Status:** in progress — week 1 research
**Source of truth for measurement definitions:** `plans/measurement_components.pdf` (AUBMC radiologist spec)

This file is for parallel research notes. It will be consolidated later into `phase-3c-signal-based.md`, `phase-4-interpretation.md`, and `phase-6-report-generation.md`.

---

## Group 5 — Abnormal Finding Detection (Signal-Based)

### 5.1 Myelomalacia Detection (T2-MI / Weber 2023)

**Goal:** detect abnormally high T2 signal within the spinal cord mask → flag as "possible cord injury / gliosis, physician review."

**Approach options to research:**
- Threshold-based: signal intensity within cord mask vs. CSF reference at the same level (Weber et al. 2023 method).
- Within-patient normalization: compare cord signal at suspected level vs. cord signal at unaffected adjacent levels.

**Key references to read:**
- Weber et al. 2023 — T2 Myelopathy Index (primary method)
- Horáková et al. 2022 — SCT compression detection (related approach)

**Open questions:**
- _(append as research progresses)_

---

### 5.2 Fracture Detection

**Goal:** flag vertebral body shape deformity (compression, burst, wedge).

**Approach options:**
- Geometric: compare actual VB shape to expected shape from neighboring levels.
- Signal-based: bone marrow edema on T2/STIR.

**Decision:** likely **defer** signal-based (needs T1+STIR which we don't input). Geometric only, as a "shape deviation flag." Confirm scope with team.

---

### 5.3 Tumor / Mass Detection

**Per AUBMC recommendation:** scope as "abnormal signal regions flagged for physician review," not classification. Frame in report as `"region of abnormal signal at C5; clinical correlation required"`.

---

### 5.4 Post-Surgical Scar Detection

**Status:** likely defer entirely — typically requires gadolinium-enhanced sequences which are out of scope (sagittal T2 only).

---

## Group 6 — Clinical Interpretation Layer

### 6.1 Radiculopathy Indicators

**Combines:** disc measurements (2.x) + foraminal proxies → flag pattern, never diagnose.

**Output wording (per CLAUDE.md medical AI rules):**
`"Findings consistent with possible C5–C6 radiculopathy; clinical correlation required."`

---

### 6.2 Myelopathy Indicators

**Combines:** central canal stenosis (3.1) + reduced SAC (3.3) + cord signal changes (5.1).
- Threshold table needs literature review (DCM diagnostic criteria).
- Combine via rule-based scoring (e.g., 2 of 3 thresholds crossed → flag).

---

### 6.3 Per-Level Structured Report

**This defines the report schema that everyone writes to.** Critical cross-slot dependency.

Per level (C2–C3 through C6–C7), the report contains:
- Vertebral body dimensions (from Ronnie — Group 1)
- Disc dimensions (from Mohammad — Group 2)
- Canal AP diameter (from Ronnie — Group 3)
- Cord AP diameter (from Ronnie — Group 3)
- SAC (derived)
- Torg-Pavlov ratio (derived)
- Cobb / segmental angle (from Mohammad — Group 4)
- Any flags (myelomalacia from 5.1, fracture from 5.2, etc.)

**TODO:** publish a JSON schema for the per-level data structure so Ronnie + Mohammad write to it directly.

---

### 6.4 Demographic Percentile Comparison

**Approach:** quantile regression on Duke CSpineSeg (age, sex as inputs). For each measurement, report patient value + percentile.

Example output: `"Canal AP at C5: 11.2mm (12th percentile for 55-year-old male)."`

**Open questions:**
- Train one quantile regression per measurement, or a multi-output model?
- What percentile thresholds trigger a flag (e.g., <10th)?
- Cord percentiles: use SCT's `-normalize-hc` instead of training our own.

---

## Cross-slot dependencies (track here)

| Dependency | I need from | Status |
|---|---|---|
| Vertebra coords (for context in report layout) | Ronnie | not yet defined |
| Disc dimensions (for report 6.3) | Mohammad | not yet defined |
| Canal/cord measurements (for 6.2 myelopathy logic + 6.3 report) | Ronnie | not yet defined |
| Cobb / segmental angles (for 6.3 report) | Mohammad | not yet defined |

---

## Session notes

(Append by date. Don't delete old notes.)

- 2026-04-22 — Andrew: file created. Beginning lit review for 5.1 (Weber 2023) and 6.4 (quantile regression on Duke).
