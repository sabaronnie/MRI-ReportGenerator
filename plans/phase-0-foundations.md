# Phase 0 — Foundations

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

### 0.1 Project scope in one paragraph

A sagittal-only cervical spine MRI pipeline that takes a T2-weighted NIfTI (or DICOM series) as input, runs deep-learning segmentation to identify vertebrae, discs, canal, and cord, extracts a defined set of geometric and signal-based measurements, compares each against literature-derived thresholds to flag abnormal values, and outputs a structured radiology-style report. Scope is limited to what a clinician gets from sagittal T2 alone — no axial input, no contrast-enhanced sequences, no multi-sequence fusion. Pathology flagging is positioned as "findings for physician review," never as a diagnosis.

### 0.2 Pipeline architecture

```
┌─────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────────┐   ┌────────┐
│  Input  │ → │ Segmentation │ → │ Measurements │ → │ Assessement │ → │ Report │
└─────────┘   └──────────────┘   └──────────────┘   └────────────────┘   └────────┘
    NIfTI        TotalSpineSeg      Geometric +          Threshold             PDF /
    DICOM        + SCT cord         Cord +               flagging vs.          DOCX
                                    Signal               literature             +
                                    engines              + demographic          figure
                                                         percentiles            overlays
```

**Clinical Validation** (Phase 5) is a separate workstream that runs once over a held-out subset with radiologist ground truth to measure system agreement. It is not a runtime stage.

### 0.3 Dataset strategy — Duke CSpineSeg

The Duke CSpineSeg dataset (Zhou et al. 2025, *Scientific Data*) was reviewed in detail. Key facts that shaped our decisions:

- **1,255 sagittal T2 cervical MRI exams from 1,232 patients**
- **481 patients have expert-verified segmentation masks;** remaining ~60% are auto-labeled by the authors' nnU-Net and explicitly flagged by the authors as "weakly labeled"
- **Labels are anatomical only — binary vertebral body (1) and disc (2)**, no per-level classification (C1–C7), no pathology labels, no radiologist measurements
- **Demographics available** (age, sex, race, ethnicity) via `Clinical_manifest_RSNA_20250321.tsv`
- **Imaging metadata available** (echo time, repetition time, slice thickness, spacing, manufacturer)
- The authors explicitly list per-level classification and Pfirrmann grading as **future work**, meaning they are not in the dataset

**Duke's role in this project:**

| Use case | Verdict |
|---|---|
| Segmentation quality check (TotalSpineSeg output vs Duke expert masks, 481 cases) | **YES** — primary use |
| Demographic reference database (build percentile curves for our measurements stratified by age/sex) | **YES** — matches approach of SHIP study (Thelen 2019, *PLOS One*, N=2,453) |
| Pipeline plausibility test (run 1,000+ end-to-end, check output distributions) | **YES** — secondary use |
| Clinical validation of measurements (Cobb angle accuracy, canal diameter accuracy, etc.) | **NO** — Duke has no ground-truth measurements |

**Consequence:** Clinical validation of measurements (Phase 5) requires AUBMC radiologist collaboration on a separate 20–30 case subset. This is non-negotiable; no amount of work on Duke gives us measurement ground truth.

### 0.4 Scope decisions (in/out/experimental)

| Group | Item | Status | One-line reason |
|---|---|---|---|
| 1 | Vertebral body AP width | **Core** | Direct from segmentation mask |
| 1 | Vertebral body SI height (anterior/middle/posterior) | **Core** | Direct from mask; triple extraction enables wedge detection |
| 1 | Spondylolisthesis + Meyerding grade | **Core** | Simple geometry on mask corners |
| 1 | Vertebral T1/T2 signal for osteoporosis | **Deferred** | Requires T1; MRI is not gold standard for osteoporosis |
| 2 | Disc SI height | **Core** | Direct from disc mask |
| 2 | Disc AP width | **Core** | Direct from disc mask |
| 2 | Disc Height Index (derived) | **Core** | Free, derived from 1.2 and 2.1 |
| 2 | Pfirrmann grading (5-class) | **Deferred → replaced by simplified signal classifier (experimental)** | Cervical-specific 5-grade classifier doesn't exist publicly; 3-class T2 signal classifier is tractable |
| 3 | Canal AP diameter | **Core** | Direct from canal mask (TotalSpineSeg label 2) |
| 3 | Spinal cord AP diameter | **Core (via SCT)** | TotalSpineSeg cord unvalidated for compression; use Spinal Cord Toolbox |
| 3 | SAC (space available for cord) | **Core** | Derived from canal AP − cord AP |
| 3 | Torg-Pavlov ratio | **Core** | Derived from canal AP ÷ VB AP |
| 3 | Most stenotic level | **Core** | Trivial post-processing |
| 4 | C2–C7 Cobb angle | **Core** | Geometric computation from endplate lines |
| 4 | Lordosis classification | **Core** | Thresholding on Cobb angle |
| 4 | Segmental angles (C2–C3, C3–C4, …) | **Core** | Same method as Cobb, applied per adjacent pair |
| 5 | Myelomalacia detection (T2-MI) | **Experimental** | Weber et al. 2023 validated method; intra-subject normalization feasible |
| 5 | Fracture detection | **Deferred** | Requires T1+STIR+bone marrow edema analysis |
| 5 | Tumor detection | **Deferred** | Requires own annotated training set + classification model |
| 5 | Post-surgical scar | **Deferred** | Requires gadolinium-enhanced sequences |
| 6 | Radiculopathy indicators | **Core** | Rule-based combination of 3A measurements |
| 6 | Myelopathy indicators | **Core** | Rule-based combination of 3A + 3B + optionally 3C |
| 6 | Per-level structured report | **Core** | Report-generation logic |
| 6 | Demographic percentile comparison | **Core (cord via SCT `-normalize-hc`; others via Duke-built curves)** | SCT provides this free for cord; we build it for vertebral/canal |
| Deferred | Axial canal transverse width | **Deferred** | Requires axial input (second file) |
| Deferred | Facet joint analysis | **Deferred** | Axial input + new segmentation needed |

### 0.5 Success criteria per phase

| Phase | Definition of "done" |
|---|---|
| 1 — Input | Any sagittal T2 cervical MRI (NIfTI or DICOM folder) loads, orientation is detected, voxel spacing recorded, and a QC pass fails fast on bad inputs |
| 2 — Segmentation | TotalSpineSeg runs end-to-end on all 481 Duke expert-labeled cases with Dice ≥ 0.85 against Duke masks (semantic-level match); mid-sagittal slice selection works on ≥ 95% of cases |
| 3 — Measurements | All core measurements computed on every Duke case without crashes; measurement output distributions are plausible (within literature ranges for ≥ 90% of cases) |
| 4 — Assessement | Every measurement has a threshold function and a severity tag (normal / mild / moderate / severe / critical); syndrome flags fire when expected on known-positive test cases |
| 5 — Clinical Validation | AUBMC radiologist has reviewed ≥ 20 cases; ICC for canal AP ≥ 0.75, Cobb angle MAE ≤ 5° |
| 6 — Report | PDF/DOCX report generated for every Duke case, passes visual review on 20 random samples |

### 0.6 Hardware & environment assumptions

- CUDA GPU with ≥ 8 GB VRAM for TotalSpineSeg inference (per their README)
- ≥ 32 GB RAM
- Python 3.10
- TotalSpineSeg pinned to `totalspineseg[nnunetv2]` with `nnunetv2==2.6.2` (their tested version)
- SCT v6.x (current stable) for cord analysis
- Storage: ~500 GB recommended (Duke MRI files + outputs)

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
