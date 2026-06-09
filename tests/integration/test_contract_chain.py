"""Integration across services via the frozen contract.

The measurements IEP emits the post-assessement handoff contract; the reporting IEP consumes the
exact same contract. This test proves the two services integrate at the contract boundary without a
network: handoff JSON -> reporting builder -> renderers -> a valid report. It also exercises the EEP's
case->handoff normalizer feeding reporting (the path /cases/{id}/report.html takes in production).
"""

from __future__ import annotations

import json
import os

import pytest

from services.eep import orchestration, store
from services.reporting.builder import build_report_document
from services.reporting.render_html import render_clinical_report_html

CONTRACT = os.path.join(
    os.path.dirname(__file__), "..", "..", "services", "reporting", "examples", "sample_reporting_contract.json"
)

# The status enum frozen in docs/contracts/data-contract-v0.1.md.
FROZEN_STATUSES = {"within_reference", "outside_reference", "review_only", "not_assessable"}


@pytest.mark.integration
def test_measurements_handoff_renders_through_reporting():
    handoff = json.load(open(CONTRACT))
    document = build_report_document(handoff)
    # Reporting must derive a coherent document from the measurements contract.
    assert document["title"]
    assert document["source_contract_version"] == handoff["contract_version"]
    assert isinstance(document["impression"], list)
    # Every assessed row keeps a frozen status (contract compatibility).
    for row in handoff["assessements"]["measurements"]:
        assert row["status"] in FROZEN_STATUSES
    html = render_clinical_report_html(document)
    assert html.startswith("<!doctype html>")
    assert "Cervical" in html


@pytest.mark.integration
def test_eep_normalizer_feeds_reporting_for_every_fixture():
    # The EEP turns each stored case into a handoff that reporting accepts — no case should crash.
    for cid in ("demo-healthy-0001", "demo-stenosis-0003", "demo-fracture-0002"):
        handoff = orchestration._case_to_handoff(store.get_case(cid))
        document = build_report_document(handoff)
        assert document["title"]
        assert "table_rows" in document["findings"]


@pytest.mark.integration
def test_live_services_orchestrate_if_running():
    """If MEASUREMENTS_URL/REPORTING_URL point at running services, verify the EEP reaches them.

    Skipped by default (unit/CI run has no live IEPs); exercised against docker-compose locally.
    """
    if not (os.environ.get("MEASUREMENTS_URL") or os.environ.get("REPORTING_URL")):
        pytest.skip("no live IEP URLs configured")
    if os.environ.get("MEASUREMENTS_URL"):
        assert orchestration.measurements_ready() is True
    if os.environ.get("REPORTING_URL"):
        assert orchestration.reporting_ready() is True
