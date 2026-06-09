# Demo Script & Runbook

Live-demo plan mapped to the rubric. Goal: show a real, deployed, observable system end-to-end —
**not a local notebook**. Hard rule: if the system fails during the demo, grading stops — so do the
pre-flight, and keep the fallback ready.

## Pre-flight (do ~30 min before)
1. Bring the cluster up if torn down: `./deployment/aws/01-provision.sh && ./deployment/aws/02-deploy-backend.sh && ./deployment/aws/03-deploy-frontend.sh` (~25 min) + `./deployment/monitoring/install.sh`.
2. Get the live URLs (they change per deploy):
   - `kubectl -n mri get svc eep frontend -o wide`  → EEP + frontend ELB hostnames
   - `kubectl -n monitoring get svc kps-grafana`     → Grafana hostname
3. Smoke test: `curl <eep>/healthz` and `curl <eep>/readyz` (expect `measurements_ready:true`,
   `reporting_ready:true`), open the frontend `/login`, open Grafana.
4. Warm the dashboards: `EEP_BASE_URL=<eep> pytest tests/e2e -m e2e` (also proves the deployed e2e live)
   + a few clicks, so Grafana panels show data.
5. **Fallback ready:** if AWS misbehaves, `cd deployment/compose && docker compose up` runs the identical
   stack locally; the frontend in `live` mode points at it. (Mention it's the same images.)
6. **If deploying the auth-enabled image** (full-stack branch): create the `eep-auth` Secret first
   (see `docs/deployment.md` → Authentication), and demo login with `radiologist@demo` / `demo12345`.
   `/cases*` then needs a token — the frontend handles it; raw `curl` needs `POST /auth/login` first.
   The EEP is single-replica (in-memory store), so uploaded cases stay on the one pod — expected.

## The flow (≈6–8 min) — call out the rubric box as you go
1. **Frontend → worklist** (`<frontend>`): log in as the radiologist. "This is the public app on AWS."
   → *GT1 demo, GT2 public, D5 polish.*
2. **Open a case** (e.g. demo-stenosis): show the findings table + impressions + the **NiiVue viewer**
   (real MRI + TSS overlay, loaded from the EEP/S3). → *the product.*
3. **Upload a scan**: it goes to the EEP, which **orchestrates the measurements IEP**; case appears.
   → *GT3 + T4 orchestration, S2 validation.*
4. **Open the generated report** (`<eep>/cases/<id>/report.html` or the "View report" button): rendered
   by the **reporting IEP**. "The EEP orchestrates two independent internal services." → *GT3 / T2 / T3.*
5. **Sign-off** (radiologist only): show RBAC + the report becomes signed. → *robustness / product.*
6. **API surface**: open `<eep>/docs` (FastAPI). → *EEP is a real boundary, not a pass-through.*
7. **Observability**: open **Grafana → "MRI-ReportGenerator — Services"**: throughput, error rate by
   class, p50/p95 latency, IEP durations, and the **ML signal** (pathology-flag distribution).
   → *§11 / M3.*
8. **Engineering maturity** (briefly, screen or repo): the green **test suite** (`pytest -q`, incl. the
   deployed e2e), the **MLOps gate** (`python -m mlops.validate` → PROMOTE + MLflow), **CI** (Actions),
   **PRs** (#2/#3). → *Q1/Q2, M1/M2, G1/G2.*

## Evidence to have open in tabs
- Frontend app · a case report · `<eep>/docs` · `<eep>/metrics` · Grafana dashboard
- A terminal showing `pytest -q` (27 passed) + `python -m mlops.validate` (PROMOTE)
- GitHub: the commit history + PRs #2/#3

## Likely Q&A (have answers ready)
- **"Why EKS not Fargate?"** → satisfies k8s+public-API in one; cost mitigated by teardown.
- **"Where's the ML signal / how do you monitor a non-classifier?"** → pathology-flag distribution +
  component error rate as drift proxies (monitoring.md).
- **"How do you test a medical pipeline?"** → unit + cross-service + deployed e2e + golden regression +
  the MLOps gate that blocks threshold regressions.
- **"No LLM?"** → deliberate: deterministic, golden-testable, no confabulation.
- **"Failure modes?"** → IEP unreachable → fixture fallback + retries; per-component graceful errors;
  `/readyz` surfaces IEP health.
- **"Positioning / who pays?"** → radiology departments; manual measurement baseline;
  augment-not-replace, physician-review wording.

## After the demo
- `./deployment/aws/teardown.sh` (+ `helm uninstall kps -n monitoring`) to stop the cost.
