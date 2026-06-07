"""Cervical sagittal alignment (Cobb) from fitted endplate LINES, not corner extrema.

The literature-validated fix for the corrupted angular outputs (Wang 2023: line-fit ICC 0.97 vs
0.75 four-corner): derive the Cobb angle from the inferior-endplate lines of C2/C3 and C7. These
tests cover the pure angle geometry + the per-vertebra tangent extraction; the lordosis sign and
the +9-11 deg healthy expectation are validated on the 12 Spine-Generic necks separately.
"""
import math

import numpy as np

from research.group5.cervical_alignment import (
    cobb_from_tangents,
    vertebra_inf_tangent,
    slip_mm,
    spineps_body,
    spineps_cobb_angle,
    spineps_endplate_tangent,
    spineps_endplate_cobb_angle,
)


def _two_stacked(upper_ap=(4, 16), lower_ap=(4, 16)):
    """Two stacked cervical bodies (C5 over C6, P-S-R) + a posterior canal."""
    seg = np.zeros((24, 34, 6), dtype=int)
    seg[lower_ap[0]:lower_ap[1], 3:15, 1:5] = 16    # C6 lower (low SI)
    seg[upper_ap[0]:upper_ap[1], 18:30, 1:5] = 15   # C5 upper (high SI)
    seg[17:22, 3:30, 1:5] = 2                        # canal posterior to both
    return seg


def test_slip_aligned_bodies_near_zero():
    s = slip_mm(_two_stacked(), ("P", "S", "R"), (1.0, 1.0, 4.0), 15, 16)
    assert s is not None and abs(s) < 1.5


def test_slip_anterior_shift_detected():
    # upper body shifted 3 voxels anteriorly -> a real slip of ~3 mm
    s = slip_mm(_two_stacked(upper_ap=(1, 13)), ("P", "S", "R"), (1.0, 1.0, 4.0), 15, 16)
    assert s is not None and 1.5 <= abs(s) <= 4.5


def test_cobb_parallel_endplates_is_zero():
    assert abs(cobb_from_tangents((1.0, 0.0), (1.0, 0.0))) < 1e-6


def test_cobb_known_angle():
    t = (math.cos(math.radians(20)), math.sin(math.radians(20)))
    assert abs(cobb_from_tangents((1.0, 0.0), t) - 20.0) < 1e-6


def test_cobb_is_a_line_angle_robust_to_tangent_ray_flip():
    # a tangent rotated 160 deg is the SAME line as -20 deg -> Cobb reads the acute line angle
    t = (math.cos(math.radians(160)), math.sin(math.radians(160)))
    assert abs(cobb_from_tangents((1.0, 0.0), t) - (-20.0)) < 1e-6


def test_vertebra_inf_tangent_uniform_body_is_horizontal():
    # synthetic P-S-R vertebra: body (label 13) anterior, canal (2) behind, posterior arch behind that.
    seg = np.zeros((32, 22, 6), dtype=int)
    seg[2:13, 4:16, 1:5] = 13         # body: AP 2-12, SI 4-15, uniform
    seg[18:29, 8:13, 1:5] = 13        # posterior arch (must be cut away)
    seg[13:18, 4:16, 1:5] = 2         # spinal canal between body and arch
    t = vertebra_inf_tangent(seg, 13, seg == 2, ("P", "S", "R"), (0.5, 1.0, 4.0))
    assert t is not None
    assert abs(t[1] / t[0]) < 0.2     # uniform body -> inferior endplate ~ along image AP


# ---- SPINEPS corpus-body consumer (Group 4 endpoint-precision pilot) --------------
# Body = (seg-spine == corpus_label, default 49) & (seg-vert == vertebra instance).
# Verified on real SPINEPS output (model T2w_semantic_v1.0.9): corpus=49, instances follow
# VerSe numbering C2=2..C7=7. Feeds the SAME endplate_lines/cobb path as the canal-cut method.


def test_spineps_body_is_corpus_intersect_instance_excluding_arch():
    spine = np.zeros((4, 20, 20), dtype=int)
    vert = np.zeros((4, 20, 20), dtype=int)
    vert[1:3, 2:18, 5:15] = 3            # whole vertebra instance 3 (body + arch)
    spine[1:3, 2:10, 5:15] = 49          # corpus (anterior body block)
    spine[1:3, 14:18, 5:15] = 41         # posterior arch subregion (not corpus)
    body = spineps_body(spine, vert, instance_label=3)
    assert body[1:3, 2:10, 5:15].all()           # body kept
    assert not body[1:3, 14:18, 5:15].any()      # arch excluded (corpus==49 only)
    assert int(body.sum()) == 2 * 8 * 10


def test_spineps_cobb_parallel_bodies_near_zero():
    # two axis-aligned corpus slabs (C5 over C6) -> endplates parallel -> Cobb ~ 0
    spine = np.zeros((6, 40, 44), dtype=int)
    vert = np.zeros((6, 40, 44), dtype=int)
    spine[1:5, 8:28, 4:18] = 49;  vert[1:5, 8:28, 4:18] = 6     # C6 (lower)
    spine[1:5, 8:28, 24:38] = 49; vert[1:5, 8:28, 24:38] = 5    # C5 (upper)
    c = spineps_cobb_angle(spine, vert, ("R", "A", "S"), (1.0, 1.0, 1.0),
                           top_instance=5, bottom_instance=6)
    assert c is not None and abs(c) < 3.0


def test_spineps_cobb_none_when_instance_absent():
    spine = np.zeros((6, 40, 44), dtype=int)
    vert = np.zeros((6, 40, 44), dtype=int)
    spine[1:5, 8:28, 4:18] = 49; vert[1:5, 8:28, 4:18] = 6     # only C6 present
    c = spineps_cobb_angle(spine, vert, ("R", "A", "S"), (1.0, 1.0, 1.0),
                           top_instance=5, bottom_instance=6)
    assert c is None


# ---- SPINEPS ENDPLATE-VOXEL Cobb (Option C1: fit the line to SPINEPS' own endplate voxels) -------
# SPINEPS writes each vertebra's inferior-endplate sheet into the instance file at label 100+X
# (verified on real output: thin sheets at the inferior body border; C2=102..C7=107). Fitting the
# line to those endplate voxels (the Wang-2023 method) beat the corpus line-fit AND the canal-cut
# Cobb on 12 healthy necks (C6-C7 SD 5.9 vs 18.5 deg). The endplate angle is consistently negative
# across subjects, so a single sign flip makes lordosis positive.


def _ep_sheet(seg, inst, ap0, ap1, si0, tilt_deg, offset=100, thick=2):
    # a thin endplate sheet for vertebra `inst` (label offset+inst), tilted tilt_deg from horizontal
    for ap in range(ap0, ap1):
        si = int(round(si0 + (ap - ap0) * math.tan(math.radians(tilt_deg))))
        for d in range(thick):
            seg[1:4, ap, si + d] = offset + inst


def test_spineps_endplate_tangent_recovers_known_tilt():
    seg = np.zeros((5, 50, 90), dtype=int)
    _ep_sheet(seg, 3, 10, 34, 40, 15.0)          # 24-wide endplate tilted +15 deg
    t = spineps_endplate_tangent(seg, 3, ("R", "A", "S"), (1.0, 1.0, 1.0))
    assert t is not None
    assert abs(abs(cobb_from_tangents((1.0, 0.0), t)) - 15.0) < 3.0


def test_spineps_endplate_cobb_parallel_sheets_near_zero():
    seg = np.zeros((5, 50, 90), dtype=int)
    _ep_sheet(seg, 3, 10, 34, 60, 10.0)
    _ep_sheet(seg, 7, 10, 34, 25, 10.0)          # same tilt -> parallel endplates
    c = spineps_endplate_cobb_angle(seg, ("R", "A", "S"), (1.0, 1.0, 1.0),
                                    top_instance=3, bottom_instance=7)
    assert c is not None and abs(c) < 3.0


def test_spineps_endplate_cobb_lordotic_arrangement_is_positive():
    # mimic real data: upper (C3) shallow, lower (C7) steeper (more negative) -> lordosis-positive
    seg = np.zeros((5, 50, 90), dtype=int)
    _ep_sheet(seg, 3, 10, 34, 70, -10.0)
    _ep_sheet(seg, 7, 10, 34, 40, -30.0)
    c = spineps_endplate_cobb_angle(seg, ("R", "A", "S"), (1.0, 1.0, 1.0),
                                    top_instance=3, bottom_instance=7)
    assert c is not None and c > 0


def test_spineps_endplate_cobb_none_when_endplate_absent():
    seg = np.zeros((5, 50, 90), dtype=int)
    _ep_sheet(seg, 3, 10, 34, 40, 0.0)           # only C3 present
    c = spineps_endplate_cobb_angle(seg, ("R", "A", "S"), (1.0, 1.0, 1.0),
                                    top_instance=3, bottom_instance=7)
    assert c is None
