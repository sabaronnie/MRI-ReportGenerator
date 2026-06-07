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

from services.measurements.group5.vertebral_fracture import (
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


def _endplate_from_body(body, axcodes, zooms, margin=0.15):
    """Fit endplate lines on an already-isolated 3D vertebral-BODY mask, or None.

    Shared tail for both body-isolation sources (canal-cut and SPINEPS corpus): pick the body's
    mid-sagittal slice, then fit the superior/inferior endplate lines. `margin` sets how far in
    from the body edge the corners are read.
    """
    ap, si, lr, anterior = vertebra_axes_from_orientation(axcodes)
    body = np.asarray(body, dtype=bool)
    if not body.any():
        return None
    mid = mid_sagittal_index(body, lr)
    sl = [slice(None)] * body.ndim
    sl[lr] = mid
    slice2d = body[tuple(sl)]
    remaining = sorted(a for a in range(body.ndim) if a != lr)
    return endplate_lines(
        slice2d, ap_axis=remaining.index(ap), si_axis=remaining.index(si),
        ap_spacing=float(zooms[ap]), si_spacing=float(zooms[si]), anterior=anterior, margin=margin,
    )


def _vertebra_endplate(seg3d, label, canal, axcodes, zooms, margin=0.15):
    """Full endplate_lines dict for one vertebra label via CANAL-CUT body isolation, or None.
    `margin` sets how far in from the body edge the corners are read (small margin -> true
    posterior/anterior edge, for slip)."""
    vert = np.asarray(seg3d) == label
    if not vert.any():
        return None
    body = extract_body_via_canal(vert, canal, axcodes) if canal.any() else vert
    return _endplate_from_body(body, axcodes, zooms, margin)


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


def _endplate_reliable(el):
    """True if the body's endplate orientation is trustworthy (a sane, non-vertical tangent exists)."""
    return _reliable_tangent(el) is not None


def vertebra_inf_tangent(seg3d, label, canal, axcodes, zooms):
    """Inferior-endplate tangent (unit vector in image ap,si mm) for one vertebra label, or None."""
    el = _vertebra_endplate(seg3d, label, canal, axcodes, zooms)
    return el["inf_tangent"] if el else None


def slip_mm(seg3d, axcodes, zooms, upper_label, lower_label, canal_label=2):
    """EXPERIMENTAL spondylolisthesis slip (mm), line-derived (NOT validated for screening).

    Uses the posterior corners of the fitted endplate lines (line-derived per de Dios 2023, not
    single-corner extrema): image-AP offset between the upper body's posterior-inferior corner and
    the lower body's posterior-superior corner. Returns None if either body's orientation is
    unreliable (the C6/C7-obscured case).

    STATUS (validated on 12 healthy necks): the line-derived approach modestly improves the spread
    (pooled SD ~2.9 mm vs the corner-extrema method's 3.7 mm) but still carries a systematic ~3 mm
    offset on real lordotic necks (both this AP-difference and a perpendicular-to-lower-wall variant
    are biased), so it does NOT yet meet the <1.5 mm de Dios noise floor and must NOT be used as a
    screening flag yet. Closing the gap needs the proper de Dios posterior-surface measurement in the
    lower-body frame + better C6/C7 body isolation (SPINEPS corpus) + 1-2 radiologist-labelled cases
    to calibrate the sign/offset. Magnitude is what the healthy-cohort SD check uses.
    """
    seg = np.asarray(seg3d)
    canal = seg == canal_label
    up = _vertebra_endplate(seg, upper_label, canal, axcodes, zooms)
    lo = _vertebra_endplate(seg, lower_label, canal, axcodes, zooms)
    if not (_endplate_reliable(up) and _endplate_reliable(lo)):
        return None
    return float(up["corners"]["PI"][0] - lo["corners"]["PS"][0])   # image-AP offset (mm), uncalibrated


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


# ---- SPINEPS corpus-body source (learned body/arch split; the J8 endpoint-precision upgrade) ----
# Cervical vertebra instances under the VerSe numbering SPINEPS emits (verified on real output,
# model T2w_semantic_v1.0.9): C2=2, C3=3, C4=4, C5=5, C6=6, C7=7.
CERVICAL_INSTANCES = {"C2": 2, "C3": 3, "C4": 4, "C5": 5, "C6": 6, "C7": 7}
SPINEPS_CORPUS_LABEL = 49


def spineps_body(seg_spine, seg_vert, instance_label, corpus_label=SPINEPS_CORPUS_LABEL):
    """Vertebral BODY mask from SPINEPS outputs: corpus subregion INTERSECT this vertebra instance.

    seg_spine : SPINEPS semantic mask (vertebra corpus = corpus_label, default 49).
    seg_vert  : SPINEPS instance mask (each vertebra a distinct label; VerSe C2=2..C7=7).
    The intersection keeps only the load-bearing body, dropping the posterior arch automatically
    (a learned body/arch split, corpus DSC ~0.95) -- the upgrade over canal-cut isolation that
    mis-shapes C6/C7 at the cervicothoracic junction (J8). VERIFY corpus_label/instances on the
    first mask of any new SPINEPS model version (IDs vary by version).
    """
    return (np.asarray(seg_spine) == corpus_label) & (np.asarray(seg_vert) == instance_label)


def _spineps_vertebra_endplate(seg_spine, seg_vert, instance_label, axcodes, zooms,
                               corpus_label=SPINEPS_CORPUS_LABEL, margin=0.15):
    """endplate_lines dict for one vertebra instance via SPINEPS corpus-body isolation, or None."""
    body = spineps_body(seg_spine, seg_vert, instance_label, corpus_label)
    return _endplate_from_body(body, axcodes, zooms, margin)


def spineps_cobb_angle(seg_spine, seg_vert, axcodes, zooms, top_instance, bottom_instance,
                       corpus_label=SPINEPS_CORPUS_LABEL):
    """Cobb angle (deg, lordosis-positive) between two vertebrae using the SPINEPS corpus body.

    Same inferior-endplate-line method + reliability fallback as `cobb_angle`, but the body comes
    from the SPINEPS corpus instead of the canal cut. Returns None if either endplate is
    unmeasurable. NOTE the same supine->standing offset caveat as `cobb_angle`.
    """
    t_top = _reliable_tangent(
        _spineps_vertebra_endplate(seg_spine, seg_vert, top_instance, axcodes, zooms, corpus_label)
    )
    t_bot = _reliable_tangent(
        _spineps_vertebra_endplate(seg_spine, seg_vert, bottom_instance, axcodes, zooms, corpus_label)
    )
    if t_top is None or t_bot is None:
        return None
    return LORDOSIS_SIGN * cobb_from_tangents(t_top, t_bot)


# ---- SPINEPS endplate-VOXEL Cobb (Option C1: the validated line-fit on the REAL endplate voxels) --
# SPINEPS writes each vertebra's inferior-endplate sheet into the INSTANCE mask at label
# SPINEPS_ENDPLATE_OFFSET + instance (verified on real output: thin sheets at the inferior body
# border; C2=102..C7=107). Fitting the line directly to those endplate voxels is the
# literature-validated method (Wang 2023: line-fit ICC 0.97 vs four-corner 0.75); on 12 healthy
# Spine-Generic necks it beat BOTH the corpus line-fit and the canal-cut Cobb on precision + C7
# coverage (C6-C7 SD 5.9 vs canal-cut 18.5 deg; C2-C7 13.7 vs 16.6). The raw endplate angle is
# consistently negative across subjects, so SPINEPS_ENDPLATE_SIGN flips it to lordosis-positive
# (calibrated on the 12 necks; healthy mean ~+15 deg matches the F1000 literature mean 15.4 deg).
SPINEPS_ENDPLATE_OFFSET = 100
SPINEPS_ENDPLATE_SIGN = -1


def spineps_endplate_tangent(seg_vert, instance_label, axcodes, zooms,
                             offset=SPINEPS_ENDPLATE_OFFSET, min_voxels=20):
    """Inferior-endplate tangent (unit ap,si) for one vertebra, fit to SPINEPS' endplate voxels.

    The endplate sheet for vertebra X is label (offset + X) in the instance mask (offset=100 verified
    = the inferior endplate). On the sheet's mid-sagittal slice, the PCA major axis of the thin
    AP-elongated sheet IS the endplate orientation -- no body isolation needed. Returns None if the
    endplate is absent or too small to fit (the literature-honest "level not measurable" case).
    """
    ap, si, lr, _ = vertebra_axes_from_orientation(axcodes)
    ep = np.asarray(seg_vert) == (offset + instance_label)
    if ep.sum() < min_voxels:
        return None
    mid = mid_sagittal_index(ep, lr)
    sl = [slice(None)] * ep.ndim
    sl[lr] = mid
    slice2d = ep[tuple(sl)]
    remaining = sorted(a for a in range(ep.ndim) if a != lr)
    pts = np.argwhere(slice2d).astype(float)
    if len(pts) < 8:
        return None
    coords = np.column_stack([
        pts[:, remaining.index(ap)] * float(zooms[ap]),
        pts[:, remaining.index(si)] * float(zooms[si]),
    ])
    c = coords - coords.mean(0)
    _, evecs = np.linalg.eigh(np.cov(c.T))
    t = evecs[:, -1]                                  # major axis = endplate elongation = tangent
    return (float(t[0]), float(t[1]))


def spineps_endplate_cobb_angle(seg_vert, axcodes, zooms, top_instance, bottom_instance,
                                offset=SPINEPS_ENDPLATE_OFFSET):
    """Cobb angle (deg, lordosis-positive) between two vertebrae's INFERIOR endplates, fit directly to
    SPINEPS' endplate voxels (Option C1). Needs only the instance mask (seg_vert). Returns None if
    either endplate is unmeasurable. Same supine->standing caveat as cobb_angle; no radiologist GT yet,
    so this is validated on PRECISION + coverage, not absolute accuracy (target ceiling Zhang 2025:
    ICC 0.94 / MAE 2.44 deg on sagittal-T2 C2-C7).
    """
    t_top = spineps_endplate_tangent(seg_vert, top_instance, axcodes, zooms, offset)
    t_bot = spineps_endplate_tangent(seg_vert, bottom_instance, axcodes, zooms, offset)
    if t_top is None or t_bot is None:
        return None
    return SPINEPS_ENDPLATE_SIGN * cobb_from_tangents(t_top, t_bot)
