# MRI-ReportGenerator

Cervical spine MRI analysis pipeline — sagittal T2 MRI (DICOM/NIfTI) in, structured radiologist-style report out. The report carries vertebral/disc/canal/cord measurements, threshold-based assessment against cited norms, and anomaly flags **for physician review**.

**Course:** EECE503N / EECE798N — AI Engineering, AUB — Final Project (Spring 2026)

## Andrew Khoury, Ronnie Saba, Mohammad Sharafeddine

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

### Monitoring & Observability

**[`deliverables/monitoring.md`](deliverables/monitoring.md)**

Covers the full Prometheus + Grafana stack (rubric §11 M3): per-service metrics exposed by each IEP, all seven Grafana dashboard panels with PromQL, the ML-specific signal (pathology flag distribution as output-drift proxy), install/access instructions, and teardown notes.

### Tradeoffs

**[`technical-documentation/tradeoffs.md`](technical-documentation/tradeoffs.md)** — three explicit engineering tradeoffs (rubric §5): three containers vs. one, threshold catalog vs. ML classifier, async job queue vs. synchronous response — each with what was chosen, what was not, and evidence.

### MLOps & CI

| File | What it covers |
|------|----------------|
| [`mlops/validate.py`](mlops/validate.py) | Evaluation + MLflow tracking + promotion gate (rubric §7) |
| [`.github/workflows/mlops.yml`](.github/workflows/mlops.yml) | Runs the promotion gate on every push/PR |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | pytest (unit + integration + golden) → Docker build → ECR push on main |
| [`technical-documentation/mlops.md`](technical-documentation/mlops.md) | MLOps design doc |
| [`technical-documentation/ci.md`](technical-documentation/ci.md) | CI workflow and secrets setup |

### Security & Robustness

**[`technical-documentation/auth-design.md`](technical-documentation/auth-design.md)** — input validation, rate-limiting, and failure-mode behaviour (rubric §12).

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
| G4 alignment (Cobb) | ✅ measurement validated (method-valid; not a disease discriminator — d=0.28, p=0.32 — reported as reference value) |
| G1 Ha/Hp | ✅ correctly null on spondylosis cohort (p=0.92) — healthy-validated compression screen; dedicated fracture dataset not available |
| G5 fracture (5.2) + myelomalacia (5.1) | ✅ 5.2 fracture screen validated + calibrated (healthy FP 17% → 0%, Spine-Generic n=60); 5.1 myelomalacia wired (healthy-specificity Colab run pending) |
| G6 assessment | wired end-to-end |

Full results: [`docs/validation/results-final-2026-06-08.md`](docs/validation/results-final-2026-06-08.md)

---

## Tests

```bash
pytest services tests
```

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
