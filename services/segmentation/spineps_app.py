"""Flask service exposing SPINEPS segmentation as a separate IEP (Group 4 endplate-voxel Cobb).

SPINEPS pins ``numpy==2.0.2`` (incompatible with TotalSpineSeg/nnU-Net) -> deploy as its OWN image.
Runs independently on the raw sagittal T2 (in parallel with the TSS service).

Endpoints:
- GET  /healthz : liveness probe
- POST /segment : multipart upload (NIfTI sagittal T2, or zipped DICOM folder); returns a zip of
                  the SPINEPS instance mask (seg-vert, with endplate voxels 102-107) + manifest.
"""

from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from .input_handler import InputError, prepare_nifti
from .spineps_segmenter import SpinepsSegmentationError, SpinepsSegmentationResult, run_spineps


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GiB upload cap


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.post("/segment")
def segment():
    if "file" not in request.files:
        return jsonify(error="multipart field 'file' (sagittal T2 NIfTI) is required"), 400

    upload = request.files["file"]
    job_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.gettempdir()) / f"mri-spineps-{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    saved = work_dir / (upload.filename or "input.nii.gz")
    upload.save(saved)

    try:
        metadata = prepare_nifti(saved, work_dir)
        result = run_spineps(metadata.nifti_path, work_dir)
    except InputError as e:
        return jsonify(error="input", detail=str(e)), 400
    except SpinepsSegmentationError as e:
        return jsonify(error="spineps-segmentation", detail=str(e)), 500

    zip_path = work_dir / "spineps_segmentation.zip"
    _zip_outputs(result, zip_path)
    return send_file(zip_path, as_attachment=True, download_name="spineps_segmentation.zip")


def _zip_outputs(result: SpinepsSegmentationResult, zip_path: Path) -> None:
    manifest = {
        "spineps_seg_vert": "spineps_seg-vert_msk.nii.gz",
        "spineps_seg_spine": "spineps_seg-spine_msk.nii.gz" if result.seg_spine is not None else None,
        "endplate_labels_present": result.endplate_labels_present,
        "consumed_by": (
            "services.measurements.geometric.c3c7_cobb_angle via spineps_endplate_cobb_angle "
            "(C3 instance=3 .. C7 instance=7); pass as load_context(spineps_seg_path=...)"
        ),
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(result.seg_vert, arcname="spineps_seg-vert_msk.nii.gz")
        if result.seg_spine is not None:
            zf.write(result.seg_spine, arcname="spineps_seg-spine_msk.nii.gz")
        zf.writestr("spineps_segmentation_manifest.json", json.dumps(manifest, indent=2))


if __name__ == "__main__":
    # Ports: TSS 8080, SPINEPS 8081, SCT 8082.
    app.run(host="0.0.0.0", port=8081, debug=False)
