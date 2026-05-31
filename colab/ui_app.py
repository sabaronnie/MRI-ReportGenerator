"""Group-2 service UI — input a cervical spine MRI, get the disc measurements in the browser.

A small local web app that runs the whole group-2 pipeline on one scan:
    input (NIfTI file or DICOM folder)  ->  TotalSpineSeg  ->  4 disc measurements  ->  table

Segmentation takes a few minutes (GPU), so each request runs as a background job and the
result page auto-refreshes until it is ready. If the scan was already segmented (e.g. a Duke
case in tss_runs/), the cached segmentation is reused and results appear immediately.

Run it, then open the printed URL in your browser:
    py -3.12 colab/ui_app.py
    py -3.12 colab/ui_app.py --port 5000 --device cuda
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import nibabel as nib
import numpy as np
from flask import Flask, redirect, render_template_string, request, url_for

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "colab"))

from services.segmentation import input_handler as ih  # noqa: E402
from services.segmentation.input_handler import InputError  # noqa: E402
import run_group2_pipeline as pipe  # noqa: E402  (measure_case, find_cached_seg, _level_sort_key)

app = Flask(__name__)
UI_DIR = ROOT / "tss_runs" / "ui_jobs"
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
DEVICE = "cuda"


def _set(job_id: str, **kw):
    with LOCK:
        JOBS[job_id].update(**kw)


def _prepare_input(raw_path: str, fmt: str, work_dir: Path):
    """Resolve the input to a NIfTI path (converting DICOM if needed) and sanity-check it.

    Unlike input_handler.prepare_nifti, the sagittal check here is orientation-ORDER
    independent: it accepts any scan whose L-R axis is the coarsest (slice) direction, so
    real sagittal data like Duke (axcodes ('P','S','R'), L-R on axis 2) is not rejected.
    Reorientation to canonical RAS is handled downstream by load_context.
    """
    p = Path(raw_path)
    if not p.exists():
        raise InputError(f"Path not found: {p}")
    if fmt == "nifti" and not (p.is_file() and ih._is_nifti(p)):
        raise InputError("Format 'NIfTI file' selected, but the path is not a .nii/.nii.gz file.")
    if fmt == "dicom" and not p.is_dir():
        raise InputError("Format 'DICOM folder' selected, but the path is not a folder.")

    if p.is_file() and ih._is_nifti(p):
        nifti = p
    elif p.is_dir():
        nifti = ih._convert_dicom_with_dcm2niix(p, work_dir)   # DICOM -> NIfTI
    else:
        raise InputError(f"Input must be a .nii/.nii.gz file or a DICOM folder; got: {p}")

    img = nib.load(str(nifti))
    if img.ndim != 3:
        raise InputError(f"{nifti.name}: expected a 3D volume, got {img.ndim}D")
    axcodes = nib.aff2axcodes(img.affine)
    zooms = [float(z) for z in img.header.get_zooms()[:3]]
    lr_axis = next((i for i, a in enumerate(axcodes) if a in ("L", "R")), None)
    if lr_axis is None:
        raise InputError(f"{nifti.name}: no left-right axis found; not a spatial MRI volume.")
    if zooms[lr_axis] < 0.6 * max(zooms):
        raise InputError(
            f"{nifti.name}: orientation {axcodes} with spacing {tuple(round(z,2) for z in zooms)} "
            "is not sagittal-dominant (the L-R axis should be the slice direction). Expected sagittal T2."
        )
    can = nib.as_closest_canonical(img)
    spacing = tuple(float(z) for z in can.header.get_zooms()[:3])
    shape = tuple(int(s) for s in can.shape[:3])
    return nifti, spacing, shape


def _run_tss(nifti_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "totalspineseg.inference", str(nifti_path), str(out_dir),
           "--device", DEVICE, "--keep-only", "step2_output"]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"TotalSpineSeg failed (exit {proc.returncode})")
    seg = out_dir / "step2_output" / nifti_path.name
    if seg.is_file():
        return seg
    hits = sorted((out_dir / "step2_output").glob("*.nii.gz"))
    if not hits:
        raise RuntimeError("TotalSpineSeg produced no step2 segmentation")
    return hits[0]


def _process(job_id: str, raw_path: str, fmt: str):
    try:
        _set(job_id, stage="Validating input")
        job_dir = UI_DIR / job_id
        nifti, spacing, shape = _prepare_input(raw_path, fmt, job_dir)
        _set(job_id, input_name=nifti.name,
             spacing="x".join(f"{s:.2f}" for s in spacing),
             shape="x".join(str(s) for s in shape))

        _set(job_id, stage="Checking for a cached segmentation")
        seg = pipe.find_cached_seg(nifti.name)
        if seg is None:
            _set(job_id, stage="Segmenting with TotalSpineSeg (a few minutes)...")
            seg = _run_tss(nifti, job_dir / "tss")
            _set(job_id, seg_source="TotalSpineSeg (new)")
        else:
            _set(job_id, seg_source="cached segmentation")

        _set(job_id, stage="Computing disc measurements")
        rows = pipe.measure_case(seg, nifti)
        rows.sort(key=lambda r: pipe._level_sort_key(r["disc_level"]))
        n_rel = sum(1 for r in rows if r["reliable"])
        _set(job_id, status="done", stage="Done", rows=rows, n_disc=len(rows), n_reliable=n_rel)
    except Exception as e:  # noqa: BLE001 - surface any failure in the UI
        _set(job_id, status="error", stage="Error", error=f"{type(e).__name__}: {e}")


PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>Group-2 spine MRI service</title>
{% if refresh %}<meta http-equiv="refresh" content="3">{% endif %}
<style>
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:1050px;margin:24px auto;padding:0 16px;color:#1c2530}
 h1{font-size:21px} h2{font-size:16px;margin-top:26px}
 .card{background:#f6f8fa;border:1px solid #d7dde3;border-radius:10px;padding:18px 20px;margin:14px 0}
 label{display:block;font-weight:600;margin:12px 0 4px} input[type=text]{width:100%;padding:9px;border:1px solid #c2cad2;border-radius:6px;font-size:14px}
 .radios label{display:inline-block;font-weight:400;margin-right:18px}
 button{margin-top:16px;background:#2563eb;color:#fff;border:0;border-radius:7px;padding:10px 20px;font-size:15px;cursor:pointer}
 table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px} th,td{border:1px solid #d7dde3;padding:6px 9px;text-align:right}
 th{background:#eef2f6} td.l,th.l{text-align:left}
 tr.bad{background:#fff4f4;color:#7a2a2a} .pill{display:inline-block;border-radius:10px;padding:1px 8px;color:#fff;font-size:12px}
 .muted{color:#6b7682;font-size:13px} .stage{font-size:15px} .err{color:#a40000;white-space:pre-wrap}
 .spin{display:inline-block;width:14px;height:14px;border:2px solid #c7d2e0;border-top-color:#2563eb;border-radius:50%;animation:s 0.8s linear infinite;vertical-align:-2px}
 @keyframes s{to{transform:rotate(360deg)}}
 .disc{background:#dbeafe;color:#1e3a8a;padding:2px 6px;border-radius:5px}
</style></head><body>
<h1>Cervical spine MRI — disc measurement service <span class="muted">(group 2)</span></h1>

{% if not job %}
<form method="post" action="{{ url_for('run') }}" class="card">
  <label>Path to the scan on this machine</label>
  <input type="text" name="path" placeholder="C:\\Users\\...\\scan.nii.gz   or   C:\\Users\\...\\dicom_folder" required>
  <div class="radios">
    <label>Format:</label>
    <label><input type="radio" name="fmt" value="auto" checked> Auto-detect</label>
    <label><input type="radio" name="fmt" value="nifti"> NIfTI file (.nii/.nii.gz)</label>
    <label><input type="radio" name="fmt" value="dicom"> DICOM folder</label>
  </div>
  <button type="submit">Run measurements</button>
</form>
<p class="muted">Tip: paste a local file path or DICOM-folder path. Already-segmented scans return
instantly; new scans run TotalSpineSeg first (a few minutes).</p>
{% else %}

  {% if job.status == 'running' %}
    <div class="card"><div class="stage"><span class="spin"></span>
      &nbsp;{{ job.stage }}</div>
      <p class="muted">This page refreshes automatically. Segmentation of a new scan takes a few minutes.</p>
    </div>
  {% elif job.status == 'error' %}
    <div class="card"><div class="stage">Could not process the scan.</div>
      <p class="err">{{ job.error }}</p>
      <a href="{{ url_for('index') }}">&larr; try another scan</a></div>
  {% else %}
    <div class="card">
      <b>{{ job.input_name }}</b> &nbsp;<span class="muted">spacing {{ job.spacing }} mm · {{ job.shape }} ·
      segmentation: {{ job.seg_source }}</span><br>
      <span class="muted">{{ job.n_disc }} disc levels measured · {{ job.n_reliable }} reliable</span>
    </div>
    <h2>Disc measurements</h2>
    <table>
      <tr><th class="l">Level</th><th>H&nbsp;center</th><th>H&nbsp;middle</th><th>AP&nbsp;width</th>
          <th>DHI</th><th>disc/VB</th><th>bulge</th><th>Pfirrmann</th><th class="l">Quality</th></tr>
      {% for r in job.rows %}
      <tr class="{{ '' if r.reliable else 'bad' }}">
        <td class="l"><span class="disc">{{ r.disc_level }}</span></td>
        <td>{{ '%.2f'|format(r.H_center_mm) if r.H_center_mm is not none else '-' }}</td>
        <td>{{ '%.2f'|format(r.H_middle_mm) if r.H_middle_mm is not none else '-' }}</td>
        <td>{{ '%.2f'|format(r.AP_width_mm) if r.AP_width_mm is not none else '-' }}</td>
        <td>{{ '%.3f'|format(r.DHI) if r.DHI is not none else '-' }}</td>
        <td>{{ '%.2f'|format(r.disc_vb_ap_ratio) if r.disc_vb_ap_ratio is not none else '-' }}</td>
        <td>{{ '%.2f'|format(r.posterior_bulge_mm) if r.posterior_bulge_mm is not none else '-' }}</td>
        <td>{% if r.pfirrmann_grade is not none %}
            <span class="pill" style="background:{{ ['#16a34a','#16a34a','#65a30d','#d97706','#dc2626','#991b1b'][r.pfirrmann_grade] }}">
            {{ r.pfirrmann_label }}</span>{% else %}-{% endif %}</td>
        <td class="l muted">{{ 'reliable' if r.reliable else (r.flags or 'flagged') }}</td>
      </tr>
      {% endfor %}
    </table>
    <p class="muted">Columns in mm unless unitless (DHI, disc/VB ratio). Flagged rows
    (e.g. C2-C3 dens, FOV edge, implausible value) are excluded from the reliable set.</p>
    <a href="{{ url_for('index') }}">&larr; measure another scan</a>
  {% endif %}
{% endif %}

<hr style="margin-top:30px;border:0;border-top:1px solid #e2e6ea">
<p class="muted"><b>Research / educational use only — not a diagnostic device.</b> Outputs are
automated measurements flagged for physician review; clinical correlation required.</p>
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, job=None, refresh=False)


@app.route("/run", methods=["POST"])
def run():
    raw_path = request.form.get("path", "").strip().strip('"').strip("'")
    fmt = request.form.get("fmt", "auto")
    if not raw_path:
        return redirect(url_for("index"))
    job_id = uuid.uuid4().hex[:12]
    with LOCK:
        JOBS[job_id] = {"status": "running", "stage": "Queued"}
    threading.Thread(target=_process, args=(job_id, raw_path, fmt), daemon=True).start()
    return redirect(url_for("job", job_id=job_id))


@app.route("/job/<job_id>")
def job(job_id: str):
    with LOCK:
        j = dict(JOBS.get(job_id, {}))
    if not j:
        return redirect(url_for("index"))
    return render_template_string(PAGE, job=j, refresh=(j.get("status") == "running"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    args = p.parse_args(argv)
    global DEVICE
    DEVICE = args.device
    UI_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nGroup-2 spine MRI service running at  http://{args.host}:{args.port}\n"
          f"(segmentation device: {DEVICE})  — press Ctrl+C to stop\n")
    app.run(host=args.host, port=args.port, threaded=True, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
