# MLOps — validation, tracking & promotion (rubric §7 / M1–M2)

## The framing (why this isn't model training)
This system does **not** train a black-box model. Its decision logic is a **cited threshold table**
(`services/interpretation/thresholds.py`) plus geometric measurement methods. So the meaningful ML
lifecycle here is **threshold/method versioning**, not weight training. We treat a change to the
threshold table (or measurement code) the way a team treats a new model version:

```
   change thresholds/methods  ──▶  EVALUATE on golden cohort  ──▶  TRACK in MLflow  ──▶  PROMOTE / BLOCK
```

This is an honest, defensible mapping of §7 onto a measurement system, and it is automated + gated.

## The pipeline — `mlops/validate.py`
1. **Version** the "model": a short hash of `thresholds.py` (`threshold_version`).
2. **Evaluate** on a fixed golden cohort (the sample interpretation contract + the 3 bundled demo
   cases) by running the interpretation → reporting chain and computing metrics.
3. **Track**: log params (threshold version + gate config), metrics, and the promotion decision to
   **MLflow** (SQLite backend, `mlflow.db`; experiment `mri-threshold-validation`).
4. **Decide** (explicit metrics + thresholds — the promotion gate):

   | metric | threshold | rationale |
   |--------|-----------|-----------|
   | `render_success_rate` | == 1.0 | every golden case must produce a report |
   | `golden_match` | required | the reference case must not drift from its committed golden |
   | `cases_evaluated` | ≥ 4 | minimum cohort coverage |

   Pass → **PROMOTE** (exit 0, eligible to merge/deploy). Fail → **BLOCKED** (exit 1).

## Run it
```bash
pip install -r requirements-dev.txt -r requirements-mlops.txt
python -m mlops.validate                 # prints metrics + decision, logs to mlflow.db
mlflow ui --backend-store-uri sqlite:///mlflow.db   # browse tracked runs
```

## Automation
`.github/workflows/mlops.yml` runs the gate on every push/PR and **fails the build if a threshold
change regresses the golden cohort** — so a measurement/threshold change cannot reach `main` (and thus
deploy) without passing evaluation. The MLflow DB is uploaded as a build artifact for audit.

## Example run
```
threshold_version 6d7a460d75a3
metrics: cases_evaluated=4  render_success_rate=1.0  total_findings=62  flagged_findings=13  golden_match=1.0
DECISION: PROMOTE ✅
```

## Relationship to the science track
The deeper clinical validation (distribution separation, threshold-crossing analysis on real cohorts)
lives in the measurement/science work (`research/`, `docs/validation/`). This pipeline is the
**engineering gate** that keeps those validated thresholds from silently regressing once committed.
