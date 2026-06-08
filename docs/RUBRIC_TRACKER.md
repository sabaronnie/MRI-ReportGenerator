# Rubric Tracker — what's done, what's left

> Living checklist mapping the EECE503N rubric to our actual state. Updated 2026-06-09 (Andrew; science
> rows finalized). Legend: ✅ done · 🟡 partial · 🔴 not started · 🧭 needs a decision
> Owner tags: `[infra]` EEP/frontend/deploy/CI/monitoring · `[science]` measurement-validation · `[report]` reporting
>
> **Science track is COMPLETE (2026-06-09):** deliverables T1/P2/P4/C1-P3 written (`overleaf/deliverables/`,
> compile with tectonic) + the paper (`overleaf/paper/`). Final per-group verdicts (reproduced from committed
> code, `docs/validation/results-final-2026-06-08.md`): **G3 canal/SAC/cord ✅ strong (p=0.0001)** · **G2 disc
> ⚠️ partial** (disc/VB AP ratio AUC 0.62; signal/bulge negative) · **G4 alignment ❌ NOT a discriminator**
> (validated *measurement*, not a screen; balanced d=0.28, p=0.32) · **G1/G5.1 ✅ healthy-validated screens**
> · **G6 🟢 wired end-to-end**. Frontend + infra code are the remaining open tracks.

## ⚠️ Top risks (read first)
1. ~~**GT3 / T3 / T4 — second IEP + real EEP orchestration.**~~ ✅ **RESOLVED 2026-06-08.** Wrapped the existing `services/reporting/` builder/renderers in a Flask IEP (`/render`), wired the EEP to orchestrate **measurements → reporting**, and DEPLOYED it. Live EEP `/readyz` shows `measurements_ready:true` AND `reporting_ready:true`; `GET /cases/{id}/report.html` renders a clinical report via the reporting IEP. EEP now orchestrates TWO independent IEPs. GT3/T3/T4 met.
2. **MLOps (§7 / M1–M2) is the weakest fit — needs a framing decision.** We don't *train* a model (TotalSpineSeg/SCT are pretrained; interpretation is threshold-based). To satisfy "automated pipeline covering eval + promotion decision + experiment tracking + thresholds," frame it as an **automated validation pipeline**: run the pipeline on the golden cohort → log metrics to **MLflow** → gate "promotion" (merge to main / threshold-table version bump) on metric thresholds. This is defensible but must be decided + built. 🧭 `[team]+[infra]+[science]`
3. ~~**Competitive grading + a duplicate title.**~~ ✅ **ADDRESSED 2026-06-09.** Team 14 also submitted "Automated Cervical Spine MRI Analysis." The novelty + AI-justification is now written up standalone (`overleaf/deliverables/C1_P3_novelty.tex`): healthy-anchored disease-agnostic detectors, no-per-case-GT validation methodology, the physical-dimension scanner-immunity insight, honest negatives, and a cited review-only interpretation layer. Argument stands on its own; a point-by-point head-to-head can be appended if Team 14's scope is shared. `[science]`

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
| T1 | AI depth / non-triviality | ✅ | **Written up: `overleaf/deliverables/T1_ai_depth.tex`** (+ `docs/ai-depth.md` mirror) — multi-model segmentation composition, the geometric measurement algorithms (endplate-line fit, canal-cut, SPINEPS Cobb), and the validation methodology, with a bug-ledger of clinically-wrong naïve outputs we caught + fixed. `[science]` |
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
| S3 | Errors / timeouts / retries / fallbacks | ✅ | Fixture fallback ✅, httpx timeouts ✅, per-component errors ✅, **retry-with-backoff on IEP calls** (connect/timeout/5xx) ✅ + tested (`services/eep/clients/_http.py`, `test_retries.py`). |
| S4 | Containerization & orchestration | 🟡 | 3 Dockerfiles ✅ + compose ✅ (built & run 2026-06-08). **k8s manifests REQUIRED — 🔴 not started.** `[infra]` |
| S5 | Deployment architecture & secrets | 🔴 | AWS arch + Secrets Manager + written doc. Blocked on creds. `[infra]` |

## P — Application / Research Positioning (10%)
| # | Item | Status | Next |
|---|------|--------|------|
| P1 | Problem / question clarity | ✅ | `docs/positioning.md` — operational problem (radiologist shortage/wait-times) + the decision augmented (auto measurement table + threshold-screen flags). `[science]` |
| P2 | Baseline / benchmark rigor | ✅ | `overleaf/deliverables/P2_baseline.tex` + `docs/positioning.md` — manual baseline quantified, PMID-verified: read time 2.7–3.8 min (Forsberg 2017) + 5–10 min geometry (Zhu 2024); inter-observer Pfirrmann κ 0.265, cord AP ICC 0.66 axial, compression 0.35–0.56, Cobb mixed-reader ~0.55. `[science]` |
| P3 | AI justification / contribution | ✅ | `overleaf/deliverables/C1_P3_novelty.tex` — disease-agnostic healthy-anchored detectors + no-per-case-GT validation + scanner-immunity insight + honest negatives. `[science]` |
| P4 | Value or publishability | ✅ | `overleaf/deliverables/P4_publishability.tex` + the paper (`overleaf/paper/`). Application value; methodology = publishable upside. `[science]` |

## D — Presentation / Demo / Wow (20%) — mostly demo-day
| # | Item | Status | Next |
|---|------|--------|------|
| D1 | Demo completeness | 🟡 | Needs deployed system. |
| D2 | Technical clarity | 🔴 | Slides/docs. |
| D3 | Evidence shown | ✅ | Final consolidated validation (`docs/validation/results-final-2026-06-08.md`) + figures + `DEVELOPMENT_JOURNEY.md` (J1–J26). `[science]` |
| D4 | Q&A & delivery | 🔴 | Prep. |
| D5 | Visual polish / wow | ✅ | The React clinical UI is a genuine differentiator. Keep. `[infra]` |

## C — Creativity & Innovation (5%)
| # | Item | Status | Next |
|---|------|--------|------|
| C1 | Originality | ✅ | Risk #3 addressed — `overleaf/deliverables/C1_P3_novelty.tex`. `[science]` |
| C2 | Insightful design choices | ✅ | Mock-first contract-driven UI, healthy-anchored detectors, threshold-crossing validation — written up (T1 + C1/P3 + paper). |

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
- 🧭 **Final merges to main** — Andrew is handling the final stage solo; science + docs reconciled to main
  via the `integration/finalize-main` work (2026-06-09). Frontend + infra branches still to fold in.
- After the demo: `deployment/aws/teardown.sh` to stop the cluster cost.

### `[science]` — COMPLETE (2026-06-09)
- ✅ Write-ups: AI depth (T1), baseline rigor (P2), publishability (P4), novelty (C1/P3) — all in `overleaf/`.
- ✅ Validation finalized (`results-final-2026-06-08.md`): G3 strong, G2 partial, G4 not-a-discriminator,
  G1/G5.1 screens, G6 wired. Distribution-separation results feed the threshold table the MLOps gate guards.

### Optional polish (not blocking)
- S3: add explicit httpx retries (timeouts + fixture fallback already in).
- Single ALB Ingress (saves one ELB, removes CORS) — documented in tradeoffs as the next optimization.
- Per-case MRI in the viewer (frontend chat is exploring).
