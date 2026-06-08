"""In-memory case store + the simulated processing clock.

Default ("fixture") mode serves the 3 bundled sample cases and runs uploaded cases through a
simulated queued -> ... -> ready timeline (mirrors the frontend mock, server-side). When a real
measurements IEP is configured + reachable, orchestration.py fills an uploaded case's core from it.
A real datastore (Postgres) replaces this dict in the deployment track.
"""

from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock

from . import config

_STAGE_ORDER = ["queued", "segmenting", "measuring", "interpreting", "ready"]
# (stage, progress-fraction upper bound) — drives both the stage label and the progress bar.
_SIM_STEPS = [("queued", 0.18), ("segmenting", 0.5), ("measuring", 0.82), ("interpreting", 1.0)]

_lock = Lock()
_store: dict[str, dict] = {}
_sim_start: dict[str, float] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_fixtures() -> None:
    for path in sorted(config.FIXTURES_DIR.glob("case-*.json")):
        data = json.loads(path.read_text())
        _store[data["case"]["case_id"]] = data


_load_fixtures()


def _advance(case: dict) -> None:
    """Recompute an uploaded case's job/status from elapsed time. No-op for fixtures."""
    cid = case["case"]["case_id"]
    start = _sim_start.get(cid)
    if start is None:
        return
    frac = min(1.0, (time.monotonic() - start) / max(0.1, config.SIM_TOTAL_S))
    stage = "ready"
    for name, upper in _SIM_STEPS:
        if frac < upper:
            stage = name
            break
    case["job"] = {"stage": stage, "stages": _STAGE_ORDER, "progress": round(frac, 3), "error": None}
    case["case"]["status"] = "ready" if stage == "ready" else "processing"


def _summary(case: dict) -> dict:
    c = case["case"]
    return {k: c[k] for k in ("case_id", "status", "triage_badge", "modality", "uploader", "created_at", "updated_at")}


def list_cases() -> list[dict]:
    with _lock:
        cases = list(_store.values())
        for c in cases:
            _advance(c)
        return sorted((_summary(c) for c in cases), key=lambda s: s["updated_at"], reverse=True)


def get_case(case_id: str) -> dict | None:
    with _lock:
        c = _store.get(case_id)
        if c is None:
            return None
        _advance(c)
        return deepcopy(c)


def get_job(case_id: str) -> dict | None:
    c = get_case(case_id)
    return c["job"] if c else None


def create_case(filename: str, uploader: str, core: dict | None = None) -> dict:
    """Create a new queued case. `core` (real measurements output) overrides the cloned baseline."""
    with _lock:
        base = deepcopy(_store.get("demo-healthy-0001") or next(iter(_store.values())))
        if core:
            for key in ("measurements", "flags", "components", "interpretations", "report"):
                if key in core:
                    base[key] = core[key]
        cid = f"upload-{uuid.uuid4().hex[:8]}"
        now = _now_iso()
        base["case"].update(
            {
                "case_id": cid,
                "status": "queued",
                "triage_badge": "none",
                "uploader": uploader,
                "created_at": now,
                "updated_at": now,
                "series_description": filename,
            }
        )
        base["job"] = {"stage": "queued", "stages": _STAGE_ORDER, "progress": 0.0, "error": None}
        _store[cid] = base
        _sim_start[cid] = time.monotonic()
        return {"case_id": cid, "status": "queued"}


def sign_off(case_id: str, signed_by: str) -> dict | None:
    with _lock:
        c = _store.get(case_id)
        if c is None:
            return None
        now = _now_iso()
        meta = c["report"].get("metadata") or {}
        meta.update(
            {
                "status": "signed",
                "signed_by": signed_by,
                "signed_at": now,
                "generated_at": meta.get("generated_at", now),
                "schema_version": meta.get("schema_version", "report-0.1"),
            }
        )
        c["report"]["metadata"] = meta
        c["case"]["status"] = "reviewed"
        c["case"]["updated_at"] = now
        _advance(c)
        return deepcopy(c)
