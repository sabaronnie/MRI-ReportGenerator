"""Selectively download ONLY what 5.2 validation needs from RSNA-2022 (NOT the ~350 GB images).

Pulls: train.csv + train_bounding_boxes.csv (tiny labels) and N vertebral SEGMENTATION masks
(segmentations/*.nii). The full seg set is 87 files / ~13.7 GB; use --n-segs to cap it.

  python download_rsna.py --n-segs 3      # proof: labels + 3 smallest masks (~150 MB)
  python download_rsna.py --n-segs 87     # everything (~13.7 GB)
Resumable: skips files already on disk.
"""
import argparse
import glob
import json
import os
import zipfile

from kaggle.api.kaggle_api_extended import KaggleApi

COMP = "rsna-2022-cervical-spine-fracture-detection"
OUT = "data/rsna"


def all_seg_files(api):
    rows, token, pages = [], None, 0
    while True:
        try:
            res = api.competition_list_files(COMP, page_token=token, page_size=200) if token \
                  else api.competition_list_files(COMP, page_size=200)
        except TypeError:
            res = api.competition_list_files(COMP)
        files = list(getattr(res, "files", res) or [])
        for f in files:
            try:
                rows.append(json.loads(str(f)))
            except Exception:
                pass
        pages += 1
        token = getattr(res, "nextPageToken", None) or getattr(res, "next_page_token", None)
        if not token or not files or pages > 30:
            break
    return [r for r in rows if r.get("ref", "").startswith("segmentations/")]


def fetch(api, ref, dest_dir):
    """Download one competition file into dest_dir; unzip if Kaggle wrapped it in .zip."""
    base = os.path.basename(ref)
    final = os.path.join(dest_dir, base)
    if os.path.exists(final):
        return "skip"
    api.competition_download_file(COMP, ref, path=dest_dir, quiet=True, force=False)
    z = final + ".zip"
    if os.path.exists(z):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(dest_dir)
        os.remove(z)
    return "ok" if os.path.exists(final) else "missing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-segs", type=int, default=3, help="how many segmentation masks (smallest-first)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "segmentations"), exist_ok=True)

    api = KaggleApi(); api.authenticate()
    print("auth OK as", api.config_values.get("username"))

    for csv in ("train.csv", "train_bounding_boxes.csv"):
        print(f"labels: {csv} -> {fetch(api, csv, a.out)}")

    segs = sorted(all_seg_files(api), key=lambda r: r.get("totalBytes", 0))
    pick = segs[: a.n_segs]
    gb = sum(r.get("totalBytes", 0) for r in pick) / 1e9
    print(f"\n{len(segs)} segmentations available; downloading {len(pick)} (~{gb:.1f} GB):")
    for i, r in enumerate(pick, 1):
        try:
            status = fetch(api, r["ref"], os.path.join(a.out, "segmentations"))
        except Exception as e:                      # one bad file must not abort the batch
            status = f"ERROR {type(e).__name__}: {str(e)[:80]}"
        print(f"  [{i}/{len(pick)}] {os.path.basename(r['ref'])}  {r['totalBytes']/1e6:.0f}MB -> {status}", flush=True)

    have = glob.glob(os.path.join(a.out, "segmentations", "*.nii"))
    print(f"\nsegmentations on disk: {len(have)}")


if __name__ == "__main__":
    main()
