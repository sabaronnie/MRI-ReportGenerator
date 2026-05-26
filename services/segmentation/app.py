"""Flask service exposing the segmentation IEP.

Endpoints:
- GET  /healthz : liveness probe
- POST /segment : multipart upload (NIfTI or zipped DICOM folder); returns a zip
                  of step2_output, step1_levels, optional input_iso, and a manifest.
"""

from __future__ import annotations

import tempfile
import uuid
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from .input_handler import InputError, prepare_nifti
from .segmenter import SegmentationError, SegmentationResult, run_totalspineseg


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GiB upload cap


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.post("/segment")
def segment():
    if "file" not in request.files:
        return jsonify(error="multipart field 'file' is required"), 400

    upload = request.files["file"]
    iso = request.form.get("iso", "true").lower() != "false"

    job_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.gettempdir()) / f"mri-seg-{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        input_path = _materialise_upload(upload, work_dir)
        metadata = prepare_nifti(input_path, work_dir)
        result = run_totalspineseg(metadata.nifti_path, work_dir, iso=iso)
    except InputError as e:
        return jsonify(error="input", detail=str(e)), 400
    except SegmentationError as e:
        return jsonify(error="segmentation", detail=str(e)), 500

    zip_path = work_dir / "segmentation.zip"
    _zip_outputs(result, metadata, zip_path)
    return send_file(zip_path, as_attachment=True, download_name="segmentation.zip")


def _materialise_upload(upload, work_dir: Path) -> Path:
    raw = work_dir / "upload"
    raw.mkdir(parents=True, exist_ok=True)
    fname = upload.filename or "input"
    saved = raw / fname
    upload.save(saved)
    if fname.lower().endswith(".zip"):
        extract_dir = raw / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(saved) as zf:
            zf.extractall(extract_dir)
        children = [p for p in extract_dir.iterdir() if p.is_dir()]
        return children[0] if len(children) == 1 else extract_dir
    return saved


def _zip_outputs(result: SegmentationResult, metadata, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(result.step2_output, arcname="step2_output.nii.gz")
        zf.write(result.step1_levels, arcname="step1_levels.nii.gz")
        if result.iso_input is not None and result.iso_input.exists():
            zf.write(result.iso_input, arcname="input_iso.nii.gz")
        manifest = (
            f"input_nifti={metadata.nifti_path.name}\n"
            f"voxel_spacing_mm={metadata.voxel_spacing_mm}\n"
            f"shape={metadata.shape}\n"
            f"canonical_axes={metadata.canonical_axes}\n"
            f"geometry_standardization={metadata.geometry_standardization}\n"
            f"cervical_labels_present={result.cervical_labels_present}\n"
        )
        zf.writestr("manifest.txt", manifest)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
