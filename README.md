# MRI-ReportGenerator

Cervical spine MRI analysis pipeline — sagittal T2 MRI (DICOM/NIfTI) in, structured radiologist-style report out. The report carries vertebral/disc/canal/cord measurements, threshold-based assessment against cited norms, and anomaly flags **for physician review**.

**Course:** EECE503N / EECE798N — AI Engineering, AUB — Final Project (Spring 2026)

---

## How it works

```
Input (DICOM/NIfTI, sagittal T2)
  → Segmentation        TotalSpineSeg + Spinal Cord Toolbox + SPINEPS
  → Measurements        vertebra · disc · canal/cord · alignment · screens
  → Assessment          threshold catalog → status per finding
  → Report              clinical report, flagged for physician review
```

**Architecture (EECE503N rubric):**
- **EEP** — public gateway: input validation, rate-limiting, orchestrates all IEPs, assembles the response
- **IEP – Segmentation:** three engines behind HTTP (TotalSpineSeg, SCT, SPINEPS)
- **IEP – Measurements + Assessment:** geometric/cord/signal engines + cited-threshold assessment layer
- **IEP – Reporting:** turns the assessment handoff into an HTML/PDF clinical report
- **Deployment:** AWS EKS, Docker images, Kubernetes manifests, Prometheus + Grafana, MLflow

---

## Deliverables

### Paper

The full research paper is at [`deliverables/paper/main.pdf`](deliverables/paper/main.pdf). It covers the clinical background, pipeline architecture, all six measurement groups, validation methodology, and results.

### Rubric documents

Four standalone rubric documents in [`deliverables/docs/`](deliverables/docs/):

| PDF | Summary |
|-----|---------|
| [`T1_ai_depth.pdf`](deliverables/docs/T1_ai_depth.pdf) | Demonstrates AI technical depth and non-triviality — covers the three segmentation models, how they integrate into the pipeline, and why each choice is non-trivial |
| [`P2_baseline.pdf`](deliverables/docs/P2_baseline.pdf) | Non-AI baseline comparison with primary-source numbers — establishes what manual radiologist measurement achieves and where the pipeline improves on it |
| [`P4_publishability.pdf`](deliverables/docs/P4_publishability.pdf) | Argues the value and publishability of the work — positions the system relative to existing tools and makes the case for clinical and research impact |
| [`C1_P3_novelty.pdf`](deliverables/docs/C1_P3_novelty.pdf) | Novelty and AI justification — explains what is genuinely new about this system and why AI is the right approach rather than a rule-based substitute |

---

## Deployment

Full step-by-step instructions are in the runbook:

**[`technical-documentation/RUNBOOK-deployment.md`](technical-documentation/RUNBOOK-deployment.md)**

The runbook covers two paths:

- **Part A — Docker only (local):** build and run the three segmentation model containers on your machine, no cloud required. Good for verifying the models work.
- **Part B — AWS EKS (recommended):** full production deployment on Amazon EKS with all six services, ECR image registry, load balancers, and monitoring. This is the deployment the project runs on.

---

## Validation status

| Group | Verdict |
|-------|---------|
| G3 canal / SAC / cord | ✅ strong (p=0.0001) |
| G2 disc | ⚠️ partial — disc/VB AP ratio AUC 0.62; signal & bulge are documented negatives |
| G4 alignment (Cobb) | ❌ not a discriminator (validated measurement, not a screen; d=0.28, p=0.32) |
| G1 Ha/Hp + G5.1 myelomalacia | ✅ healthy-validated screens (compression-fracture arm untested — no dataset) |
| G6 assessment | wired end-to-end |

Full results: [`docs/validation/results-final-2026-06-08.md`](docs/validation/results-final-2026-06-08.md)

---

## Tests

```bash
pytest services tests
```

---

## Medical-AI rules

1. **Cite every clinical claim.** If it can't be cited, it isn't claimed.
2. **Never diagnose.** Output wording: *"finding flagged for physician review"* / *"pattern consistent with possible X; clinical correlation required"* — never *"patient has X."*
3. **Separate training from evaluation data.** Segmenters are pretrained + frozen; the symptomatic cohort is a demonstration set, never trained on.
4. **No patient data in git** — NIfTI/DICOM are `.gitignore`d.
5. **No secrets in git** — `.env` / Secrets Manager / Actions secrets only.

---

## Licenses

| Component | License | Note |
|-----------|---------|------|
| TotalSpineSeg | LGPLv3 | dynamic CLI invocation |
| Spinal Cord Toolbox (incl. SCIseg) | LGPLv3 | dynamic CLI invocation |
| SPINEPS | Apache-2.0 | — |
| TPTBox / spinestats | Apache-2.0 | not AGPL, not a redistribution blocker |
| nnU-Net v2 | Apache-2.0 | via TotalSpineSeg |
| dcm2niix / nibabel / Flask | MIT / BSD / BSD | — |
| Duke CSpineSeg dataset | CC BY-NC-ND 4.0 | **non-commercial, no redistribution of derivatives** |
