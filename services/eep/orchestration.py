"""Upload -> (segmentation: upstream/Colab) -> measurements IEP -> assembled case.

When a real measurements IEP + a stand-in segmentation zip are available, the case's core is
computed for real (genuine EEP -> IEP orchestration). Otherwise a cloned-fixture core is used so
the EEP runs self-contained. The segmentation step (TotalSpineSeg, GPU/Colab) is represented by a
bundled stand-in mask zip — it is not run in-process.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import BackgroundTasks

from . import config, store
from .clients import segmentation as seg
from .clients.measurements import MeasurementsClient
from .clients.reporting import ReportingClient

# A stand-in segmentation zip (contains step2_output.nii.gz) mounted at runtime; absent => fixture mode.
SEG_ZIP = config.SAMPLE_DATA_DIR / "segmentation.zip"

_DEFAULT_DISCLAIMERS = [
    "All outputs are screens flagged for physician review, never a diagnosis.",
    "Values are real pipeline output but pre-validation; clinical correlation required.",
]


def _map_core(handoff: dict) -> dict | None:
    """Project the measurements handoff JSON onto the frozen-core keys the frontend renders."""
    if not handoff:
        return None
    core = {k: handoff[k] for k in ("measurements", "flags", "components", "assessements") if k in handoff}
    return core or None


def _standin_seg_zip() -> Path | None:
    """The bundled stand-in mask zip the measurements IEP consumes, or None if absent."""
    return SEG_ZIP if SEG_ZIP.exists() else None


def enqueue_upload(
    filename: str, uploader: str, input_bytes: bytes | None, background: BackgroundTasks
) -> dict:
    """Route entry point. Returns immediately with a queued case.

    Real segmentation (all 3 engines wired + we have the upload bytes) takes MINUTES, so it must NOT
    run inside the upload request: create a queued case and run seg -> measurements in a BACKGROUND
    task. Otherwise the stand-in fast path runs synchronously (~1-2 s — current demo, unchanged).
    """
    if input_bytes and seg.all_engines_configured():
        created = store.create_case(filename, uploader, simulated=False)
        background.add_task(run_pipeline, created["case_id"], filename, input_bytes)
        return created
    return process_upload(filename, uploader, input_bytes)


def process_upload(filename: str, uploader: str, input_bytes: bytes | None = None) -> dict:
    """Synchronous stand-in path: measure the bundled mask zip (fast) and create a simulated case."""
    client = MeasurementsClient()
    core: dict | None = None
    seg_zip = _standin_seg_zip()
    if client.configured and seg_zip is not None and seg_zip.exists():
        handoff = client.measure(seg_zip, case_id="pending", filename=filename)
        core = _map_core(handoff or {})
    return store.create_case(filename, uploader, core=core)


def run_pipeline(case_id: str, filename: str, input_bytes: bytes) -> None:
    """Background worker: real 3-engine segmentation -> measurements -> ready (or error).

    Runs in a threadpool thread (FastAPI BackgroundTasks for a sync callable) — i.e. OFF the request
    event loop. That makes the sync `seg.run_segmentation` wrapper's `asyncio.run(...)` safe (no loop
    is already running in this thread) and keeps the blocking measurements call from stalling the
    request loop. Failures are recorded on the case (status "error"), never silently masked.
    """
    tmp: Path | None = None
    try:
        store.set_stage(case_id, "segmenting", progress=0.1)
        merged = seg.run_segmentation(input_bytes, filename)  # parallel fan-out over the 3 engines
        tmp = Path(tempfile.gettempdir()) / f"segzip-{uuid.uuid4().hex[:8]}.zip"
        tmp.write_bytes(merged)

        store.set_stage(case_id, "measuring", progress=0.6)
        client = MeasurementsClient()
        core: dict | None = None
        if client.configured:
            handoff = client.measure(tmp, case_id=case_id, filename=filename)
            core = _map_core(handoff or {})
        if core:
            store.update_case_core(case_id, core)
        store.set_stage(case_id, "ready", progress=1.0)
    except Exception as exc:  # noqa: BLE001 — surface on the case; a worker crash must not be silent
        store.set_stage(case_id, "error", error=f"segmentation/measurement failed: {exc}")
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def measurements_ready() -> bool:
    return MeasurementsClient().health()


def segmentation_ready() -> bool:
    """True when all 3 engines are wired (real segmentation active); False => stand-in mode."""
    return seg.all_engines_configured()


def reporting_ready() -> bool:
    return ReportingClient().health()


def _case_to_handoff(case: dict) -> dict:
    """Project a stored case onto the post-assessement handoff contract the reporting IEP expects.

    Uploaded cases carry the real measurements handoff; bundled fixtures predate some envelope
    fields, so we fill them with safe defaults rather than fail to render.
    """
    interp = dict(case.get("assessements") or {})
    interp.setdefault("measurements", [])
    interp.setdefault("syndromes", [])
    return {
        "contract_version": case.get("schema_version") or "reporting-handoff-0.1",
        "case": case.get("case", {}),
        "manifest": case.get("manifest", {}),
        "components": case.get("components", {}),
        "measurements": case.get("measurements", {}),
        "flags": case.get("flags", {}),
        "assessements": interp,
        "report_context": case.get("report_context")
        or {
            "modality": "cervical_sagittal_mri",
            "report_language": "en",
            "disclaimers": _DEFAULT_DISCLAIMERS,
            "include_appendix": True,
        },
    }


def render_case_report(case: dict) -> str | None:
    """Orchestrate the reporting IEP: hand it the case's contract, return clinical HTML (or None)."""
    rendered = ReportingClient().render(_case_to_handoff(case))
    if not rendered:
        return None
    return (rendered.get("artifacts") or {}).get("clinical_html")
