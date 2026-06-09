"""Workflow tests — worklist filter/sort/TAT, claim/release/assign, addenda.

Env (temp DBs + test secret) is set in conftest.py before the app imports.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from services.eep.app import app
from services.eep.workflow import tat

client = TestClient(app)


def _token(email="radiologist@demo", pw="demo12345"):
    return client.post("/auth/login", json={"email": email, "password": pw}).json()["token"]


def _h(tok=None):
    return {"Authorization": f"Bearer {tok or _token()}"}


def test_workflow_requires_auth():
    assert client.get("/workflow/worklist").status_code == 401


def test_worklist_returns_enriched_rows():
    rows = client.get("/workflow/worklist", headers=_h()).json()
    assert len(rows) >= 3
    assert "assignment" in rows[0] and "tat_status" in rows[0]["tat"]


def test_worklist_priority_sort_urgent_first():
    triages = [r["triage_badge"] for r in client.get("/workflow/worklist?sort=priority", headers=_h()).json()]
    assert triages.index("urgent") < triages.index("none")


def test_worklist_filter_and_search():
    urgent = client.get("/workflow/worklist?triage=urgent", headers=_h()).json()
    assert urgent and all(r["triage_badge"] == "urgent" for r in urgent)
    found = client.get("/workflow/worklist?q=stenosis", headers=_h()).json()
    assert found and all("stenosis" in r["case_id"] for r in found)


def test_claim_release_and_mine_filter():
    h = _h()
    cid = client.get("/workflow/worklist", headers=h).json()[0]["case_id"]
    claimed = client.post(f"/workflow/cases/{cid}/claim", headers=h)
    assert claimed.status_code == 200 and claimed.json()["assignee_name"]
    assert any(r["case_id"] == cid for r in client.get("/workflow/worklist?mine=true", headers=h).json())
    assert client.get(f"/workflow/cases/{cid}", headers=h).json()["assignment"]["assignee_name"]
    client.post(f"/workflow/cases/{cid}/release", headers=h)
    assert not any(r["case_id"] == cid for r in client.get("/workflow/worklist?mine=true", headers=h).json())


def test_assign_to_another_user_and_unknown_assignee():
    h = _h()
    users = client.get("/auth/users", headers=_h(_token("admin@demo"))).json()
    tech_id = next(u["id"] for u in users if u["role"] == "technologist")
    cid = client.get("/workflow/worklist", headers=h).json()[0]["case_id"]
    ok = client.post(f"/workflow/cases/{cid}/assign", headers=h, json={"assignee_id": tech_id})
    assert ok.status_code == 200 and ok.json()["assignee_id"] == tech_id
    assert client.post(f"/workflow/cases/{cid}/assign", headers=h, json={"assignee_id": "nope"}).status_code == 404


def test_addendum_create_and_list():
    h = _h()
    cid = "demo-healthy-0001"
    created = client.post(f"/workflow/cases/{cid}/addendum", headers=h, json={"text": "Re-evaluate C5-C6 next study."})
    assert created.status_code == 201 and created.json()["author_name"]
    detail = client.get(f"/workflow/cases/{cid}", headers=h).json()
    assert detail["addenda"] and detail["addenda"][-1]["text"].startswith("Re-evaluate")
    assert client.post(f"/workflow/cases/{cid}/addendum", headers=h, json={"text": ""}).status_code == 422


def test_unknown_case_404():
    h = _h()
    assert client.get("/workflow/cases/nope", headers=h).status_code == 404
    assert client.post("/workflow/cases/nope/claim", headers=h).status_code == 404


def test_tat_buckets():
    now = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)  # target 24h
    assert tat.compute("2026-01-01T23:00:00Z", "ready", now)["tat_status"] == "on_track"  # 1h
    assert tat.compute("2026-01-01T04:00:00Z", "ready", now)["tat_status"] == "warning"   # 20h
    assert tat.compute("2025-12-31T18:00:00Z", "ready", now)["tat_status"] == "breach"    # 30h
    assert tat.compute("2020-01-01T00:00:00Z", "reviewed", now)["tat_status"] == "signed"
