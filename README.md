# MRI-ReportGenerator

Cervical spine MRI analysis pipeline — sagittal T2 MRI (DICOM/NIfTI) in, structured radiologist-style report out. The report carries vertebral/disc/canal/cord measurements, threshold-based assessment against cited norms, and anomaly flags **for physician review**.

**Course:** EECE503N / EECE798N — AI Engineering, AUB — Final Project (Spring 2026)  
**Team:** Andrew Khoury · Roni Saba · Hamad

---

## Pipeline

```
Input (DICOM/NIfTI, sagittal T2)
  → Segmentation        TotalSpineSeg + Spinal Cord Toolbox + SPINEPS
  → Measurements        vertebra · disc · canal/cord · alignment · screens
  → Assessment          threshold catalog → status per finding
  → Report              clinical HTML/PDF report, flagged for physician review
```

---

## Rubric map

Every graded requirement below links directly to where it is satisfied in the repo.

| Rubric § | Requirement | Where it lives |
|----------|-------------|----------------|
| §3 | **Novelty claim** (not done before) | [`deliverables/docs/C1_P3_novelty.pdf`](deliverables/docs/C1_P3_novelty.pdf) |
| §3 | **Non-AI baseline** + quantitative justification | [`deliverables/docs/P2_baseline.pdf`](deliverables/docs/P2_baseline.pdf) |
| §3 | **Publishability / research value** | [`deliverables/docs/P4_publishability.pdf`](deliverables/docs/P4_publishability.pdf) |
| §3 | **AI depth** — why this is non-trivial | [`deliverables/docs/T1_ai_depth.pdf`](deliverables/docs/T1_ai_depth.pdf) |
| §4 | **EEP** — public gateway (FastAPI, input validation, rate-limiting, orchestration) | [`services/eep/`](services/eep/) |
| §4 | **IEP — Segmentation** (TotalSpineSeg / SCT / SPINEPS, non-trivial logic) | [`services/segmentation/`](services/segmentation/) |
| §4 | **IEP — Measurements + Assessment** (geometric engines + cited-threshold layer) | [`services/measurements/`](services/measurements/) · [`services/assessement/`](services/assessement/) |
| §4 | **IEP — Reporting** (assessment handoff → HTML/PDF clinical report) | [`services/reporting/`](services/reporting/) |
| §4 | Pipeline structure / service contracts | [`technical-documentation/pipeline-structure.md`](technical-documentation/pipeline-structure.md) |
| §5 | **Explicit tradeoffs** (≥3 with evidence) | [`deliverables/paper/main.pdf`](deliverables/paper/main.pdf) — Tradeoffs section |
| §6 | **Git discipline** — branching strategy, commit conventions, PR workflow | [`CLAUDE.md`](CLAUDE.md) (Branching and commit rules) |
| §7 | **MLOps pipeline** — evaluation, promotion gate, rollback decision | [`mlops/validate.py`](mlops/validate.py) · [`.github/workflows/mlops.yml`](.github/workflows/mlops.yml) |
| §7 | **Experiment tracking** (MLflow) | [`mlops/validate.py`](mlops/validate.py) · [`technical-documentation/mlops.md`](technical-documentation/mlops.md) |
| §7 | Explicit metrics and thresholds | `GATE` dict in [`mlops/validate.py`](mlops/validate.py) |
| §8 | **Unit + integration tests** | [`tests/`](tests/) · [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| §8 | **End-to-end test** (calls deployed system) | [`tests/e2e/test_deployed.py`](tests/e2e/test_deployed.py) |
| §8 | **Golden-dataset regression** | [`tests/integration/test_golden_report.py`](tests/integration/test_golden_report.py) · [`tests/integration/golden/`](tests/integration/golden/) |
| §8 | CI workflow (tests gate every push/PR) | [`technical-documentation/ci.md`](technical-documentation/ci.md) |
| §9 | **Docker images** (EEP + Measurements + Reporting + 3 seg engines) | [`deployment/docker/`](deployment/docker/) |
| §9 | **Docker Compose** (local full-stack) | [`deployment/compose/docker-compose.yml`](deployment/compose/docker-compose.yml) |
| §9 | **Kubernetes manifests** | [`deployment/k8s/`](deployment/k8s/) |
| §10 | **Cloud deployment** (AWS EKS) — step-by-step runbook | [`technical-documentation/RUNBOOK-deployment.md`](technical-documentation/RUNBOOK-deployment.md) |
| §10 | AWS provisioning scripts | [`deployment/aws/`](deployment/aws/) |
| §10 | Secrets management approach | [`technical-documentation/RUNBOOK-deployment.md`](technical-documentation/RUNBOOK-deployment.md) — Secrets section |
| §11 | **Prometheus + Grafana** stack | [`deployment/monitoring/`](deployment/monitoring/) |
| §11 | Per-service metrics, PromQL, ML-specific signal | [`deliverables/monitoring.md`](deliverables/monitoring.md) · [`technical-documentation/monitoring.md`](technical-documentation/monitoring.md) |
| §12 | **Input validation, rate limits, failure modes** | [`technical-documentation/auth-design.md`](technical-documentation/auth-design.md) · [`services/eep/`](services/eep/) |

---

## Deliverables

### Paper

[`deliverables/paper/main.pdf`](deliverables/paper/main.pdf) — clinical background, pipeline architecture, all six measurement groups, validation methodology, and results.

### Rubric documents

| PDF | Contents |
|-----|---------|
| [`deliverables/docs/T1_ai_depth.pdf`](deliverables/docs/T1_ai_depth.pdf) | AI technical depth — three segmentation models, integration, non-triviality |
| [`deliverables/docs/P2_baseline.pdf`](deliverables/docs/P2_baseline.pdf) | Non-AI baseline comparison with primary-source numbers |
| [`deliverables/docs/P4_publishability.pdf`](deliverables/docs/P4_publishability.pdf) | Research value and publishability argument |
| [`deliverables/docs/C1_P3_novelty.pdf`](deliverables/docs/C1_P3_novelty.pdf) | Novelty claim and AI justification |

### Monitoring

[`deliverables/monitoring.md`](deliverables/monitoring.md) — Prometheus + Grafana stack, per-service metrics, all seven dashboard panels with PromQL, ML-specific signal (pathology flag distribution as output-drift proxy), install/access, teardown.

---

## Tests

```bash
pytest -q                             # unit + integration + golden (e2e auto-skips without EEP_BASE_URL)
EEP_BASE_URL=https://... pytest -q    # include e2e against deployed system
```

Test layout:

| Path | What it covers |
|------|----------------|
| `tests/integration/test_golden_report.py` | Golden-dataset regression (§8.2) |
| `tests/integration/test_contract_chain.py` | Assessment → reporting contract chain |
| `tests/e2e/test_deployed.py` | End-to-end against live deployment (§8.1) |

CI runs all three on every push/PR via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## MLOps

The validation / promotion gate runs on every push via [`.github/workflows/mlops.yml`](.github/workflows/mlops.yml):

1. Evaluates the current threshold version on the golden cohort
2. Logs params + metrics to MLflow (SQLite in CI, configurable via `MLFLOW_TRACKING_URI`)
3. Exits non-zero if render success rate < 1.0 or golden match fails — **blocks merge**

Full design: [`technical-documentation/mlops.md`](technical-documentation/mlops.md)

---

## Deployment

Full step-by-step instructions: [`technical-documentation/RUNBOOK-deployment.md`](technical-documentation/RUNBOOK-deployment.md)

| Path | What |
|------|------|
| `deployment/docker/` | Six Dockerfiles (EEP, measurements, reporting, TSS, SCT, SPINEPS) |
| `deployment/compose/docker-compose.yml` | Local full-stack (Docker Compose) |
| `deployment/k8s/` | Kubernetes manifests for AWS EKS |
| `deployment/aws/` | EKS cluster provisioning + deploy scripts |
| `deployment/monitoring/` | Prometheus + Grafana Helm values, ServiceMonitors, dashboard ConfigMap |

---

## Validation status

| Group | Verdict |
|-------|---------|
| G3 canal / SAC / cord | strong (p=0.0001) |
| G2 disc | partial — disc/VB AP ratio AUC 0.62; signal & bulge documented negatives |
| G4 alignment (Cobb) | measurement validated (method-valid; d=0.28, p=0.32 — reference value) |
| G1 Ha/Hp | correctly null on spondylosis cohort (p=0.92) |
| G5 fracture (5.2) + myelomalacia (5.1) | fracture screen validated (healthy FP 17% → 0%, n=60); myelomalacia wired |
| G6 assessment | wired end-to-end |

Full results: [`docs/validation/results-final-2026-06-08.md`](docs/validation/results-final-2026-06-08.md)

---

## Licenses

| Component | License | Note |
|-----------|---------|------|
| TotalSpineSeg | LGPLv3 | dynamic CLI invocation |
| Spinal Cord Toolbox (incl. SCIseg) | LGPLv3 | dynamic CLI invocation |
| SPINEPS | Apache-2.0 | — |
| TPTBox / spinestats | Apache-2.0 | — |
| nnU-Net v2 | Apache-2.0 | via TotalSpineSeg |
| dcm2niix / nibabel / Flask | MIT / BSD / BSD | — |
| Duke CSpineSeg dataset | CC BY-NC-ND 4.0 | **non-commercial, no redistribution of derivatives** |
