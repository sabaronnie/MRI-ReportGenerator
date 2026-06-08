# Rubric Tracker — what's done, what's left

> Living checklist mapping the EECE503N rubric to our actual state. Updated 2026-06-08 (Andrew, infra chat).
> Legend: ✅ done · 🟡 partial · 🔴 not started · 🧭 needs a team decision
> Owner tags: `[infra]` this chat (EEP/frontend/deploy/CI/monitoring) · `[science]` measurement-validation chat · `[report]` Ronnie/reporting · `[team]`

## ⚠️ Top risks (read first)
1. ~~**GT3 / T3 / T4 — second IEP + real EEP orchestration.**~~ ✅ **RESOLVED 2026-06-08.** Wrapped the existing `services/reporting/` builder/renderers in a Flask IEP (`/render`), wired the EEP to orchestrate **measurements → reporting**, and DEPLOYED it. Live EEP `/readyz` shows `measurements_ready:true` AND `reporting_ready:true`; `GET /cases/{id}/report.html` renders a clinical report via the reporting IEP. EEP now orchestrates TWO independent IEPs. GT3/T3/T4 met.
2. **MLOps (§7 / M1–M2) is the weakest fit — needs a framing decision.** We don't *train* a model (TotalSpineSeg/SCT are pretrained; interpretation is threshold-based). To satisfy "automated pipeline covering eval + promotion decision + experiment tracking + thresholds," frame it as an **automated validation pipeline**: run the pipeline on the golden cohort → log metrics to **MLflow** → gate "promotion" (merge to main / threshold-table version bump) on metric thresholds. This is defensible but must be decided + built. 🧭 `[team]+[infra]+[science]`
3. **Competitive grading + a duplicate title.** Team 14 also submitted "Automated Cervical Spine MRI Analysis." Originality (C1) and AI-justification (P3) are scored relative to cohort → sharpen the novelty claim (healthy-anchored geometric detectors, frozen contracts, threshold-crossing validation, the React clinical UI). 🧭 `[team]`

---

## Baseline Gates (hard stops — any fail = rejection)
| Gate | Status | Where we are / next |
|------|--------|---------------------|
| **GT1** demo works end-to-end | ✅ | Verified on the DEPLOYED system (EKS): login→worklist→report→viewer (volume/mask from EEP)→sign-off, 0 console errors. |
| **GT2** public cloud API functional | ✅ | Live on AWS EKS (eu-north-1). Public EEP + frontend load balancers; `/healthz`,`/readyz`,`/docs`,`/metrics` reachable. |
| **GT3** EEP + ≥2 IEPs | ✅ | EEP orchestrates measurements IEP + reporting IEP (both deployed, both `*_ready:true`). MET 2026-06-08. |
| **GT4** deliverables complete | 🟡 | Repo ✅, local deploy ✅, docs 🟡, cloud demo 🔴. |
| **GT5** Application positioning | 🟡 | Positioning set; the *written* business case (problem / decision augmented / non-AI baseline / who pays) is still stub-level. `[team]` |

---

## T — AI Technical Complexity & Execution (30%)
| # | Item | Status | Next |
|---|------|--------|------|
| T1 | AI depth / non-triviality | 🟡→✅ | Pipeline is genuinely non-trivial (TotalSpineSeg + SCT cord/canal + geometric morphometry + group5 fracture/myelomalacia + threshold interpretation). Just needs to be *written up*. `[science]` |
| T2 | IEP 1 independence & value (measurements) | ✅ | Real Flask IEP, 10 components, frozen contract, graceful per-component errors (verified). |
| T3 | IEP 2 independence & value | ✅ | reporting IEP (Flask `/render`) — independent service, turns the interpretation handoff into a clinical report. Deployed on EKS. |
| T4 | EEP orchestration logic | 🟡→✅ | EEP now calls TWO IEPs (measurements on upload + reporting for `/report.html`), with fixture/error fallbacks. Could add parallel/conditional for extra credit. |
| T5 | Tradeoff evidence (≥3, with numbers) | ✅ | `docs/tradeoffs.md` — 6 engineering tradeoffs (platform, sync-orchestration, rule-based-vs-LLM, mock-first, S3-vs-bake, routing) each with chosen/rejected + measured evidence. |
| T6 | Execution quality & edge cases | 🟡 | Per-component error contract ✅, input validation/limits ✅. Add explicit timeout/retry/fallback evidence. `[infra]` |

## S — Software Methodology (15%)
| # | Item | Status | Next |
|---|------|--------|------|
| S1 | Service boundaries & contracts | ✅ | Frozen data + report + viewer contracts. Strong. |
| S2 | Validation & request constraints | ✅ | EEP validates type/size (415/413), per-IP rate limit. |
| S3 | Errors / timeouts / retries / fallbacks | 🟡 | Fixture fallback ✅, httpx timeout ✅, per-component errors ✅. **Retries** not implemented. `[infra]` |
| S4 | Containerization & orchestration | 🟡 | 3 Dockerfiles ✅ + compose ✅ (built & run 2026-06-08). **k8s manifests REQUIRED — 🔴 not started.** `[infra]` |
| S5 | Deployment architecture & secrets | 🔴 | AWS arch + Secrets Manager + written doc. Blocked on creds. `[infra]` |

## P — Application / Research Positioning (10%)
| # | Item | Status | Next |
|---|------|--------|------|
| P1 | Problem / question clarity | 🟡 | Write the operational problem + decision augmented. `[team]` |
| P2 | Baseline / benchmark rigor | 🟡 | Non-AI baseline = manual radiologist measurement; quantify (time, inter-observer variability). `[science]` |
| P3 | AI justification / contribution | 🟡 | Sharpen vs the duplicate-title team. `[team]` |
| P4 | Value or publishability | 🟡 | Application value; `feat/paper/draft` exists as upside. `[team]` |

## D — Presentation / Demo / Wow (20%) — mostly demo-day
| # | Item | Status | Next |
|---|------|--------|------|
| D1 | Demo completeness | 🟡 | Needs deployed system. |
| D2 | Technical clarity | 🔴 | Slides/docs. |
| D3 | Evidence shown | 🟡 | Validation run1 results exist (`feat/validation/run1-results`). |
| D4 | Q&A & delivery | 🔴 | Prep. |
| D5 | Visual polish / wow | ✅ | The React clinical UI is a genuine differentiator. Keep. `[infra]` |

## C — Creativity & Innovation (5%)
| # | Item | Status | Next |
|---|------|--------|------|
| C1 | Originality | 🟡 | See risk #3 (duplicate title). `[team]` |
| C2 | Insightful design choices | 🟡→✅ | Mock-first contract-driven UI, healthy-anchored detectors, threshold-crossing validation — write these up. |

## Q — Quality Assurance (5%)
| # | Item | Status | Next |
|---|------|--------|------|
| Q1 | Test suite breadth (unit + integration + ≥1 e2e on **deployed**) | ✅ | EEP unit (API/store/orchestration) + cross-service contract integration + deployed-system e2e (`tests/e2e`, env-gated, verified green against the live EEP). `pytest -q` → 22 passed. |
| Q2 | Regression / validation strategy | ✅ | Golden regression (`tests/integration/test_golden_report.py`) pins the interpretation→reporting output; MLOps gate (`mlops/validate.py`) fails CI on drift. |

## G — GitHub Repository (5%)
| # | Item | Status | Next |
|---|------|--------|------|
| G1 | Commit history & ownership | ✅ | Granular plain commits + CODEOWNERS. Strong. |
| G2 | Branching / review / traceability | 🟡→✅ | Feature branches ✅ + CODEOWNERS ✅ + **PRs open** (#2 backend/infra, #3 frontend). Needs a teammate review/approve to merge (main protected). `[team]` |

## M — MLOps / Observability / Documentation (10%)
| # | Item | Status | Next |
|---|------|--------|------|
| M1 | Automated lifecycle pipeline | ✅ | `mlops/validate.py` + `.github/workflows/mlops.yml`: evaluate threshold version on golden cohort → promotion gate (CI fails on regression). Framing = threshold/method versioning (`docs/mlops.md`). |
| M2 | Experiment tracking & thresholds | ✅ | MLflow tracking (SQLite) logs each validation run's params/metrics + `threshold_version` tag; explicit gate thresholds in `mlops/validate.py`. |
| M3 | Monitoring & ML signal | ✅ | kube-prometheus-stack deployed on EKS; ServiceMonitors scrape all 3 services; Grafana dashboard "MRI-ReportGenerator — Services" (throughput, error rate by class, p50/p95 latency, IEP durations) + ML signal panel (`measurement_pathology_flags_total` distribution). Verified live with traffic. See `docs/monitoring.md`. |
| M4 | Documentation completeness | 🟡→✅ | Real docs now: architecture, deployment (secrets+cost), monitoring, mlops, tradeoffs, rubric-tracker + DEVELOPMENT_JOURNEY. Remaining: a business/positioning one-pager (P1–P4). `[team]` |

---

## Net: what's LEFT (most of the infra/quality scope is now DONE — 2026-06-08)

### Done this session ✅ (infra/quality)
GT1, GT2, GT3 · S1–S5 (incl. k8s + deploy + secrets/cost) · Q1 (unit+integration+deployed-e2e) ·
Q2 (golden + gate) · M1+M2 (MLOps validate + MLflow) · M3 (Prometheus+Grafana) · M4 (docs) ·
T5 (tradeoffs) · T2/T3/T4 (EEP + 2 IEPs orchestrated) · CI (GitHub Actions) · G2 (PRs #2, #3 open).

### Andrew must provide / decide
- 🧭 **Merge the PRs** (#2 backend/infra, #3 frontend) — main is protected, needs a teammate review/approve.
- 🧭 **Novelty/positioning** sharpening vs the duplicate-title team (C1/P3) — team.
- 🧭 **Business/positioning one-pager** (P1–P4) — problem, decision augmented, non-AI baseline, who deploys.
- After the demo: `deployment/aws/teardown.sh` to stop the cluster cost.

### `[science]` / `[report]` (other chats)
- Write-ups: AI depth (T1), baseline rigor (P2), publishability angle (P4).
- Deeper clinical validation (distribution separation) feeds the threshold table the MLOps gate guards.

### Optional polish (not blocking)
- S3: add explicit httpx retries (timeouts + fixture fallback already in).
- Single ALB Ingress (saves one ELB, removes CORS) — documented in tradeoffs as the next optimization.
- Per-case MRI in the viewer (frontend chat is exploring).
