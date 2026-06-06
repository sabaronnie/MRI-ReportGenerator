"""Cervical sagittal alignment (Cobb / segmental angles) from fitted ENDPLATE LINES.

The validated fix for the corrupted angular outputs (Ronnie's C3-C7 Cobb read -21 deg = kyphotic on
healthy lordotic necks). Root cause was single-corner extrema on cervical endplates that are concave
and sloped (Chen 2013); the literature-validated method is to fit a LINE to the full endplate and take
the angle between lines (Wang 2023, cervical CT: line-fit ICC 0.97 vs four-corner 0.75). This module
builds the C2/C3 -> C7 Cobb on the inferior-endplate tangents exposed by vertebral_fracture.endplate_lines
(canal-cut body + PCA + Theil-Sen line fit).

Sign convention: lordosis POSITIVE. The raw geometric sign is calibrated to the healthy cohort
(supine MRI healthy cervical Cobb is lordotic ~ +9-11 deg) via LORDOSIS_SIGN below.
"""
import math

import numpy as np

from vertebral_fracture import (
    endplate_lines,
    extract_body_via_canal,
    mid_sagittal_index,
    vertebra_axes_from_orientation,
)

# Sign that makes lordosis positive for our (TSS step2, canal-cut, anterior/+SI-fixed) frame.
# Calibrated on the 12 healthy Spine-Generic necks (healthy supine cervical is lordotic, +9-11 deg).
LORDOSIS_SIGN = 1

# A real cervical endplate is within ~45 deg of the image AP axis. A larger image-frame tangent
# slope means the body isolation / PCA orientation failed for that vertebra (the malformed C6/C7
# canal-cut body whose principal axis comes out near-vertical, esp. at the cervicothoracic junction
# where C7-inferior is obscured ~25-32%). Above this, fall back to the other endplate, else treat the
# vertebra as not measurable (the literature-honest "C7 obscured" outcome).
ENDPLATE_MAX_IMG_SLOPE = 1.0


def cobb_from_tangents(t1, t2):
    """Signed Cobb-style angle (deg) between two endplate tangents, as a LINE angle in (-90, 90].

    Taking the line angle (not the ray angle) makes it robust to the endplate tangent's arbitrary
    +/- direction (the PCA basis can flip), which is exactly the stability the corner method lacked.
    """
    ang = math.degrees(math.atan2(t1[0] * t2[1] - t1[1] * t2[0], t1[0] * t2[0] + t1[1] * t2[1]))
    if ang > 90:
        ang -= 180
    elif ang <= -90:
        ang += 180
    return ang


def _vertebra_endplate(seg3d, label, canal, axcodes, zooms):
    """Full endplate_lines dict (tangents + slopes + corners) for one vertebra label, or None.
    Canal-cut body isolation -> mid-sagittal slice -> endplate_lines."""
    ap, si, lr, anterior = vertebra_axes_from_orientation(axcodes)
    vert = np.asarray(seg3d) == label
    if not vert.any():
        return None
    body = extract_body_via_canal(vert, canal, axcodes) if canal.any() else vert
    mid = mid_sagittal_index(body, lr)
    sl = [slice(None)] * body.ndim
    sl[lr] = mid
    slice2d = body[tuple(sl)]
    remaining = sorted(a for a in range(body.ndim) if a != lr)
    return endplate_lines(
        slice2d, ap_axis=remaining.index(ap), si_axis=remaining.index(si),
        ap_spacing=float(zooms[ap]), si_spacing=float(zooms[si]), anterior=anterior,
    )


def _reliable_tangent(el, prefer="inf", max_img_slope=ENDPLATE_MAX_IMG_SLOPE):
    """Pick a trustworthy endplate tangent: the preferred endplate if its IMAGE-frame slope is sane
    (within ~45 deg of horizontal), else the other endplate (e.g. C7-superior when C7-inferior is
    obscured), else None (vertebra not measurable -> the Cobb is reported as low-confidence/None)."""
    if el is None:
        return None
    order = (("inf", "sup") if prefer == "inf" else ("sup", "inf"))
    for which in order:
        t = el[f"{which}_tangent"]
        if t[0] != 0 and abs(t[1] / t[0]) <= max_img_slope:
            return t
    return None


def vertebra_inf_tangent(seg3d, label, canal, axcodes, zooms):
    """Inferior-endplate tangent (unit vector in image ap,si mm) for one vertebra label, or None."""
    el = _vertebra_endplate(seg3d, label, canal, axcodes, zooms)
    return el["inf_tangent"] if el else None


def cobb_angle(seg3d, axcodes, zooms, top_label, bottom_label, canal_label=2):
    """Cobb angle (deg, lordosis-positive) between the inferior endplates of two vertebra labels.

    Default use: C2-C7 (12, 17) or C3-C7 (13, 17). Uses the inferior endplate of each vertebra, with
    an automatic fallback to that vertebra's SUPERIOR endplate when the inferior line fit is
    unreliable (the C7-obscured case). Returns None if either endplate is unmeasurable.
    NOTE: supine MRI reads ~5 deg less lordotic than standing radiographs -- apply a supine->standing
    offset before comparing to radiograph norms.
    """
    seg = np.asarray(seg3d)
    canal = seg == canal_label
    t_top = _reliable_tangent(_vertebra_endplate(seg, top_label, canal, axcodes, zooms))
    t_bot = _reliable_tangent(_vertebra_endplate(seg, bottom_label, canal, axcodes, zooms))
    if t_top is None or t_bot is None:
        return None
    return LORDOSIS_SIGN * cobb_from_tangents(t_top, t_bot)
