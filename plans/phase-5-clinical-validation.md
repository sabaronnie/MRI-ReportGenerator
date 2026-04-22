# Phase 5 — Clinical Validation

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

Validation against radiologist ground truth. Separate workstream, runs once.

### 5.1 Internal segmentation check (automated)

**Method:** Run TotalSpineSeg on all 481 Duke expert-annotated cases. Compare the TotalSpineSeg output to Duke's own binary vertebra + disc masks.

**Metric:** Dice coefficient at the semantic level (TotalSpineSeg gives per-level labels, Duke gives binary vertebra label — we threshold TotalSpineSeg to binary-any-vertebra for comparison).

**Acceptance:** Mean Dice ≥ 0.85 across the 481 cases.

**Code asset:** Custom, ~100 lines (Dice computation + bulk-run harness).

### 5.2 Distribution plausibility check (automated)

**Method:** Run the full pipeline end-to-end over all 1,255 Duke cases. For every measurement, plot the distribution.

**Pass/fail:**
- ≥ 90% of outputs fall within published literature range (the literature range for each measurement is documented in Appendix C)
- No bimodal distributions at unexpected values (would indicate a bug)
- Outliers (value > 3 SD from cohort mean) are examined manually — some are real pathology, others are segmentation failures

**Output:** A one-page distribution report per measurement with literature range overlaid.

### 5.3 AUBMC radiologist agreement (manual, external)

**Method:** Separate collaboration with AUB Medical Center radiology. Target workflow:

1. Select 20–30 cases from Duke spanning the severity spectrum (normal, mild, moderate, severe findings — can use our own pipeline outputs to stratify).
2. AUBMC radiologist (ideally 2 raters) measures manually using ITK-SNAP or institutional PACS tools:
   - Canal AP at each cervical level
   - Vertebral body AP and SI (middle)
   - C2–C7 Cobb angle
   - Presence/absence of myelomalacia (subjective)
3. Compare pipeline output to radiologist measurements.

**Metrics:**
- ICC (intraclass correlation) for continuous measurements — target ≥ 0.75
- Bland-Altman plots with limits of agreement
- Cohen's kappa for categorical (myelomalacia yes/no, stenosis severity) — target ≥ 0.6
- MAE on Cobb angle — target ≤ 5°

**Deliverable:** A validation report suitable for inclusion in a future publication. This is also the deliverable that makes the pipeline defensible as "could be used clinically."

**Status:** Plan-only for v1. Execution depends on AUBMC collaboration which is a separate workstream.

**Reference workflow:** Horáková 2022 (*Quant Imaging Med Surg*) documents exactly this kind of radiologist-vs-SCT validation — we follow the same design.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
