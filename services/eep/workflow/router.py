"""/workflow API — worklist (filter/sort/TAT), claim/assign, addenda.

Reads the in-memory case store (read-only) and the users DB (for assignee names);
its own mutable state lives in workflow.db. See docs/workflow-features.md.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import config, store
from ..auth import db as auth_db
from ..auth.deps import get_current_user
from ..orchestration import _case_to_handoff
from . import db, tat

db.init_db()

router = APIRouter(prefix="/workflow", tags=["workflow"])

_TRIAGE_RANK = {"urgent": 0, "review": 1, "none": 2}


class AssignIn(BaseModel):
    assignee_id: str


class AddendumIn(BaseModel):
    text: str = Field(min_length=1)


def _require_case(case_id: str) -> dict:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    return case


def _assignment_public(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "assignee_id": row["assignee_id"],
        "assignee_name": row["assignee_name"],
        "claimed_at": row["claimed_at"],
    }


# ----------------------------------------------------------------- worklist ---

@router.get("/worklist")
def worklist(
    user: dict = Depends(get_current_user),
    status: str | None = None,
    triage: str | None = None,
    assignee: str | None = None,
    mine: bool = False,
    q: str | None = None,
    sort: str = "priority",
):
    cases = store.list_cases()
    assignments = db.assignments_for([c["case_id"] for c in cases])

    rows = []
    for c in cases:
        a = assignments.get(c["case_id"])
        rows.append({
            **c,
            "assignment": _assignment_public(a),
            "tat": tat.compute(c.get("created_at", ""), c.get("status", "")),
        })

    # filters
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if triage:
        rows = [r for r in rows if r.get("triage_badge") == triage]
    if mine:
        rows = [r for r in rows if r["assignment"] and r["assignment"]["assignee_id"] == user["id"]]
    elif assignee == "unassigned":
        rows = [r for r in rows if not r["assignment"]]
    elif assignee:
        rows = [r for r in rows if r["assignment"] and r["assignment"]["assignee_id"] == assignee]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r.get("case_id", "").lower()]

    # sort
    if sort == "oldest":
        rows.sort(key=lambda r: r.get("created_at", ""))
    elif sort == "newest":
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    else:  # priority: urgent first, then oldest within a triage level
        rows.sort(key=lambda r: (_TRIAGE_RANK.get(r.get("triage_badge"), 3), r.get("created_at", "")))

    return rows


# ------------------------------------------------------------- case detail ---

@router.get("/cases/{case_id}")
def case_workflow(case_id: str, _: dict = Depends(get_current_user)):
    case = _require_case(case_id)
    c = case["case"]
    return {
        "case_id": case_id,
        "assignment": _assignment_public(db.get_assignment(case_id)),
        "tat": tat.compute(c.get("created_at", ""), c.get("status", "")),
        "addenda": db.list_addenda(case_id),
    }


# ----------------------------------------------------------- claim / assign ---

@router.post("/cases/{case_id}/claim")
def claim(case_id: str, user: dict = Depends(get_current_user)):
    _require_case(case_id)
    return _assignment_public(db.set_assignment(case_id, user["id"], user["name"]))


@router.post("/cases/{case_id}/release")
def release(case_id: str, _: dict = Depends(get_current_user)):
    _require_case(case_id)
    db.clear_assignment(case_id)
    return {"ok": True}


@router.post("/cases/{case_id}/assign")
def assign(case_id: str, body: AssignIn, _: dict = Depends(get_current_user)):
    _require_case(case_id)
    target = auth_db.get_user(body.assignee_id)
    if not target:
        raise HTTPException(status_code=404, detail="assignee not found")
    return _assignment_public(db.set_assignment(case_id, target["id"], target["name"]))


# ------------------------------------------------------------------ addenda ---

@router.post("/cases/{case_id}/addendum", status_code=201)
def add_addendum(case_id: str, body: AddendumIn, user: dict = Depends(get_current_user)):
    _require_case(case_id)
    return db.add_addendum(case_id, user["id"], user["name"], body.text)


# -------------------------------------------------------------- report PDF ---

@router.get("/cases/{case_id}/report.pdf")
def report_pdf(case_id: str, _: dict = Depends(get_current_user)):
    """Branded clinical PDF: project the case onto the reporting handoff and ask the
    reporting IEP to render a real PDF (see services/reporting/pdf_report.py)."""
    case = _require_case(case_id)
    base = (config.REPORTING_URL or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="reporting service not configured")
    try:
        resp = httpx.post(f"{base}/render.pdf", json=_case_to_handoff(case), timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="reporting service unavailable")
    return Response(
        content=resp.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{case_id}-report.pdf"'},
    )
