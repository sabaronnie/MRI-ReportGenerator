"""Group 5.2 — vertebral fracture detection via 6-point morphometry (Genant-style).

Measures anterior (Ha), middle (Hm), posterior (Hp) vertebral-body heights from a
single-vertebra binary mask on its mid-sagittal slice, then grades deformity by
percentage height loss (Genant et al. 1993, JBMR; 6-point method: McCloskey/Hurxthal).

Cervical caveats (this project is cervical):
  - Genant/6-point are validated for T4-L4, NOT cervical -> thresholds here are the
    thoracolumbar 20/25/40% rule and should be refined to cervical-specific z-scores
    (normal cervical Ha/Hp ~= 0.97 +/- 0.02, so the 20% rule clears normal easily).
  - C1/C2 (atlas/odontoid) are structurally unique -> EXCLUDE them (caller's job);
    measure C3-C7.
  - Use the mid-sagittal slice (off-midline, uncinate processes distort endplates).
"""
import numpy as np
from scipy import ndimage
from scipy.stats import theilslopes

# Healthy cervical Ha/Hp (anterior/posterior body height ratio), measured on OUR pipeline
# from the Spine-Generic healthy cohort: 0.94 +/- 0.13 (mean +/- SD, n=60 C3-C7, 12 subjects,
# 3 vendors, 2026-06-04; native 0.8mm and 4mm-downsampled agree -> resolution-robust).
# This REPLACES the debunked in-code 0.97 +/- 0.02 "norm", which traced only to Sorci 2024
# (World J Radiol PMC11718528, a 62%-osteoporotic all-female mean-age-67.6 cohort -- NOT
# healthy) with a SD-of-level-means, not a within-population SD.
# Triangulating cadaver/radiograph literature agrees on order-of-magnitude (healthy ~0.88-0.95,
# posterior > anterior from lordotic wedging): Tan 2004 (Eur Spine J PMC3476578, mean ~0.90),
# Kaur 2025 (~0.90), Lee 2012 (PMC3393857). NOTE: no like-for-like healthy + MRI + cervical
# Ha/Hp study with comparable mean +/- SD exists, so this is triangulated PLAUSIBILITY, not a
# proven comparator -> the threshold below is derived from OUR cohort (matching our definition),
# with the literature as convergent support only.
COHORT_HAHP_MEAN = 0.94
COHORT_HAHP_SD = 0.13


def _anterior_marker(seeds, anterior):
    """Label id of the seed component spanning the anterior edge (AP=axis0)."""
    ap_present = np.where(seeds.any(axis=1))[0]
    edge = int(ap_present.min()) if anterior == "low" else int(ap_present.max())
    row = seeds[edge]
    row = row[row > 0]
    return int(np.bincount(row).argmax())


def extract_vertebral_body(mask2d, ap_axis=0, anterior="low", max_erode=14):
    """Isolate the vertebral BODY from a whole-vertebra mask on a sagittal slice.

    RSNA and TotalSpineSeg masks label the WHOLE vertebra (body + pedicles/lamina/
    spinous process). Genant morphometry needs only the body (the anterior load-bearing
    block); the spinous process projects postero-inferiorly and, if included, fakes a
    wedge deformity (this caused the RSNA false positives: Ha/Hp~0.29 on healthy bodies).

    On REAL cervical anatomy the body and posterior arch are ONE connected component on
    the mid-sagittal slice (no clean canal gap in the bone mask), joined at the pedicle
    isthmus -- which is thinner than either the body or the arch. So: erode until the
    blob separates at that thin neck, keep the two largest cores as markers, then assign
    every original voxel to its nearest marker (a marker watershed). The body is the
    partition owning the anterior-most voxel. Single compact bodies never split -> returned
    unchanged; already-separated masks (clean gap) split at erosion 0.
    """
    m = np.asarray(mask2d, dtype=bool)
    transposed = (ap_axis == 1)
    if transposed:                                   # normalize to AP=axis0
        m = m.T
    if not m.any():
        return m.T if transposed else m

    markers = None
    labels0, n0 = ndimage.label(m)
    if n0 >= 2:
        markers = labels0                            # already separated (e.g. clean gap)
    else:
        for k in range(1, max_erode + 1):            # erode until the thin neck severs
            lab, n = ndimage.label(ndimage.binary_erosion(m, iterations=k))
            if n >= 2:
                markers = lab
                break
    if markers is None:                              # never separated -> can't isolate
        return m.T if transposed else m

    sizes = np.bincount(markers.ravel()); sizes[0] = 0
    keep = [i for i in np.argsort(sizes)[::-1] if sizes[i] > 0][:2]   # body + arch cores
    seeds = np.where(np.isin(markers, keep), markers, 0)
    body_label = _anterior_marker(seeds, anterior)
    # assign every original voxel to its nearest seed (marker watershed)
    idx = ndimage.distance_transform_edt(seeds == 0, return_distances=False, return_indices=True)
    body = (seeds[tuple(idx)] == body_label) & m
    return body.T if transposed else body


def extract_body_via_canal(vert_mask, canal_mask, axcodes):
    """Isolate the vertebral BODY by cutting the whole-vertebra mask at the spinal canal.

    The most reliable body/arch separation is anatomical, not morphological: the vertebral
    body is everything ANTERIOR to the spinal canal. TotalSpineSeg outputs the canal (label
    2) alongside the whole-vertebra labels, so for each (SI, LR) column we find the canal's
    anterior face and keep only the vertebra voxels anterior to it. This avoids the failure
    of connected-component / erosion heuristics on real fused body+arch masks (which left a
    wedge-shaped body and a systematic ~0.86 anterior/posterior height ratio).

    vert_mask, canal_mask : 3D boolean arrays in the same grid. axcodes from nibabel.
    Returns the body sub-mask of vert_mask. If no canal is present, returns vert_mask
    unchanged (nothing to cut).
    """
    ap, si, lr, anterior = vertebra_axes_from_orientation(axcodes)
    V = np.asarray(vert_mask, dtype=bool)
    C = np.asarray(canal_mask, dtype=bool)
    if not C.any():
        return V
    Vt = np.moveaxis(V, (ap, si, lr), (0, 1, 2))      # -> [AP, SI, LR]
    Ct = np.moveaxis(C, (ap, si, lr), (0, 1, 2))
    nap = Vt.shape[0]
    ap_idx = np.arange(nap)[:, None, None]
    has_canal = Ct.any(axis=0)
    if anterior == "low":                              # body = low AP, canal behind it
        face = np.where(Ct, ap_idx, nap).min(axis=0).astype(float)   # canal anterior face
        face[~has_canal] = np.nan
        face = np.where(np.isnan(face), np.nanmedian(face), face)
        keep = ap_idx < face[None, :, :]
    else:                                              # body = high AP
        face = np.where(Ct, ap_idx, -1).max(axis=0).astype(float)
        face[~has_canal] = np.nan
        face = np.where(np.isnan(face), np.nanmedian(face), face)
        keep = ap_idx > face[None, :, :]
    return np.moveaxis(Vt & keep, (0, 1, 2), (ap, si, lr))


def heights_from_sagittal_mask(mask2d, ap_axis=0, si_axis=1, si_spacing=1.0,
                               anterior="low", edge_frac=0.15):
    """Anterior/middle/posterior VB heights (mm) from a single-vertebra mask on the
    mid-sagittal slice.

    mask2d    : 2D boolean mask of ONE vertebral body (mid-sagittal slice).
    ap_axis/si_axis : which axis is anterior-posterior / superior-inferior.
    anterior  : which end of the AP axis is anterior ('low' or 'high' index).
    edge_frac : fraction of AP width to average the wall heights over (avoids
                single-column noise at the cortical corners).

    Returns {"Ha","Hm","Hp"} in mm: Ha=anterior wall, Hp=posterior wall, Hm=mid (50% AP).
    """
    m = np.asarray(mask2d, dtype=bool)
    if si_axis == 0:                       # normalize to AP=axis0, SI=axis1
        m = m.T
    ap_present = np.where(m.any(axis=1))[0]
    if ap_present.size == 0:
        return {"Ha": 0.0, "Hm": 0.0, "Hp": 0.0}
    lo, hi = int(ap_present.min()), int(ap_present.max())
    width = hi - lo + 1
    k = max(1, int(round(width * edge_frac)))

    def si_extent(col):
        s = np.where(m[col])[0]
        return float((s.max() - s.min() + 1) * si_spacing) if s.size else 0.0

    low_cols = range(lo, lo + k)
    high_cols = range(hi - k + 1, hi + 1)
    ant_cols, post_cols = (low_cols, high_cols) if anterior == "low" else (high_cols, low_cols)
    mid_col = (lo + hi) // 2

    return {
        "Ha": float(np.median([si_extent(c) for c in ant_cols])),
        "Hm": si_extent(mid_col),
        "Hp": float(np.median([si_extent(c) for c in post_cols])),
    }


def vertebra_axes_from_orientation(axcodes):
    """Map nibabel axcodes -> (ap_axis, si_axis, lr_axis, anterior).

    Makes the runner orientation-robust: the input is acquired P-S-R but TotalSpineSeg
    reorients to LPI internally, so we must derive axes from the segmentation's own
    orientation rather than hard-coding them. nibabel axcodes name the END each axis
    increases toward, so 'P' means index grows toward Posterior -> anterior is the LOW
    index of that axis ('A' -> anterior is the HIGH index).

    anterior is 'low'/'high' as consumed by heights_from_sagittal_mask.
    """
    ap_axis = si_axis = lr_axis = anterior = None
    for axis, code in enumerate(axcodes):
        if code in ("A", "P"):
            ap_axis, anterior = axis, ("high" if code == "A" else "low")
        elif code in ("S", "I"):
            si_axis = axis
        elif code in ("L", "R"):
            lr_axis = axis
    if None in (ap_axis, si_axis, lr_axis):
        raise ValueError(f"axcodes must cover AP, SI and LR exactly once: {axcodes}")
    return ap_axis, si_axis, lr_axis, anterior


def mid_sagittal_index(mask3d, lr_axis):
    """Index along lr_axis where a single-vertebra mask has the largest in-slice area.

    For a sagittal-slice volume this is the slice through the middle of the vertebral
    body (most voxels) -- avoids parasagittal slices where the uncinate processes
    distort the endplates (the cervical caveat).
    """
    m = np.asarray(mask3d, dtype=bool)
    other = tuple(ax for ax in range(m.ndim) if ax != lr_axis)
    return int(np.argmax(m.sum(axis=other)))


def endplate_line_heights(mask2d, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0,
                          anterior="low", nbins=12, margin=0.15):
    """Tilt-robust Ha/Hm/Hp (mm) via PCA orientation + endplate-line fitting.

    Measures on the vertebral body's OWN axes (PCA), correcting cervical tilt, then fits
    straight lines to the superior and inferior endplate boundaries and reads the gap at
    the anterior / posterior body margins. The line fit ignores rounded corner tips and
    thin posterior tails that wreck raw per-column SI-extent. Validated on real Duke T2:
    per-vertebra Ha/Hp spread [0.77, 1.01] vs [0.64, 4.60] for the old image-axis method.

    margin : where along the body's AP axis to read each wall (fraction in from the end).
    """
    fit = _endplate_fit(mask2d, ap_axis, si_axis, ap_spacing, si_spacing, anterior, nbins, robust=False)
    if fit is None:
        return {"Ha": 0.0, "Hm": 0.0, "Hp": 0.0}
    mt, bt, mb, bb, lo, rng = fit["mt"], fit["bt"], fit["mb"], fit["bb"], fit["lo"], fit["rng"]
    gap = lambda ap_pos: abs(float((mt * ap_pos + bt) - (mb * ap_pos + bb)))
    return {
        "Ha": gap(lo + (1 - margin) * rng),         # anterior = high a
        "Hm": gap(lo + 0.5 * rng),
        "Hp": gap(lo + margin * rng),
    }


def _endplate_fit(mask2d, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0,
                  anterior="low", nbins=12, robust=False):
    """Shared core for the endplate-line measurements: PCA-orient the body, bin along its AP axis,
    drop thin tails, and fit straight lines to the superior and inferior endplate boundaries.
    Returns the fit (PCA basis in image-mm coords + line params in the oriented frame) or None.
    The oriented frame is sign-fixed: `a` increases toward anterior, `s` toward +image-SI, so the
    basis is consistent across vertebrae (needed for a consistent Cobb sign). robust=True uses
    Theil-Sen (resistant to osteophyte tails) instead of least squares.
    """
    m = np.asarray(mask2d, dtype=bool)
    pts = np.argwhere(m).astype(float)
    if len(pts) < 20:
        return None
    coords = np.column_stack([pts[:, ap_axis] * ap_spacing, pts[:, si_axis] * si_spacing])
    mean = coords.mean(0)
    c = coords - mean
    _, evecs = np.linalg.eigh(np.cov(c.T))
    iap = int(np.argmax(np.abs(evecs[0, :])))      # eigenvector most aligned with image-AP
    u_ap, u_si = evecs[:, iap], evecs[:, 1 - iap]
    ant_vec = np.array([-1.0, 0.0]) if anterior == "low" else np.array([1.0, 0.0])
    if u_ap @ ant_vec < 0:
        u_ap = -u_ap                               # 'a' increases toward anterior
    if u_si[1] < 0:
        u_si = -u_si                               # 's' increases toward +image-SI (consistent)
    a, s = c @ u_ap, c @ u_si
    lo, hi = float(a.min()), float(a.max())
    rng = hi - lo
    if rng <= 0:
        return None
    edges = np.linspace(lo, hi, nbins + 1)
    ac, top, bot = [], [], []
    for i in range(nbins):
        sel = (a >= edges[i]) & (a < edges[i + 1])
        if sel.sum() < 2:
            continue
        ac.append(0.5 * (edges[i] + edges[i + 1]))
        top.append(float(s[sel].max()))
        bot.append(float(s[sel].min()))
    if len(ac) < 4:
        return None
    ac, top, bot = np.array(ac), np.array(top), np.array(bot)
    # Drop abruptly-thin bins (posterior tail / rounded tip); a gradual wedge stays above the cut.
    bin_h = top - bot
    keep = bin_h >= 0.4 * np.median(bin_h)
    if keep.sum() >= 4:
        ac, top, bot = ac[keep], top[keep], bot[keep]
    if robust:
        mt, bt = theilslopes(top, ac)[:2]           # superior endplate line (Theil-Sen)
        mb, bb = theilslopes(bot, ac)[:2]           # inferior endplate line
    else:
        mt, bt = np.polyfit(ac, top, 1)
        mb, bb = np.polyfit(ac, bot, 1)
    return {"u_ap": u_ap, "u_si": u_si, "mean": mean,
            "mt": float(mt), "bt": float(bt), "mb": float(mb), "bb": float(bb),
            "lo": lo, "hi": hi, "rng": rng}


def endplate_lines(mask2d, ap_axis=0, si_axis=1, ap_spacing=1.0, si_spacing=1.0,
                   anterior="low", nbins=12, margin=0.15):
    """Expose the fitted superior/inferior endplate lines + the 4 corners, for Cobb and slip.

    Built on the same PCA + line-fit core validated for heights, but returns the geometry the
    angular/directional measurements need -- the literature-validated way is to derive corners and
    angles from the ENDPLATE LINE, not from corner extrema (Wang 2023: line-fit ICC 0.97 vs 0.75,
    because cervical endplates are concave/sloped). Robust Theil-Sen fit. Returns None if unmeasurable.

    Returns {"corners": {AS,PS,AI,PI -> (ap_mm, si_mm)},
             "inf_tangent": unit (ap,si) direction of the inferior endplate line,
             "sup_tangent": unit (ap,si) direction of the superior endplate line}.
    The angle between two vertebrae's inferior tangents is their inter-endplate (Cobb) angle.
    """
    fit = _endplate_fit(mask2d, ap_axis, si_axis, ap_spacing, si_spacing, anterior, nbins, robust=True)
    if fit is None:
        return None
    u_ap, u_si, mean = fit["u_ap"], fit["u_si"], fit["mean"]
    mt, bt, mb, bb, lo, rng = fit["mt"], fit["bt"], fit["mb"], fit["bb"], fit["lo"], fit["rng"]

    def to_img(av, sv):                              # oriented (a,s) -> image (ap_mm, si_mm)
        p = mean + av * u_ap + sv * u_si
        return (float(p[0]), float(p[1]))

    def unit(v):
        n = float(np.hypot(v[0], v[1]))
        return (float(v[0] / n), float(v[1] / n)) if n else (float(v[0]), float(v[1]))

    a_ant, a_post = lo + (1 - margin) * rng, lo + margin * rng
    corners = {
        "AS": to_img(a_ant, mt * a_ant + bt), "AI": to_img(a_ant, mb * a_ant + bb),
        "PS": to_img(a_post, mt * a_post + bt), "PI": to_img(a_post, mb * a_post + bb),
    }
    return {"corners": corners,
            "inf_tangent": unit(u_ap + mb * u_si),
            "sup_tangent": unit(u_ap + mt * u_si),
            "inf_slope": float(mb),      # endplate slope in the body's OWN frame; |slope| large = bad fit
            "sup_slope": float(mt)}


def measure_vertebra(vb_mask3d, axcodes, zooms, isolate_body=True):
    """6-point Ha/Hm/Hp heights (mm) for ONE vertebra's 3D binary mask.

    Derives AP/SI/LR axes from `axcodes` (orientation-robust), picks the vertebra's own
    mid-sagittal slice, optionally drops the posterior arch, then measures via
    `endplate_line_heights` (PCA tilt-orient + endplate-line fit). This combination is
    what made the morphometry reliable on real Duke T2 (per-vertebra Ha/Hp [0.77,1.01]
    vs [0.64,4.60] for the old image-axis edge measurement).

    isolate_body : when True, run the morphological body isolation (anterior connected
                   component) -- the fallback when no spinal canal is available. Pass
                   False when the body was already cut anatomically via the canal
                   (`extract_body_via_canal` in the runner), which is preferred.
    """
    m = np.asarray(vb_mask3d, dtype=bool)
    ap, si, lr, anterior = vertebra_axes_from_orientation(axcodes)
    mid = mid_sagittal_index(m, lr)
    sl = [slice(None)] * m.ndim
    sl[lr] = mid
    slice2d = m[tuple(sl)]
    remaining = sorted(a for a in range(m.ndim) if a != lr)   # the 2 in-slice axes, in order
    slice_ap = remaining.index(ap)
    if isolate_body:
        slice2d = extract_vertebral_body(slice2d, ap_axis=slice_ap, anterior=anterior)
    return endplate_line_heights(
        slice2d, ap_axis=slice_ap, si_axis=remaining.index(si),
        ap_spacing=float(zooms[ap]), si_spacing=float(zooms[si]), anterior=anterior,
    )


def fracture_confusion(pairs):
    """Confusion counts + sensitivity/specificity from (predicted_flag, truth_label) pairs.

    Used to score the fracture detector against expert per-vertebra labels (e.g. RSNA-2022).
    sensitivity = TP/(TP+FN) (fraction of real fractures caught); specificity = TN/(TN+FP)
    (fraction of healthy vertebrae correctly left alone). A rate is None when its denominator
    is 0 (e.g. no real fractures in the sample -> sensitivity undefined).
    """
    tp = sum(1 for p, t in pairs if p and t)
    fp = sum(1 for p, t in pairs if p and not t)
    tn = sum(1 for p, t in pairs if not p and not t)
    fn = sum(1 for p, t in pairs if not p and t)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn, "n": len(pairs),
        "sensitivity": tp / (tp + fn) if (tp + fn) else None,
        "specificity": tn / (tn + fp) if (tn + fp) else None,
    }


def classify_genant(heights, ref_post=None, grade1=0.20, grade2=0.25, grade3=0.40):
    """Genant-style deformity grade + type from Ha/Hm/Hp.

    Height loss is taken relative to the posterior wall (wedge, biconcave) and, when a
    reference posterior height from adjacent vertebrae is supplied, relative to that
    (crush/compression). Grades: >=20% (1, mild), >=25% (2, moderate), >=40% (3, severe).
    Type = the deformity with the largest height loss (wedge=Ha, biconcave=Hm, crush=Hp).
    """
    Ha, Hm, Hp = heights["Ha"], heights["Hm"], heights["Hp"]
    losses = {}
    if Hp > 0:
        losses["wedge"] = max(0.0, 1.0 - Ha / Hp)
        losses["biconcave"] = max(0.0, 1.0 - Hm / Hp)
    if ref_post and ref_post > 0:
        losses["crush"] = max(0.0, 1.0 - Hp / ref_post)
    if not losses:
        return {"type": "normal", "grade": 0, "height_loss": 0.0}

    typ = max(losses, key=losses.get)
    loss = losses[typ]
    grade = 3 if loss >= grade3 else 2 if loss >= grade2 else 1 if loss >= grade1 else 0
    return {"type": typ if grade > 0 else "normal", "grade": grade, "height_loss": float(loss)}


def cervical_deformity_flag(ratio, mean=COHORT_HAHP_MEAN, sd=COHORT_HAHP_SD, z=2.0):
    """Data-driven cervical vertebral-body COMPRESSION/deformity SCREEN flag from Ha/Hp.

    This is SEPARATE from `classify_genant` (which stays the medical Genant standard at
    20/25/40% loss). Here we flag a cervical body whose anterior/posterior ratio falls
    `z` SDs below the measured healthy-cohort mean -- i.e. ratio < mean - z*sd. With the
    defaults (Spine-Generic healthy 0.94 +/- 0.13, z=2) the threshold is ~0.68, chosen for
    SPECIFICITY: it catches moderate-severe compression and will MISS mild wedging
    (Ha/Hp ~0.78). `z` is an EXPOSED policy knob (a team/AUBMC sensitivity-vs-specificity
    decision), deliberately NOT hardcoded as a clinical claim. The continuous `zscore` is
    returned so a borderline body is visible to the physician even when not flagged.

    SCOPE CAVEAT (keep honest): this is a vertebral-body compression/deformity screen for
    physician review, NOT a validated general fracture detector -- on RSNA-2022 the geometric
    wedge metric had ~zero power for non-compression cervical fractures (odontoid/facet/arch).
    Per-vertebra SD is wide (0.13) -> reliable at the group/screening level, coarse per body.

    Returns {"flagged": bool, "zscore": float, "threshold": float}.
    """
    threshold = mean - z * sd
    return {
        "flagged": bool(ratio < threshold),
        "zscore": float((ratio - mean) / sd),
        "threshold": float(threshold),
    }
