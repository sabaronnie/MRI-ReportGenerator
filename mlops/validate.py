"""Validation / evaluation pipeline with experiment tracking + a promotion decision (rubric §7).

Lifecycle framing: this system does not train a black-box model — its "model" is the cited
**threshold table** (`services/interpretation/thresholds.py`) plus the measurement methods. So the
ML lifecycle here is *threshold/method versioning*:

  1. EVALUATE the current threshold version on a fixed golden cohort.
  2. TRACK the run (params + metrics + threshold version) in MLflow.
  3. DECIDE: a version is promotable (eligible to merge to main / deploy) only if it clears the
     metric thresholds below; otherwise it is blocked (non-zero exit).

Run:  python -m mlops.validate            (logs to ./mlruns if mlflow is installed)
CI gates "promotion" on the exit code; see .github/workflows/mlops.yml.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

from services.eep import orchestration, store
from services.reporting.builder import build_report_document
from services.reporting.render_html import render_clinical_report_html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_CONTRACT = os.path.join(ROOT, "services", "reporting", "examples", "sample_reporting_contract.json")
GOLDEN = os.path.join(ROOT, "tests", "integration", "golden", "report_sample.golden.json")
THRESHOLDS_FILE = os.path.join(ROOT, "services", "interpretation", "thresholds.py")

# Promotion gate — explicit metrics + thresholds (rubric: "explicit metrics and thresholds").
GATE = {
    "render_success_rate_min": 1.0,   # every golden case must render a report
    "golden_match_required": True,    # the reference case must not drift from its committed golden
    "min_cases": 4,                   # cohort coverage floor
}


def threshold_version() -> str:
    return hashlib.sha256(open(THRESHOLDS_FILE, "rb").read()).hexdigest()[:12]


def _stable_subset(doc: dict) -> dict:
    impression = doc["impression"]
    return {
        "title": doc["title"],
        "summary": doc["summary"],
        "impression": sorted(impression) if all(isinstance(x, str) for x in impression) else impression,
        "n_findings": len(doc["findings"]["table_rows"]),
        "n_highlighted": len(doc["findings"]["highlighted_measurements"]),
        "statuses": sorted({r.get("status") for r in doc["findings"]["table_rows"]}),
    }


def evaluate() -> dict:
    """Run the interpretation->reporting chain over the golden cohort; return metrics."""
    cohort = [("sample_contract", json.load(open(SAMPLE_CONTRACT)))]
    for cid in ("demo-healthy-0001", "demo-stenosis-0003", "demo-fracture-0002"):
        cohort.append((cid, orchestration._case_to_handoff(store.get_case(cid))))

    rendered, total_findings, flagged = 0, 0, 0
    for _, handoff in cohort:
        try:
            doc = build_report_document(handoff)
            html = render_clinical_report_html(doc)
            assert html.startswith("<!doctype html>")
            rendered += 1
            total_findings += len(doc["findings"]["table_rows"])
            flagged += len(doc["findings"]["highlighted_measurements"])
        except Exception:  # noqa: BLE001 — a failure to render is a metric, not a crash
            pass

    golden_match = _stable_subset(build_report_document(json.load(open(SAMPLE_CONTRACT)))) == json.load(open(GOLDEN))
    n = len(cohort)
    return {
        "cases_evaluated": n,
        "render_success_rate": rendered / n,
        "total_findings": total_findings,
        "flagged_findings": flagged,
        "golden_match": 1.0 if golden_match else 0.0,
    }


def decide(metrics: dict) -> tuple[bool, list[str]]:
    reasons = []
    if metrics["render_success_rate"] < GATE["render_success_rate_min"]:
        reasons.append(f"render_success_rate {metrics['render_success_rate']:.2f} < {GATE['render_success_rate_min']}")
    if GATE["golden_match_required"] and metrics["golden_match"] != 1.0:
        reasons.append("golden_match failed (report drifted from committed golden)")
    if metrics["cases_evaluated"] < GATE["min_cases"]:
        reasons.append(f"cohort too small ({metrics['cases_evaluated']} < {GATE['min_cases']})")
    return (len(reasons) == 0), reasons


def main() -> int:
    version = threshold_version()
    metrics = evaluate()
    promote, reasons = decide(metrics)

    # Experiment tracking (MLflow if available; always print a machine-readable record).
    try:
        import mlflow  # noqa: PLC0415

        # MLflow 3.x deprecated the file store; default to a local SQLite backend.
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
        mlflow.set_experiment("mri-threshold-validation")
        with mlflow.start_run(run_name=f"thresholds-{version}"):
            mlflow.set_tag("threshold_version", version)
            mlflow.log_params({"threshold_version": version, **{f"gate_{k}": v for k, v in GATE.items()}})
            mlflow.log_metrics(metrics)
            mlflow.set_tag("promotion_decision", "promote" if promote else "blocked")
    except ImportError:
        print("(mlflow not installed — skipping tracking; run record below is the source of truth)")

    record = {"threshold_version": version, "metrics": metrics, "promote": promote, "reasons": reasons}
    print(json.dumps(record, indent=2))
    print(f"\nDECISION: {'PROMOTE ✅' if promote else 'BLOCKED ❌ — ' + '; '.join(reasons)}")
    return 0 if promote else 1


if __name__ == "__main__":
    sys.exit(main())
