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
| T5 | Tradeoff evidence (≥3, with numbers) | 🔴 | `docs/tradeoffs.md` is a 6-line stub. Need ≥3 real tradeoffs + what we *didn't* choose + measurements. `[infra]+[team]` |
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
| Q1 | Test suite breadth (unit + integration + ≥1 e2e on **deployed**) | 🟡 | measurements has unit tests ✅. **EEP: 0 tests. `tests/e2e` + `tests/integration`: empty stubs.** Manual live e2e done 2026-06-08 but not automated. `[infra]` |
| Q2 | Regression / validation strategy | 🟡 | Golden fixtures exist; need committed golden-regression gate for core measurements. `[science]+[infra]` |

## G — GitHub Repository (5%)
| # | Item | Status | Next |
|---|------|--------|------|
| G1 | Commit history & ownership | ✅ | Granular plain commits + CODEOWNERS. Strong. |
| G2 | Branching / review / traceability | 🟡 | Feature branches ✅. **No PRs opened yet — everything unmerged.** Open PRs with a teammate reviewer. `[team]` |

## M — MLOps / Observability / Documentation (10%)
| # | Item | Status | Next |
|---|------|--------|------|
| M1 | Automated lifecycle pipeline | 🔴 | See risk #2 (validation-as-lifecycle framing) + CI. `[infra]+[science]` |
| M2 | Experiment tracking & thresholds | 🔴 | MLflow (or equivalent) logging validation runs + threshold table. `[infra]+[science]` |
| M3 | Monitoring & ML signal | 🟡 | `/metrics` **exposed** on both services (eep_requests_total, eep_request_duration_seconds; measurement_duration_seconds, measurement_results_total, measurement_pathology_flags_total). Need Prometheus scrape + **Grafana** dashboards (p50/p95, error rate, throughput) + ≥1 ML signal (pathology-flag rate / component error rate as drift proxy). `[infra]` |
| M4 | Documentation completeness | 🟡 | `docs/*` are stubs; `DEVELOPMENT_JOURNEY.md` ✅. Need business + technical + deployment + cost docs. `[infra]+[team]` |

---

## Net: what's LEFT, grouped by who unblocks it

### Andrew must provide / decide
- 🔴 **AWS creds + spend OK** → unblocks GT2, S5, GT1-deployed, D1.
- 🧭 **MLOps framing** (validation-as-lifecycle) — team sign-off.
- 🧭 **Novelty/positioning** sharpening (duplicate-title team) — team.
- 🧭 **Open PRs** to merge `feat/eep` + `feat/frontend` (+ wire reporting) — needs a reviewer.

### `[infra]` (this chat) — can start now, no creds
1. k8s manifests (S4) for the 3 services + ingress.
2. EEP unit tests + automated integration + e2e (Q1).
3. Prometheus scrape config + Grafana dashboards (M3).
4. GitHub Actions CI: build/test/push images (M1 partial, G2 support).
5. Tradeoffs doc with evidence (T5) + flesh out `docs/*` (M4).
6. Wire EEP → reporting IEP + richer orchestration (T3/T4/GT3) — coordinate with `[report]`.
7. AWS IaC (ECR + ECS/Fargate or EKS + ALB + RDS + Secrets Manager) — write now, apply when creds land.

### `[science]` / `[report]` (other chats)
- Reporting service: finish + expose `/render`, define error/fallback (T3, GT3).
- Golden-regression gate + validation metrics for MLOps (Q2, M1/M2).
- Write-ups: AI depth (T1), baseline rigor (P2).

### Already solid ✅
Frozen contracts (S1) · EEP validation + rate limit (S2) · containerization built & run (S4 docker part) · real EEP↔measurements orchestration (verified) · granular git history (G1) · the React UI (D5) · `/metrics` exposed (M3 half).
