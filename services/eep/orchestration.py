"""Upload -> (segmentation: upstream/Colab) -> measurements IEP -> assembled case.

When a real measurements IEP + a stand-in segmentation zip are available, the case's core is
computed for real (genuine EEP -> IEP orchestration). Otherwise a cloned-fixture core is used so
the EEP runs self-contained. The segmentation step (TotalSpineSeg, GPU/Colab) is represented by a
bundled stand-in mask zip — it is not run in-process.
"""

from __future__ import annotations

from . import config, store
from .clients.measurements import MeasurementsClient

# A stand-in segmentation zip (contains step2_output.nii.gz) mounted at runtime; absent => fixture mode.
SEG_ZIP = config.SAMPLE_DATA_DIR / "segmentation.zip"


def _map_core(handoff: dict) -> dict | None:
    """Project the measurements handoff JSON onto the frozen-core keys the frontend renders."""
    if not handoff:
        return None
    core = {k: handoff[k] for k in ("measurements", "flags", "components", "interpretations") if k in handoff}
    return core or None


def process_upload(filename: str, uploader: str) -> dict:
    client = MeasurementsClient()
    core: dict | None = None
    if client.configured and SEG_ZIP.exists():
        handoff = client.measure(SEG_ZIP, case_id="pending", filename=filename)
        core = _map_core(handoff or {})
    return store.create_case(filename, uploader, core=core)


def measurements_ready() -> bool:
    return MeasurementsClient().health()
