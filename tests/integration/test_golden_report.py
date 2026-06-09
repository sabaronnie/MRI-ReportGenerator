"""Golden-dataset regression (rubric Q2).

A fixed input (the sample post-interpretation contract) must keep producing the same stable report
output: summary counts, impression bullets, and the set of interpreted statuses. A diff here flags an
unintended behavior change in the interpretation->reporting chain. Regenerate the golden deliberately
(and review the diff) when the change is intended.
"""

from __future__ import annotations

import json
import os

import pytest

from services.reporting.builder import build_report_document

HERE = os.path.dirname(__file__)
CONTRACT = os.path.join(HERE, "..", "..", "services", "reporting", "examples", "sample_reporting_contract.json")
GOLDEN = os.path.join(HERE, "golden", "report_sample.golden.json")


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


@pytest.mark.integration
def test_report_matches_golden():
    handoff = json.load(open(CONTRACT))
    got = _stable_subset(build_report_document(handoff))
    expected = json.load(open(GOLDEN))
    assert got == expected, "report output drifted from golden; review diff and regenerate if intended"
