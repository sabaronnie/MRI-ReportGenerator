"""End-to-end Group 5 runner: one TSS step2 mask (+ optional SCIseg lesion mask) -> flags JSON.

The orchestration glues the already-tested pieces (vertebral_fracture measurement +
myelomalacia_specificity burden + flags_contract emitter). The only NEW logic tested here is
(a) the per-vertebra assembly loop and (b) mapping a cord lesion mask to the cervical LEVEL(s)
it overlaps by superior-inferior position. Measurement/flag/contract correctness is already
covered by their own test files.
"""
import json

import numpy as np

from run_group5_pipeline import assemble_case_contract


def _two_vertebra_seg():
    """P-S-R synthetic TSS-like volume (AP=axis0 anterior=low, SI=axis1, LR=axis2):
    two uniform cervical bodies stacked along SI (C3 superior, C4 inferior) + a posterior
    canal. Labels: canal=2, C3=13, C4=14."""
    seg = np.zeros((40, 34, 6), dtype=int)
    # bodies: anterior (low AP), 12 voxels wide AP, uniform; C3 high SI, C4 low SI
    seg[3:17, 18:30, 1:5] = 13          # C3 body, SI 18-29
    seg[3:17, 3:15, 1:5] = 14           # C4 body, SI 3-14
    # spinal canal: posterior to the bodies, spans the SI range
    seg[20:25, 3:30, 1:5] = 2
    return seg


def test_assemble_fracture_only_no_lesion():
    seg = _two_vertebra_seg()
    c = assemble_case_contract(seg, ("P", "S", "R"), zooms=(0.5, 1.0, 4.0), case_id="caseA")
    levels = {lv["level"]: lv for lv in c["levels"]}
    assert set(levels) == {"C3", "C4"}                  # both cervical bodies measured
    # no lesion mask passed -> myelomalacia not assessed at every level
    assert all(lv["myelomalacia"]["assessed"] is False for lv in c["levels"])
    assert c["case_id"] == "caseA"
    json.dumps(c)                                       # must be serialisable (no numpy leak)


def test_assemble_lesion_maps_to_overlapping_level():
    seg = _two_vertebra_seg()
    # a cord lesion at SI 20-24 -> overlaps C3's SI span (18-29), NOT C4's (3-14)
    lesion = np.zeros_like(seg, dtype=bool)
    lesion[21:24, 20:25, 2:4] = True
    c = assemble_case_contract(seg, ("P", "S", "R"), zooms=(0.5, 1.0, 4.0),
                               lesion=lesion, case_id="caseB")
    m = {lv["level"]: lv["myelomalacia"] for lv in c["levels"]}
    # a lesion mask WAS provided -> every level is "assessed"
    assert all(v["assessed"] is True for v in m.values())
    assert m["C3"]["present"] is True                   # lesion overlaps C3
    assert m["C4"]["present"] is False                  # not C4
    json.dumps(c)


def test_assemble_empty_lesion_assessed_but_negative():
    seg = _two_vertebra_seg()
    lesion = np.zeros_like(seg, dtype=bool)             # SCIseg ran, found nothing (healthy)
    c = assemble_case_contract(seg, ("P", "S", "R"), zooms=(0.5, 1.0, 4.0), lesion=lesion)
    m = {lv["level"]: lv["myelomalacia"] for lv in c["levels"]}
    assert all(v["assessed"] is True for v in m.values())   # assessed...
    assert all(v["present"] is False for v in m.values())   # ...and clean (the healthy goal)
