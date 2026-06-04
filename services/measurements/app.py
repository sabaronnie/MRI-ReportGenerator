"""Flask service exposing the measurements IEP.

Endpoints:
- GET  /healthz   : liveness probe
- GET  /readyz    : readiness probe (verifies all components are importable + registered)
- GET  /metrics   : Prometheus metrics scrape endpoint
- POST /measure   : multipart upload of the segmentation zip from the segmentation IEP

The /measure endpoint accepts the same zip the segmentation IEP returns (containing at
minimum step2_output.nii.gz). Optional repeated form field `measurement=<name>` selects a
subset of registered components; default runs all.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
import zipfile
from ast import literal_eval
from pathlib import Path

from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .context import MeasurementError, load_context
from .orchestrator import COMPONENTS, run_all


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_BYTES", 1024 * 1024 * 1024))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.get("/readyz")
def readyz():
    missing = [n for n, c in COMPONENTS.items() if not hasattr(c, "compute")]
    if missing:
        return jsonify(status="not-ready", missing=missing), 503
    return jsonify(status="ready", components=sorted(COMPONENTS.keys()))


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.post("/measure")
def measure():
    if "file" not in request.files:
        return jsonify(error="multipart field 'file' (segmentation zip) is required"), 400
    upload = request.files["file"]
    enabled = request.form.getlist("measurement") or None

    job_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.gettempdir()) / f"mri-meas-{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    saved = work_dir / (upload.filename or "segmentation.zip")
    upload.save(saved)
    extract_dir = work_dir / "extracted"
    extract_dir.mkdir()
    with zipfile.ZipFile(saved) as zf:
        zf.extractall(extract_dir)

    seg_path = extract_dir / "step2_output.nii.gz"
    if not seg_path.exists():
        candidates = sorted(extract_dir.glob("*.nii.gz"))
        if not candidates:
            return jsonify(error="upload missing step2_output.nii.gz"), 400
        seg_path = candidates[0]

    levels_path = _find_optional_nifti(extract_dir, "step1_levels.nii.gz")
    raw_path = _find_optional_nifti(extract_dir, "input_iso.nii.gz")

    # The segmentation file is already 1 mm isotropic, so the original MRI slice
    # thickness can only come from the segmentation manifest (if the upload
    # included one). Absent it, load_context falls back gracefully.
    source_spacing = None
    meta = _read_segmentation_manifest(extract_dir)
    if meta:
        source_spacing = meta.get("input_metadata", {}).get("voxel_spacing_mm")

    try:
        ctx = load_context(
            seg_path,
            raw_path=raw_path,
            levels_path=levels_path,
            source_spacing_mm=source_spacing,
        )
        report = run_all(ctx, enabled)
    except MeasurementError as e:
        return jsonify(error=str(e)), 500

    return jsonify(report=report, manifest=ctx.manifest)


def _find_optional_nifti(root: Path, filename: str) -> Path | None:
    candidate = next(root.rglob(filename), None)
    return candidate if candidate is not None and candidate.exists() else None


def _read_segmentation_manifest(root: Path) -> dict:
    manifest_file = next(root.rglob("segmentation_run_manifest.json"), None)
    if manifest_file is not None:
        try:
            return json.loads(manifest_file.read_text())
        except (ValueError, OSError):
            pass

    text_file = next(root.rglob("manifest.txt"), None)
    if text_file is None:
        return {}

    parsed: dict[str, object] = {"input_metadata": {}}
    try:
        for line in text_file.read_text().splitlines():
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            raw_value = raw_value.strip()
            if key == "voxel_spacing_mm":
                parsed["input_metadata"]["voxel_spacing_mm"] = list(literal_eval(raw_value))
            elif key == "shape":
                parsed["input_metadata"]["shape"] = list(literal_eval(raw_value))
            elif key == "canonical_axes":
                parsed["input_metadata"]["canonical_axes"] = raw_value
            elif key == "geometry_standardization":
                parsed["input_metadata"]["geometry_standardization"] = literal_eval(raw_value)
            else:
                parsed[key] = raw_value
    except (SyntaxError, ValueError, OSError):
        return {}
    return parsed


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    app.run(host="0.0.0.0", port=port, debug=False)
