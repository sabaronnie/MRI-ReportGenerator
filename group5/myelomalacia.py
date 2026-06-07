"""Group 5.1 prototype — detect abnormally high cord signal, per level.

The mechanic Andrew asked about, made concrete:
  1. use the segmentation MASK to locate the cord,
  2. read the raw MRI INTENSITIES inside it,
  3. normalize each level against a LOCAL reference (nearby levels), so neither
     the scanner's arbitrary scale NOR a smooth intensity gradient (bias field)
     fools us — both cancel locally,
  4. flag levels whose ratio exceeds a threshold.

We learned the hard way (sub-oxfordFmrib: 22 false alarms) that a *global* cord
reference cannot survive a within-scan intensity gradient. A local reference can.
The true Weber-2023 T2-MI (cord-vs-CSF at the same level) is the clinical version
of this same "use a local reference" idea; it needs a CSF/canal mask too.
"""
import numpy as np


def detect_cord_signal_abnormality(
    mri, cord_mask, level_axis=2, threshold_ratio=1.3, window=10
):
    """Flag levels where median cord signal is abnormally high vs *nearby* levels.

    Returns a list of {"level": int, "ratio": float}, one per flagged level.
    `window` = how many levels on each side form the local reference.
    """
    cord = cord_mask == 1
    n_levels = mri.shape[level_axis]

    # Median cord intensity at each level (None where the cord is absent).
    level_median = [None] * n_levels
    for level in range(n_levels):
        sl = [slice(None)] * mri.ndim
        sl[level_axis] = level
        level_cord = cord[tuple(sl)]
        if level_cord.any():
            level_median[level] = float(np.median(mri[tuple(sl)][level_cord]))

    flags = []
    for level in range(n_levels):
        if level_median[level] is None:
            continue
        # Local reference: median of nearby levels' cord medians (this level excluded).
        neighbors = [
            level_median[j]
            for j in range(level - window, level + window + 1)
            if 0 <= j < n_levels and j != level and level_median[j] is not None
        ]
        if not neighbors:
            continue
        local_ref = float(np.median(neighbors))
        ratio = level_median[level] / local_ref
        if ratio >= threshold_ratio:
            flags.append({"level": level, "ratio": ratio})
    return flags


def detect_myelopathy_index(mri, cord_mask, csf_mask, level_axis=2, threshold=0.75,
                            csf_percentile=75):
    """Cord-vs-CSF signal ratio per level (the basis of Weber 2023's T2-MI).

    On T2, healthy cord is darker than CSF, so cord/CSF sits below 1. Myelomalacia
    brightens the cord toward CSF, pushing the ratio up. We flag levels where
    cord/CSF >= threshold. Because CSF sits right next to the cord at every level,
    this also cancels scanner scale and bias-field gradients — AND, unlike the
    cord-vs-cord method, it catches a *diffusely* bright cord (external reference).

    The CSF reference is a high PERCENTILE (default 75th), not the median: the
    canal-minus-cord mask includes darker partial-volume voxels at the canal edges
    that drag a median down and inflate the ratio (this caused 67 false flags on
    real Duke case 1). CSF is the bright tissue, so its upper percentile is the
    robust estimate of true CSF signal.

    NOTE: the threshold (0.75) is still a placeholder — calibrate against the Weber
    2023 paper + ROC on labeled (AUBMC) data before any clinical claim.

    Returns a list of {"level": int, "t2_mi": float}.
    """
    cord = cord_mask == 1
    csf = csf_mask == 1

    flags = []
    for level in range(mri.shape[level_axis]):
        sl = [slice(None)] * mri.ndim
        sl[level_axis] = level
        level_cord = cord[tuple(sl)]
        level_csf = csf[tuple(sl)]
        if not level_cord.any() or not level_csf.any():
            continue  # need both cord and CSF present at this level
        cord_si = float(np.median(mri[tuple(sl)][level_cord]))
        csf_si = float(np.percentile(mri[tuple(sl)][level_csf], csf_percentile))
        if csf_si == 0:
            continue
        ratio = cord_si / csf_si
        if ratio >= threshold:
            flags.append({"level": level, "t2_mi": ratio})
    return flags


def detect_focal_hyperintensity(mri, cord_mask, level_axis=2, percentile=90,
                                threshold_ratio=1.4):
    """Flag levels where the BRIGHT tail of cord signal is anomalously high vs the
    cord's overall baseline.

    Unlike the median methods, this is sensitive to small focal intramedullary
    lesions: the lesion is a bright OUTLIER occupying only part of the cord
    cross-section, so the median washes it out, but a high percentile (p90) of the
    cord intensities at that level catches it. Validated against SCIseg on real Duke
    data, where the median method had 0 sensitivity because the lesion (~240) was
    diluted by surrounding normal cord (~185) in the per-level median.

    Per level: take the `percentile` of cord intensities, compare to the cord's
    overall median baseline, flag if ratio >= threshold_ratio.
    """
    cord = cord_mask == 1
    baseline = float(np.median(mri[cord]))
    if baseline == 0:
        return []
    flags = []
    for level in range(mri.shape[level_axis]):
        sl = [slice(None)] * mri.ndim
        sl[level_axis] = level
        level_cord = cord[tuple(sl)]
        if not level_cord.any():
            continue
        bright = float(np.percentile(mri[tuple(sl)][level_cord], percentile))
        ratio = bright / baseline
        if ratio >= threshold_ratio:
            flags.append({"level": level, "ratio": ratio})
    return flags
