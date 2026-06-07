"""Group 5 -> Group 6 output contract (the flags-JSON Group 6 consumes).

The emitter turns Group 5's per-vertebra measurements into a self-contained, JSON-
serialisable findings document: per-level fracture/compression screen + (optional)
myelomalacia, plus provenance, citations, not-assessed list, and honest caveats.

Design intent (see plans/phase-4-interpretation.md): Group 6's interpretation layer reads
per-level findings with a value + a screen status + a citable reference, and its myelopathy
indicator (4.3) consumes a per-level cord-signal flag. This contract supplies exactly that.
It REUSES the validated classify_genant + cervical_deformity_flag (no logic is re-implemented).
"""
import json

from services.measurements.group5.flags_contract import build_flags_contract


def _healthy():
    # uniform body -> Ha ~= Hp, not a deformity
    return {"Ha": 10.0, "Hm": 10.0, "Hp": 10.0}


def _compressed():
    # anterior wall collapsed -> Ha/Hp ~0.5, well below the screen threshold (~0.68)
    return {"Ha": 5.0, "Hm": 8.0, "Hp": 10.0}


def test_contract_top_level_provenance_and_structure():
    c = build_flags_contract("case42", [("C5", _healthy())])
    assert c["case_id"] == "case42"
    assert "schema_version" in c
    assert isinstance(c["levels"], list) and c["levels"][0]["level"] == "C5"
    # not-assessed sub-parts are declared explicitly (honest about scope)
    joined = " ".join(c["not_assessed"]).lower()
    assert "tumor" in joined and "scar" in joined
    # fracture screen provenance carries the cohort norm, the threshold policy, and citations
    prov = c["provenance"]["fracture_screen"]
    assert prov["z"] == 2.0
    assert any("Tan 2004" in s for s in prov["citations"])


def test_contract_healthy_level_not_flagged():
    lvl = build_flags_contract("c", [("C4", _healthy())])["levels"][0]["fracture"]
    assert lvl["flagged"] is False
    assert lvl["screen"] == "normal"
    assert lvl["genant_grade"] == 0
    assert abs(lvl["ratio"] - 1.0) < 0.05


def test_contract_compressed_level_flagged_for_review():
    lvl = build_flags_contract("c", [("C5", _compressed())])["levels"][0]["fracture"]
    assert lvl["flagged"] is True
    assert lvl["screen"] == "flag"
    assert lvl["cervical_z"] < -2.0
    assert "physician review" in lvl["note"].lower()      # never a diagnosis


def test_contract_myelomalacia_not_assessed_by_default():
    m = build_flags_contract("c", [("C5", _healthy())])["levels"][0]["myelomalacia"]
    assert m["assessed"] is False
    assert m["present"] is None                            # distinct from "assessed, negative"


def test_contract_myelomalacia_present_when_provided():
    c = build_flags_contract("c", [("C5", _healthy())], myelomalacia={"C5": True})
    m = c["levels"][0]["myelomalacia"]
    assert m["assessed"] is True
    assert m["present"] is True
    assert "physician review" in m["note"].lower()


def test_contract_is_json_serialisable_no_numpy_leak():
    # measure_vertebra returns numpy floats; the contract must round-trip through json
    import numpy as np
    heights = {"Ha": np.float64(5.0), "Hm": np.float64(8.0), "Hp": np.float64(10.0)}
    c = build_flags_contract("c", [("C5", heights)])
    s = json.dumps(c)                                      # must not raise
    assert json.loads(s)["levels"][0]["fracture"]["flagged"] is True


def test_contract_z_policy_threads_through():
    # the screen z (specificity policy) flows into provenance AND changes the threshold/flag
    strict = build_flags_contract("c", [("C5", {"Ha": 7.6, "Hm": 9.0, "Hp": 10.0})], screen_z=1.0)
    loose = build_flags_contract("c", [("C5", {"Ha": 7.6, "Hm": 9.0, "Hp": 10.0})], screen_z=3.0)
    assert strict["provenance"]["fracture_screen"]["z"] == 1.0
    assert strict["levels"][0]["fracture"]["flagged"] is True     # ratio 0.76 < thr 0.81
    assert loose["levels"][0]["fracture"]["flagged"] is False     # ratio 0.76 > thr 0.55
