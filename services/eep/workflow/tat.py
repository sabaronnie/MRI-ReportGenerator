"""Turnaround-time computation — derived from the case's created_at + status.

No storage: age is measured from creation; cases that are reviewed/signed are
"done". The target is a single global env value (WORKFLOW_TAT_TARGET_HOURS).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone


def target_hours() -> float:
    try:
        return float(os.environ.get("WORKFLOW_TAT_TARGET_HOURS", "24"))
    except ValueError:
        return 24.0


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def compute(created_at: str, status: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    created = _parse(created_at)
    age_hours = round((now - created).total_seconds() / 3600, 1) if created else None
    target = target_hours()

    if status in ("reviewed", "signed"):
        tat_status = "signed"
    elif age_hours is None:
        tat_status = "unknown"
    elif age_hours >= target:
        tat_status = "breach"
    elif age_hours >= 0.75 * target:
        tat_status = "warning"
    else:
        tat_status = "on_track"

    return {"age_hours": age_hours, "tat_status": tat_status, "target_hours": target}
