# Phase 3C — Signal-based Measurements (experimental)

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

### 3C — Signal-based engine (experimental)

Everything in 3C operates on **raw T2 voxel intensities**, not on segmentation masks. It reads the original input NIfTI (not the segmentation output) and uses segmentation masks as regions of interest to extract intensity statistics.

#### 3C.1 Myelomalacia detection (T2 Myelopathy Index)

**Method:** Based on Weber et al. 2023, *Neuroradiology* ([PMC10497437](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10497437/)). Reported AUC 0.865–0.920.

For each vertebral level C2–C7:
1. Extract cord mask slab covering the level (use SCT cord seg + vertfile).
2. Extract T2 intensities within the cord mask at that level.
3. Compute: mean, std, range, and the T2-MI metric = `range / mean × 100%`.
4. **Normalization strategy:** We use intra-subject normalization (compare each level's T2-MI against the subject's own mean across unaffected-looking levels). This avoids needing an external age-matched normal database, which we don't have. Weber 2023 validated both intra-subject and against age-matched controls; intra-subject is more robust to scanner/protocol variation and is the lower-barrier option.
5. **Flag** levels where T2-MI is >1.5 SD above the patient's own median across other levels.

**Output format:** `"C4: T2-MI = 24.0% (above patient median; possible myelomalacia flagged for review)"`.

**Experimental status:** Output is flagged as *"signal anomaly detected, clinician review required"* — never as "myelomalacia detected." This keeps the pipeline honest about its limits.

**Code asset:** Custom, ~80 lines. No standalone open-source T2-MI implementation found; Weber 2023 describes the algorithm in sufficient detail to reimplement.

#### 3C.2 Cervical disc signal classifier (simplified Pfirrmann)

**Method:** Full 5-grade Pfirrmann grading for **cervical** discs is not well-automated in open-source code ([SpineNet](https://github.com/rwindsor1/SpineNet) is lumbar-only; cervical-specific classifiers don't have a public release). Implementing full Pfirrmann would require:
- Annotated cervical dataset (we don't have one)
- Training a CNN classifier
- Validating against radiologists
- Months of work

**What we do instead:** A 3-class signal classifier based on normalized T2 intensity statistics within each disc mask:
- Class 1 (bright) — mean T2 intensity is > 75th percentile of all patient's discs
- Class 2 (intermediate/gray) — between 25th and 75th percentile
- Class 3 (dark) — < 25th percentile

**Caveat:** This is explicitly *not Pfirrmann grading*. We call it "disc signal class" in the report and flag it as experimental. It gives a crude sense of "this disc is signal-darker than this patient's other discs" which is weakly correlated with degeneration, nothing more.

**Honest alternative:** Defer this entirely and don't ship any disc-degeneration feature in v1. If the team prefers the cleaner option, remove 3C.2 from scope. I've kept it in as a stretch item — low effort, low stakes, flag it as experimental and move on.

**Code asset:** Custom, ~40 lines.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
