"""Group 5 end-to-end runner: a TSS step2 segmentation (+ optional SCIseg lesion mask) -> flags JSON.

Glues the validated Group 5 pieces into the single artifact Group 6 consumes:
  - 5.2 vertebral-body compression screen  (vertebral_fracture: canal-cut + endplate morphometry)
  - 5.1 myelomalacia screen                (SCIseg lesion mask -> burden, mapped to cervical level)
  - the 5->6 contract                      (flags_contract.build_flags_contract)

The lesion mask is OPTIONAL: without it, myelomalacia reads "not assessed"; with it, every cervical
level is assessed and flagged present where the cord lesion overlaps that level's superior-inferior
span. SCIseg masks live on the raw-T2 grid, so the file wrapper resamples them onto the seg grid.

Usage:  python run_group5_pipeline.py <step2.nii.gz> [--lesion <lesion_seg.nii.gz>]
                                      [--case-id ID] [-o out.json]
"""
import argparse
import json
import os
import sys

import nibabel as nib
import numpy as np

from flags_contract import build_flags_contract
from vertebral_fracture import (
    extract_body_via_canal,
    measure_vertebra,
    vertebra_axes_from_orientation,
)

CERVICAL = {13: "C3", 14: "C4", 15: "C5", 16: "C6", 17: "C7"}   # C1/C2 excluded (structurally unique)
CANAL_LABEL = 2


def _case_key(path):
    """Shared subject key for pairing a TSS step2 mask with its SCIseg lesion mask.
    sub-amu01_T2w_step2.nii.gz -> sub-amu01_T2w ; sub-amu01_T2w_lesion_seg.nii.gz -> sub-amu01_T2w."""
    b = os.path.basename(path)
    for suf in ("_step2.nii.gz", "_lesion_seg.nii.gz", ".nii.gz"):
        if b.endswith(suf):
            return b[: -len(suf)]
    return b


def pair_cases(step2_paths, lesion_paths=None):
    """Pair each step2 mask with its lesion mask by subject key; lesion=None when absent.
    Returns a list of (case_key, step2_path, lesion_path_or_None)."""
    lesion_by_key = {_case_key(p): p for p in (lesion_paths or [])}
    return [(_case_key(s), s, lesion_by_key.get(_case_key(s))) for s in step2_paths]


def _si_span(mask, si_axis):
    """(min, max) index along the SI axis where `mask` is present, or None if empty."""
    s = np.where(mask)[si_axis]
    return (int(s.min()), int(s.max())) if s.size else None


def assemble_case_contract(seg, axcodes, zooms, lesion=None, case_id="case", screen_z=2.0):
    """Build the Group 5 flags contract from a (same-grid) seg array + optional lesion array.

    seg     : int label volume (TSS step2 canonical labels).
    lesion  : optional boolean cord-lesion mask ON THE SAME GRID as seg (None -> 5.1 not assessed).
    Returns the JSON-serialisable contract dict (see flags_contract.build_flags_contract).
    """
    seg = np.asarray(seg)
    ap, si, lr, anterior = vertebra_axes_from_orientation(axcodes)
    canal = seg == CANAL_LABEL

    fracture_levels, spans = [], {}
    for lbl in sorted(c for c in CERVICAL if np.any(seg == c)):
        vert = seg == lbl
        body = extract_body_via_canal(vert, canal, axcodes) if canal.any() else vert
        h = measure_vertebra(body, axcodes, zooms, isolate_body=not canal.any())
        if h["Hp"] > 0:                                  # drop bodies we couldn't measure
            name = CERVICAL[lbl]
            fracture_levels.append((name, h))
            spans[name] = _si_span(vert, si)

    myelomalacia = None
    if lesion is not None:                               # SCIseg ran -> every level is assessed
        les_si = np.where(np.asarray(lesion, dtype=bool))[si]
        myelomalacia = {
            name: bool(span and les_si.size and np.any((les_si >= span[0]) & (les_si <= span[1])))
            for name, span in spans.items()
        }

    return build_flags_contract(case_id, fracture_levels, myelomalacia=myelomalacia, screen_z=screen_z)


def run_group5_case(step2_path, lesion_path=None, case_id=None, screen_z=2.0):
    """Load a TSS step2 (+ optional SCIseg lesion) from disk and emit the flags contract."""
    seg_img = nib.load(step2_path)
    seg = np.rint(np.asarray(seg_img.dataobj)).astype(int)
    axcodes = nib.aff2axcodes(seg_img.affine)
    zooms = seg_img.header.get_zooms()[:3]

    lesion = None
    if lesion_path:
        les_img = nib.load(lesion_path)
        if les_img.shape != seg_img.shape or nib.aff2axcodes(les_img.affine) != axcodes:
            import nibabel.processing as nibproc          # SCIseg mask is on the raw-T2 grid
            les_img = nibproc.resample_from_to(les_img, seg_img, order=0)
        lesion = np.asarray(les_img.dataobj) > 0.5

    cid = case_id or step2_path.split("/")[-1].replace(".nii.gz", "")
    return assemble_case_contract(seg, axcodes, zooms, lesion=lesion, case_id=cid, screen_z=screen_z)


def main(argv=None):
    p = argparse.ArgumentParser(description="Group 5 end-to-end runner -> flags JSON")
    p.add_argument("step2", help="TotalSpineSeg step2_output .nii.gz")
    p.add_argument("--lesion", help="SCIseg lesion mask .nii.gz (optional; enables 5.1)")
    p.add_argument("--case-id", help="case identifier (default: from the step2 filename)")
    p.add_argument("-o", "--out", help="write JSON here (default: stdout)")
    args = p.parse_args(argv)

    c = run_group5_case(args.step2, args.lesion, args.case_id)
    txt = json.dumps(c, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(txt)
        print(f"wrote {args.out}")
    else:
        print(txt)

    n_flag = sum(1 for lv in c["levels"] if lv["fracture"]["flagged"])
    myo = [lv for lv in c["levels"] if lv["myelomalacia"]["assessed"]]
    n_myo = sum(1 for lv in myo if lv["myelomalacia"]["present"])
    print(f"# {c['case_id']}: {len(c['levels'])} levels | {n_flag} compression-flagged | "
          f"myelomalacia {'not assessed' if not myo else f'{n_myo} positive'}", file=sys.stderr)


if __name__ == "__main__":
    main()
