"""Flask service exposing SCT segmentation as a separate IEP.

Endpoints:
- GET  /healthz      : liveness probe
- POST /segment-sct  : multipart upload of the TotalSpineSeg zip returned by
                       the segmentation IEP. Returns a zip containing the
                       original segmentation artifacts plus SCT canal/cord masks.
"""

from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from .sct_segmenter import SCTSegmentationError, SCTSegmentationResult, run_sct_segmentations


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GiB upload cap


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.post("/segment-sct")
def segment_sct():
    if "file" not in request.files:
        return jsonify(error="multipart field 'file' (TotalSpineSeg zip) is required"), 400

    upload = request.files["file"]
    job_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.gettempdir()) / f"mri-sct-{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    saved = work_dir / (upload.filename or "segmentation.zip")
    upload.save(saved)
    extract_dir = work_dir / "extracted"
    extract_dir.mkdir()

    try:
        with zipfile.ZipFile(saved) as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        return jsonify(error="upload must be the segmentation zip from the TSS service"), 400

    raw_path = _find_optional_nifti(extract_dir, "input_iso.nii.gz")
    if raw_path is None:
        return jsonify(
            error=(
                "upload missing input_iso.nii.gz; run the TotalSpineSeg service with "
                "iso enabled and pass its zip output here"
            )
        ), 400

    try:
        result = run_sct_segmentations(raw_path, work_dir / "sct_output")
    except SCTSegmentationError as e:
        return jsonify(error="sct-segmentation", detail=str(e)), 500

    zip_path = work_dir / "sct_segmentation.zip"
    _zip_outputs(extract_dir, result, zip_path)
    return send_file(zip_path, as_attachment=True, download_name="sct_segmentation.zip")


def _find_optional_nifti(root: Path, filename: str) -> Path | None:
    candidate = next(root.rglob(filename), None)
    return candidate if candidate is not None and candidate.exists() else None


def _zip_outputs(extract_dir: Path, result: SCTSegmentationResult, zip_path: Path) -> None:
    has_lesion = result.lesion_seg is not None and result.lesion_seg.exists()
    manifest_payload = {
        "sct_canal_seg": "sct_canal_seg.nii.gz",
        "sct_spinalcord_seg": "sct_spinalcord_seg.nii.gz",
        "sct_lesion_seg": "sct_lesion_seg.nii.gz" if has_lesion else None,  # SCIseg, Group 5.1
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(extract_dir.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(extract_dir).as_posix())
        zf.write(result.canal_seg, arcname="sct_canal_seg.nii.gz")
        zf.write(result.cord_seg, arcname="sct_spinalcord_seg.nii.gz")
        if has_lesion:
            zf.write(result.lesion_seg, arcname="sct_lesion_seg.nii.gz")
        zf.writestr("sct_segmentation_manifest.json", json.dumps(manifest_payload, indent=2))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=False)
