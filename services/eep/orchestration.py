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
    core = {k: handoff[k] for k in ("measurements", "flags", "components", "interpretations") if k in handoff}
    return core or None


def _resolve_segmentation(filename: str, input_bytes: bytes | None) -> Path | None:
    """Real segmentation (3 engines in parallel) when wired + we have the upload; else the stand-in.

    Returns a path to the segmentation zip the measurements IEP consumes, or None.
    """
    if input_bytes and seg.all_engines_configured():
        try:
            merged = seg.run_segmentation(input_bytes, filename)
            tmp = Path(tempfile.gettempdir()) / f"segzip-{uuid.uuid4().hex[:8]}.zip"
            tmp.write_bytes(merged)
            return tmp
        except Exception:  # noqa: BLE001 — any engine failure falls back to the stand-in, never crashes
            pass
    return SEG_ZIP if SEG_ZIP.exists() else None


def process_upload(filename: str, uploader: str, input_bytes: bytes | None = None) -> dict:
    client = MeasurementsClient()
    core: dict | None = None
    seg_zip = _resolve_segmentation(filename, input_bytes)
    if client.configured and seg_zip is not None and seg_zip.exists():
        handoff = client.measure(seg_zip, case_id="pending", filename=filename)
        core = _map_core(handoff or {})
    return store.create_case(filename, uploader, core=core)


def measurements_ready() -> bool:
    return MeasurementsClient().health()


def segmentation_ready() -> bool:
    """True when all 3 engines are wired (real segmentation active); False => stand-in mode."""
    return seg.all_engines_configured()


def reporting_ready() -> bool:
    return ReportingClient().health()


def _case_to_handoff(case: dict) -> dict:
    """Project a stored case onto the post-interpretation handoff contract the reporting IEP expects.

    Uploaded cases carry the real measurements handoff; bundled fixtures predate some envelope
    fields, so we fill them with safe defaults rather than fail to render.
    """
    interp = dict(case.get("interpretations") or {})
    interp.setdefault("measurements", [])
    interp.setdefault("syndromes", [])
    return {
        "contract_version": case.get("schema_version") or "reporting-handoff-0.1",
        "case": case.get("case", {}),
        "manifest": case.get("manifest", {}),
        "components": case.get("components", {}),
        "measurements": case.get("measurements", {}),
        "flags": case.get("flags", {}),
        "interpretations": interp,
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
