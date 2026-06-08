"""Unit tests for the in-memory store + the orchestration helpers."""

from __future__ import annotations

from services.eep import orchestration, store


def test_fixtures_loaded():
    # The store is a shared singleton across the test session (other tests may add uploads),
    # so assert the three bundled demo cases are present rather than an exact count.
    ids = {c["case_id"] for c in store.list_cases()}
    assert {"demo-healthy-0001", "demo-stenosis-0003", "demo-fracture-0002"} <= ids


def test_create_case_starts_queued():
    res = store.create_case("scan.nii.gz", "tester")
    assert res["status"] == "queued"
    case = store.get_case(res["case_id"])
    assert case["case"]["status"] in {"queued", "processing", "ready"}
    assert case["job"]["stages"][0] == "queued"


def test_signoff_status_survives_sim_clock():
    # Regression: the simulated clock used to revert an uploaded case's status from
    # "reviewed" back to "ready" on every read. Sign-off must stick.
    res = store.create_case("scan.nii.gz", "tester")
    cid = res["case_id"]
    signed = store.sign_off(cid, "Dr. Test")
    assert signed["case"]["status"] == "reviewed"
    # Re-read several times — the _advance guard must keep it reviewed.
    for _ in range(3):
        assert store.get_case(cid)["case"]["status"] == "reviewed"


def test_case_to_handoff_fills_missing_contract_keys():
    # Fixtures predate some envelope fields; the normalizer must backfill them so reporting accepts them.
    minimal = {"case": {"case_id": "x"}, "measurements": {}, "flags": {}, "interpretations": {}}
    handoff = orchestration._case_to_handoff(minimal)
    for key in ("contract_version", "case", "manifest", "components", "measurements", "flags", "interpretations", "report_context"):
        assert key in handoff
    assert "measurements" in handoff["interpretations"]
    assert "syndromes" in handoff["interpretations"]


def test_readiness_false_without_iep_urls(monkeypatch):
    monkeypatch.setattr(orchestration.config, "MEASUREMENTS_URL", "")
    monkeypatch.setattr(orchestration.config, "REPORTING_URL", "")
    assert orchestration.measurements_ready() is False
    assert orchestration.reporting_ready() is False


def test_render_case_report_uses_reporting_client(monkeypatch):
    class FakeReporting:
        def render(self, handoff):
            return {"report": {"title": "T"}, "artifacts": {"clinical_html": "<html>ok</html>"}}

    monkeypatch.setattr(orchestration, "ReportingClient", lambda: FakeReporting())
    html = orchestration.render_case_report(store.get_case("demo-healthy-0001"))
    assert html == "<html>ok</html>"


def test_render_case_report_none_when_reporting_down(monkeypatch):
    class DeadReporting:
        def render(self, handoff):
            return None

    monkeypatch.setattr(orchestration, "ReportingClient", lambda: DeadReporting())
    assert orchestration.render_case_report(store.get_case("demo-healthy-0001")) is None
