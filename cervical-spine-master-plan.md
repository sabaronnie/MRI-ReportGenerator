# Cervical Spine MRI Analysis Pipeline — Master Plan

**Status:** v1 — under team review (imported from research session 2026-04-22)
**Course:** EECE503N / EECE798N (AI Engineering, AUB) — Final Project
**Team:** Andrew Khoury · Roni (sabaronnie) · Hamad
**Repo:** https://github.com/sabaronnie/MRI-ReportGenerator

This file is the top-level plan and index. Deep-dive research for each phase lives in `plans/phase-*.md`. Never edit this file directly without opening a PR.

---

## Goal

Build a cervical spine MRI analysis pipeline that takes a sagittal T2-weighted MRI (DICOM series or NIfTI file) as input and produces a structured radiology-style report containing vertebral, disc, canal, and cord measurements, threshold-based interpretation against literature norms, and anomaly flags for physician review.

The system is positioned as an **Application** (provisional — pending explicit team sign-off): a clinical-workflow tool, with manual radiologist measurement as the non-AI baseline.

---

## Scope

### Pipeline architecture

```
┌─────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────────┐   ┌────────┐
│  Input  │ → │ Segmentation │ → │ Measurements │ → │ Interpretation │ → │ Report │
└─────────┘   └──────────────┘   └──────────────┘   └────────────────┘   └────────┘
  Phase 1        Phase 2           Phase 3             Phase 4            Phase 6
                 TotalSpineSeg     Geometric +         Threshold          PDF/DOCX
                 + SCT (cord)      Cord +              flagging +         + figure
                                   Signal engines      demographic        overlays
                                                       percentiles
```

**Clinical Validation (Phase 5)** is a separate meta-workstream that validates the whole system against radiologist ground truth. It is not a runtime pipeline stage.

### Service architecture (per EECE503N rubric, GT3)

- **External Endpoint (EEP):** Flask orchestrator (decided 2026-04-28 by Roni; was FastAPI in v1 — Flask is sufficient for a stateless inference pipeline with no per-request persistence). Public API, input validation, rate-limit, report assembly. Not yet implemented.
- **Internal Endpoint 1 (IEP1):** Segmentation service. TotalSpineSeg + Spinal Cord Toolbox wrappers. Non-trivial DL inference. **Implementation:** [`services/segmentation/`](./services/segmentation/) — Phase 1 input handling + Phase 2.1 TSS wrapper landed 2026-04-28; SCT (Phase 2.2), mid-sagittal slice selection (2.3), and segmentation QC (2.4) pending.
- **Internal Endpoint 2 (IEP2):** Measurements + Interpretation service. Geometric, cord, signal engines + threshold flagging. **Implementation:** [`services/measurements/`](./services/measurements/) — pluggable-component scaffold landed 2026-04-28; the first producer component is now [`services/measurements/geometric/cervical_body_morphometry.py`](./services/measurements/geometric/cervical_body_morphometry.py), which outputs vertebral body AP width and anterior/middle/posterior heights for C3-C7. Downstream geometric components consume its corners/AP widths via `DEPENDS_ON`. Remaining 3A / 3B / 3C / Phase 4 components pending.

Three services → three Docker images (rubric S4) → three owners.

**Open question:** Is report generation a third IEP (IEP3) or does it live inline in the EEP? Impacts Docker image count and rubric T3. See `plans/phase-6-report-generation.md` and open questions below.

### Implementation status

Live mapping of plan-to-code. Owners stay TBD per the matrix below — *Built by* records who landed the implementation and is descriptive, not an ownership claim.

| Plan section | Implementation | Built by | Status |
|---|---|---|---|
| Phase 1 — Input Handling (1.1–1.4) | [`services/segmentation/input_handler.py`](./services/segmentation/input_handler.py) | Roni 2026-04-28 | Smoke-tested 6/6 on synthetic NIfTI; pending end-to-end on a Duke case |
| Phase 2.1 — TotalSpineSeg wrapper | [`services/segmentation/segmenter.py`](./services/segmentation/segmenter.py) | Roni 2026-04-28 | Subprocess shape per plan; pending live TSS run on a Duke case |
| Phase 3A.1 + 3A.2 — VB AP width + SI heights (validated-style body morphometry) | [`services/measurements/geometric/cervical_body_morphometry.py`](./services/measurements/geometric/cervical_body_morphometry.py) | Roni 2026-04-28 / updated 2026-04-28 | First measurement producer in IEP2. Implements canonical-RAS geometry, 3D disc-anchored body isolation, canal-visible midline-band slice selection, Genant-style 3-point heights, and refined SHIP-style mid-body AP width: AP-only distance, SI-center-constrained width points, and per-vertebra minimum-SI-mismatch width-slice choice across valid `best ± 1` slices. Synthetic-mask unit tests added; pending Duke-case parity check against the Colab notebook. |
| Phase 3A.3 — Spondylolisthesis + Meyerding grading | [`services/measurements/geometric/spondylolisthesis.py`](./services/measurements/geometric/spondylolisthesis.py) | Roni 2026-04-28 / updated 2026-04-28 | First downstream `DEPENDS_ON` consumer of `cervical_body_morphometry` (reads PI / PS corners and lower-level AP width). Unit coverage retained for anterolisthesis / retrolisthesis / neutral / spacing scaling / grade thresholds I–V / missing-producer / missing-corner / missing-AP-width / supine-caveat-in-report, plus a synthetic two-vertebra integration test. Outputs `spondy_slip_mm` + `spondy_pct_of_lower_AP` as numeric measurements; Meyerding grade and report lines (with mandatory supine-MRI caveat) in metadata. Pending Duke-case parity check. |

`ComponentResult` (the standard return shape for every measurement) lives in [`services/measurements/context.py`](./services/measurements/context.py) so multiple components can share the contract without circular imports.

Service runtime layout (both IEPs are Flask, K8s-shaped):

| Service | Path | Endpoints | Notes |
|---|---|---|---|
| IEP1 segmentation | [`services/segmentation/`](./services/segmentation/) | `GET /healthz`, `POST /segment` | `cli.py` for "prove on one case before scaling" runs |
| IEP2 measurements | [`services/measurements/`](./services/measurements/) | `GET /healthz`, `GET /readyz`, `GET /metrics`, `POST /measure` | Prometheus metrics: `measurement_duration_seconds`, `measurement_results_total`, `measurement_pathology_flags_total`. `PORT` and `MAX_UPLOAD_BYTES` env-driven; no on-disk state between requests |

Pending implementation (in plan order): 2.2 SCT cord, 2.3 mid-sagittal slice selection, 2.4 segmentation QC, 3A.4–3A.12, 3B.x, 3C.x, Phase 4, Phase 5, Phase 6, EEP service.

### Phase ownership matrix (research phase)

Owners and reviewers are assigned here once the team decides. Until then, every phase file has `Owner: TBD` in its header.

| Phase | File | Owner | Reviewer |
|---|---|---|---|
| 0 — Foundations | [`plans/phase-0-foundations.md`](./plans/phase-0-foundations.md) | TBD | TBD |
| 1 — Input Handling | [`plans/phase-1-input-handling.md`](./plans/phase-1-input-handling.md) | TBD | TBD |
| 2 — Segmentation | [`plans/phase-2-segmentation.md`](./plans/phase-2-segmentation.md) | TBD | TBD |
| 3A — Geometric Measurements | [`plans/phase-3a-geometric-measurements.md`](./plans/phase-3a-geometric-measurements.md) | TBD | TBD |
| 3B — Cord / Compression | [`plans/phase-3b-cord-compression.md`](./plans/phase-3b-cord-compression.md) | TBD | TBD |
| 3C — Signal-based (experimental) | [`plans/phase-3c-signal-based.md`](./plans/phase-3c-signal-based.md) | TBD | TBD |
| 4 — Interpretation | [`plans/phase-4-interpretation.md`](./plans/phase-4-interpretation.md) | TBD | TBD |
| 5 — Clinical Validation | [`plans/phase-5-clinical-validation.md`](./plans/phase-5-clinical-validation.md) | TBD | TBD |
| 6 — Report Generation | [`plans/phase-6-report-generation.md`](./plans/phase-6-report-generation.md) | TBD | TBD |
| 7 — Deferred / Out of scope | [`plans/phase-7-deferred.md`](./plans/phase-7-deferred.md) | All (append) | — |

### Scope decisions (in / experimental / deferred)

| Group | Item | Status | Source |
|---|---|---|---|
| 1 | VB AP width | Core | Phase 3A |
| 1 | VB SI height (anterior/middle/posterior) | Core | Phase 3A |
| 1 | Spondylolisthesis + Meyerding | Core | Phase 3A |
| 1 | VB T1/T2 signal for osteoporosis | Deferred | Phase 7 |
| 2 | Disc SI height | Core | Phase 3A |
| 2 | Disc AP width | Core | Phase 3A |
| 2 | Disc Height Index (derived) | Core | Phase 3A |
| 2 | Full 5-grade Pfirrmann | Deferred; replaced by simplified signal classifier | Phase 3C, Phase 7 |
| 3 | Canal AP diameter | Core | Phase 3A |
| 3 | Cord AP diameter (via SCT) | Core | Phase 3B |
| 3 | SAC (derived) | Core | Phase 3B |
| 3 | Torg-Pavlov ratio | Core | Phase 3A |
| 3 | Most stenotic level | Core | Phase 3A |
| 4 | C2–C7 Cobb angle | Core | Phase 3A |
| 4 | Lordosis classification | Core | Phase 4 |
| 4 | Segmental angles | Core | Phase 3A |
| 5 | Myelomalacia (T2-MI) | Experimental | Phase 3C |
| 5 | Fracture / tumor / scar detection | Deferred | Phase 7 |
| 6 | Radiculopathy indicators | Core | Phase 4 |
| 6 | Myelopathy indicators | Core | Phase 4 |
| 6 | Per-level structured report | Core | Phase 6 |
| 6 | Demographic percentile comparison | Core (cord via SCT `-normalize-hc`; others via Duke-built curves) | Phase 4 |

---

## Rubric alignment (EECE503N)

**Hard-stop gates — non-negotiable:**

- **GT1** Live demo works end-to-end → demo pipeline on one Duke case
- **GT2** Public cloud API functional → **AWS** deployment (decided)
- **GT3** EEP + ≥2 IEPs architecture → Flask EEP + IEP1 (Segmentation) + IEP2 (Measurements)
- **GT4** Required deliverables complete → repo + docs + deployment + demo + poster
- **GT5** Application positioning (provisional) → baseline = manual radiologist measurement; deployer = radiology departments

**Weighted categories and where they're addressed:**

| Category | Weight | Where addressed |
|---|---|---|
| AI Technical Complexity (T1–T6) | 30% | Phases 2, 3, 6; tradeoff documentation in each phase file |
| Software Methodology (S1–S5) | 15% | Phase 1 (validation), Phase 6 (error handling), Docker/K8s scaffolding, AWS deployment |
| Positioning (P1–P4) | 10% | Phase 0 (positioning), README, poster |
| Presentation / Demo (D1–D5) | 20% | Final-deliverable session (pre-demo rehearsal) |
| Creativity (C1–C2) | 5% | Phase 3 design choices (SCT integration is differentiator) |
| QA (Q1–Q2) | 5% | Test suite (unit + integration + E2E), golden-dataset regression |
| GitHub (G1–G2) | 5% | This repo; branching rules in CLAUDE.md |
| MLOps / Observability / Docs (M1–M4) | 10% | MLflow, Prometheus + Grafana, CI/CD, runbook |
| Bonus | +0 to +2 | Group 5 experimental features if they work |

---

## Data sources

### Primary dataset

**Duke University Cervical Spine MRI Segmentation Dataset (CSpineSeg)**
- Zhou et al. 2025, *Scientific Data* 12:1695
- DOI: [10.1038/s41597-025-05975-w](https://doi.org/10.1038/s41597-025-05975-w)
- Access: MIDRC — https://doi.org/10.60701/H6K0-A61V
- License: CC BY-NC-ND 4.0 (non-commercial, no derivatives)
- 1,255 sagittal T2 MRI exams, 1,232 patients, 481 with expert-verified segmentations
- Demographics: age, sex, race, ethnicity in `Clinical_manifest_RSNA_20250321.tsv`
- **What Duke IS used for:** segmentation quality check, demographic percentile curves, end-to-end plausibility runs
- **What Duke is NOT used for:** clinical measurement validation — no radiologist measurements in the dataset

### Pre-trained models

- **TotalSpineSeg** (Warszawer et al. 2025) — https://github.com/neuropoly/totalspineseg — LGPLv3
- **Spinal Cord Toolbox (SCT)** — https://github.com/spinalcordtoolbox/spinalcordtoolbox — LGPLv3
- **nnU-Net v2** (transitive) — https://github.com/MIC-DKFZ/nnUNet — Apache 2.0

### Normative references (used for threshold tables)

- Ulbrich et al. 2014 — Normative MR cervical canal dimensions (N=140 healthy)
- Thelen et al. 2019 (SHIP study) — cervical canal + VB reference values (N=2,453 general population)
- Yukawa et al. 2018 — C2–C7 Cobb in 1,200 asymptomatic adults
- Valošek et al. 2024 — healthy spinal cord morphometry database (built into SCT `-normalize-hc`)
- Martini et al. 2021 — review of cervical sagittal alignment measures
- Weber et al. 2023 — T2 Myelopathy Index method (Phase 3C)
- Horáková et al. 2022 — SCT compression detection (basis for `sct_detect_compression`)

See each phase file's `References` section for the full list relevant to that phase.

### Clinical validation data (future)

AUBMC radiologist collaboration — 20–30 case subset, manual measurements for ICC / Bland-Altman against pipeline output. Not part of Duke. Separate workstream.

---

## Open questions

Questions that affect the plan and need team answers:

1. **Application vs Research framing** — provisional: Application. Explicit team sign-off needed.
2. **Third IEP (report generation as separate service)?** — affects Docker image count, rubric T3 ceiling, and effort budget. See `plans/phase-6-report-generation.md`.
3. **Coding-phase ownership split** — deferred; team decides after research phase finishes.
4. **Repository license** — TBD. Duke data forces non-commercial downstream. Our own code could still be MIT-permissive-with-notice. Needs a decision before deployment.
5. **AWS service choice** — ECS (simpler) vs EKS (Kubernetes-native) vs Lambda (serverless + ECS for long tasks). Rubric requires K8s somewhere — EKS aligns naturally.
6. **TotalSpineSeg GPU requirement on cloud** — T4 GPU minimum; affects AWS instance-family choice and cost. Budget conversation.
7. **Sample data story** — we cannot commit Duke data. Demo needs a sample (possibly one de-identified cooperative case from AUBMC, or a publicly shareable case).
8. **Tradeoffs section** (rubric T5) — rubric requires ≥ 3 documented engineering tradeoffs with evidence. Candidates: inference latency vs precision on TotalSpineSeg (--iso flag), single-service monolith vs 3-service split, TotalSpineSeg cord vs SCT cord. Tradeoffs file created once Phase 0 finalizes.

---

## Glossary

**AP** — anterior-posterior (front-back dimension in sagittal plane)
**Cobb angle** — measurement of spinal curvature between two vertebral endplates
**CSF** — cerebrospinal fluid
**DICOM** — Digital Imaging and Communications in Medicine (standard medical image format)
**DHI** — Disc Height Index (disc height / adjacent vertebral body height)
**DCM** — Degenerative Cervical Myelopathy
**EEP / IEP** — External Endpoint / Internal Endpoint (rubric terminology)
**FOV** — Field of view
**ICC** — Intraclass Correlation Coefficient (agreement metric)
**IVD** — Intervertebral disc
**MCC / MSCC** — Maximum (spinal) Canal / Cord Compression
**Meyerding grade** — spondylolisthesis severity grade (I–V) based on slip percentage
**MRI** — Magnetic Resonance Imaging
**NIfTI** — Neuroimaging Informatics Technology Initiative (neuroimaging file format, .nii / .nii.gz)
**nnU-Net** — self-configuring deep learning segmentation framework
**Pfirrmann grade** — disc degeneration severity (I–V) based on T2 signal
**SAC** — Space Available for the Cord (canal AP − cord AP)
**SCT** — Spinal Cord Toolbox (spinalcordtoolbox.com)
**SI** — superior-inferior (top-bottom dimension)
**Stenosis** — narrowing (typically of spinal canal)
**T1w / T2w / STIR** — MRI sequence types
**T2-MI** — T2 Myelopathy Index (Weber 2023)
**Torg-Pavlov ratio** — canal AP / vertebral body AP
**TSS** — TotalSpineSeg
**VB** — Vertebral body
