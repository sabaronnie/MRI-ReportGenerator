"""Cervical sagittal alignment (Cobb) from fitted endplate LINES, not corner extrema.

The literature-validated fix for the corrupted angular outputs (Wang 2023: line-fit ICC 0.97 vs
0.75 four-corner): derive the Cobb angle from the inferior-endplate lines of C2/C3 and C7. These
tests cover the pure angle geometry + the per-vertebra tangent extraction; the lordosis sign and
the +9-11 deg healthy expectation are validated on the 12 Spine-Generic necks separately.
"""
import math

import numpy as np

from cervical_alignment import cobb_from_tangents, vertebra_inf_tangent


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
