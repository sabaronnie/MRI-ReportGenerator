"""Group 5.1 — myelomalacia (cord T2 signal abnormality) detection.

Two detectors under test:
  - detect_cord_signal_abnormality: compares cord to NEARBY CORD levels (local,
    no CSF needed). Robust to scanner scale + bias-field gradients.
  - detect_myelopathy_index: compares cord to CSF at the SAME level (the cord-vs-CSF
    ratio underlying Weber 2023's T2 Myelopathy Index). Adds an EXTERNAL reference,
    so it can catch a diffusely-bright cord that the cord-vs-cord method misses.
"""
import numpy as np

from services.measurements.group5.research.myelomalacia import detect_cord_signal_abnormality


def test_flags_abnormally_bright_cord_level():
    # Synthetic volume (X, Y, Z); Z is the head->foot "level" axis.
    mri = np.zeros((20, 20, 12), dtype=float)
    cord_mask = np.zeros_like(mri, dtype=int)
    cord_mask[9:11, 9:11, :] = 1
    mri[cord_mask == 1] = 100.0

    level_index = np.arange(mri.shape[2])[None, None, :]
    bright = (cord_mask == 1) & (level_index == 6)
    mri[bright] = 160.0

    flags = detect_cord_signal_abnormality(
        mri, cord_mask, level_axis=2, threshold_ratio=1.3
    )
    flagged_levels = [f["level"] for f in flags]
    assert flagged_levels == [6]


def test_smooth_intensity_gradient_is_not_flagged():
    """Reproduces the real sub-oxfordFmrib bug: a HEALTHY cord whose brightness
    drifts smoothly head->foot (a scanner bias field, not disease) must NOT be
    flagged.
    """
    mri = np.zeros((20, 20, 60), dtype=float)
    cord_mask = np.zeros_like(mri, dtype=int)
    cord_mask[9:11, 9:11, :] = 1

    gradient = np.linspace(80.0, 160.0, mri.shape[2])
    for k in range(mri.shape[2]):
        level_sel = cord_mask[:, :, k] == 1
        mri[:, :, k][level_sel] = gradient[k]

    flags = detect_cord_signal_abnormality(
        mri, cord_mask, level_axis=2, threshold_ratio=1.3
    )
    assert flags == []


def _t2_phantom_with_cord_and_csf():
    """T2-like phantom: CSF very bright (200), healthy cord darker (80)."""
    mri = np.zeros((20, 20, 12), dtype=float)
    cord_mask = np.zeros_like(mri, dtype=int)
    csf_mask = np.zeros_like(mri, dtype=int)
    cord_mask[9:11, 9:11, :] = 1   # cord column
    csf_mask[6:8, 9:11, :] = 1     # CSF beside the cord, every level
    mri[csf_mask == 1] = 200.0     # CSF bright on T2
    mri[cord_mask == 1] = 80.0     # healthy cord = darker
    return mri, cord_mask, csf_mask


def test_weber_flags_focal_cord_bright_relative_to_csf():
    """A focal lesion: at one level the cord is bright (near CSF). cord/CSF jumps."""
    from services.measurements.group5.research.myelomalacia import detect_myelopathy_index

    mri, cord_mask, csf_mask = _t2_phantom_with_cord_and_csf()
    level_index = np.arange(mri.shape[2])[None, None, :]
    mri[(cord_mask == 1) & (level_index == 6)] = 170.0  # lesion: cord near CSF

    flags = detect_myelopathy_index(
        mri, cord_mask, csf_mask, level_axis=2, threshold=0.75
    )
    assert [f["level"] for f in flags] == [6]


def test_weber_flags_diffuse_cord_brightening_that_local_misses():
    """A DIFFUSELY bright cord (every level near CSF). The cord-vs-cord method sees
    no per-level deviation and misses it; cord-vs-CSF catches it everywhere.
    """
    from services.measurements.group5.research.myelomalacia import detect_myelopathy_index

    mri, cord_mask, csf_mask = _t2_phantom_with_cord_and_csf()
    mri[cord_mask == 1] = 170.0  # whole cord uniformly bright relative to CSF

    weber = detect_myelopathy_index(mri, cord_mask, csf_mask, level_axis=2, threshold=0.75)
    local = detect_cord_signal_abnormality(mri, cord_mask, level_axis=2, threshold_ratio=1.3)

    assert len(weber) == 12   # caught at every level
    assert local == []        # cord-vs-cord is blind to uniform brightening


def test_weber_csf_reference_robust_to_dark_partial_volume_voxels():
    """Real Duke-case-1 issue: the CSF mask (canal minus cord) includes darker
    partial-volume voxels at the canal edges. A MEDIAN CSF reference gets dragged
    down by them and false-flags a healthy cord. A robust upper-percentile reference
    uses the true bright CSF and does not.
    """
    from services.measurements.group5.research.myelomalacia import detect_myelopathy_index

    mri = np.zeros((20, 20, 12), dtype=float)
    cord_mask = np.zeros_like(mri, dtype=int)
    csf_mask = np.zeros_like(mri, dtype=int)

    cord_mask[9:11, 9:11, :] = 1
    mri[cord_mask == 1] = 80.0       # healthy cord

    csf_mask[2:7, 9:11, :] = 1       # 10 "CSF" voxels per level
    mri[2:5, 9:11, :] = 90.0         # 6/10 dark partial-volume edge voxels
    mri[5:7, 9:11, :] = 200.0        # 4/10 true bright CSF

    flags = detect_myelopathy_index(
        mri, cord_mask, csf_mask, level_axis=2, threshold=0.75
    )
    assert flags == []   # robust CSF reference -> healthy cord NOT flagged


def test_focal_lesion_caught_by_bright_tail_but_missed_by_median():
    """Real Duke finding (case 000009): a focal intramedullary lesion is only a small
    fraction of the cord cross-section, so the per-level MEDIAN barely moves and the
    median detector misses it. Detecting on the bright TAIL (p90) of cord signal
    catches it. This is why median-based detection had 0 sensitivity vs SCIseg.
    """
    from services.measurements.group5.research.myelomalacia import detect_focal_hyperintensity

    mri = np.full((20, 20, 12), 100.0)        # uniform healthy cord baseline
    cord_mask = np.zeros((20, 20, 12), dtype=int)
    cord_mask[8:12, 8:12, :] = 1              # 16 cord voxels per level
    # focal lesion at level 6: ~6/16 voxels bright (200) — a minority of the cord
    mri[8:10, 8:11, 6] = 200.0

    bright = detect_focal_hyperintensity(mri, cord_mask, level_axis=2,
                                         percentile=90, threshold_ratio=1.4)
    median_based = detect_cord_signal_abnormality(mri, cord_mask, level_axis=2,
                                                  threshold_ratio=1.3)

    assert 6 in [f["level"] for f in bright]   # bright-tail catches the lesion
    assert median_based == []                  # median washes it out (the bug)
