"""EEP runtime configuration (all env-overridable)."""

from __future__ import annotations

import os
from pathlib import Path

EEP_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = EEP_DIR / "fixtures"

# Real measurements IEP base URL (set in compose/k8s, e.g. http://measurements:8081).
# Empty => the EEP runs self-contained in fixture/simulated mode.
MEASUREMENTS_URL = os.environ.get("MEASUREMENTS_URL", "").rstrip("/")

# Reporting IEP base URL (set in compose/k8s, e.g. http://reporting:8082). Empty => the EEP
# can't render reports (the /report.html endpoint returns 503).
REPORTING_URL = os.environ.get("REPORTING_URL", "").rstrip("/")

# Where the viewer NIfTI volume/mask live at runtime (mounted, never committed).
SAMPLE_DATA_DIR = Path(os.environ.get("EEP_SAMPLE_DIR", str(EEP_DIR / "sample_data")))

# Upload constraints.
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(500 * 1024 * 1024)))
ACCEPTED_SUFFIXES = (".zip", ".nii", ".nii.gz")

# CORS — the frontend origin(s).
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("EEP_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

# Simple fixed-window rate limit (per client IP).
RATE_LIMIT_MAX = int(os.environ.get("EEP_RATE_LIMIT_MAX", "120"))
RATE_LIMIT_WINDOW_S = int(os.environ.get("EEP_RATE_LIMIT_WINDOW_S", "60"))

# Simulated processing timeline (seconds) — the UX clock while a case "processes".
SIM_TOTAL_S = float(os.environ.get("EEP_SIM_TOTAL_S", "8"))
