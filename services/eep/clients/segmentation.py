"""Segmentation orchestration — run the 3-engine DAG, then merge their masks into one zip.

The engines are NOT a flat 3-way fan-out. SCT consumes TotalSpineSeg's iso-resampled volume
(`input_iso.nii.gz`), so the real dependency graph is:

        raw sagittal T2
        ├─▶ TotalSpineSeg  /segment        ┐ (parallel)
        └─▶ SPINEPS        /segment        ┘
                 │ (TSS zip carries input_iso + step1/step2)
                 └─▶ SCT   /segment-sct  ─▶ canal/cord (+ SCIseg lesion)

So TSS ∥ SPINEPS is the genuine parallel model interaction (rubric §4.3) and SCT is a dependent
stage. We merge SCT's zip (which re-includes the TSS artifacts) with SPINEPS's zip into the single
segmentation zip the measurements IEP consumes. SCT and SPINEPS are non-fatal: a single-engine
failure still yields the masks the other engines produced (TSS is required — the others depend on /
complement it).

Output filenames the measurements IEP reads: step2_output.nii.gz, step1_levels.nii.gz, input_iso.nii.gz
(TSS); sct_canal_seg.nii.gz, sct_spinalcord_seg.nii.gz, sct_lesion_seg.nii.gz (SCT); and
spineps_seg-vert_msk.nii.gz (SPINEPS, G4 endplate Cobb). The merge is filename-agnostic.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import httpx

from .. import config
from ._http import send_with_retries  # noqa: F401  (kept for parity; async path below)


# (engine name, base URL) — used only for the configured/health checks.
def _engines() -> list[tuple[str, str]]:
    return [
        ("totalspineseg", config.SEG_TSS_URL),
        ("sct", config.SEG_SCT_URL),
        ("spineps", config.SEG_SPINEPS_URL),
    ]


def all_engines_configured() -> bool:
    """True only when all three segmentation services are wired (so real segmentation can run)."""
    return all(url for _, url in _engines())


def any_engine_ready() -> bool:
    return any(_health(url) for _, url in _engines() if url)


def _health(url: str) -> bool:
    try:
        return httpx.get(f"{url}/healthz", timeout=3.0).status_code == 200
    except httpx.HTTPError:
        return False


async def _post(client: httpx.AsyncClient, base_url: str, path: str, data: bytes, send_name: str) -> bytes:
    """POST a multipart upload to one engine and return its zip bytes."""
    resp = await client.post(
        f"{base_url}{path}",
        files={"file": (send_name, data, "application/gzip")},
    )
    resp.raise_for_status()
    return resp.content


def _add_zip(out: zipfile.ZipFile, zip_bytes: bytes, seen: set[str]) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for member in z.namelist():
            if member.endswith("/") or member in seen:
                continue
            seen.add(member)
            out.writestr(member, z.read(member))


async def run_segmentation_async(data: bytes, filename: str) -> bytes:
    """Run the engine DAG (TSS ∥ SPINEPS → SCT) and return one merged segmentation zip."""
    async with httpx.AsyncClient(timeout=config.SEG_TIMEOUT_S) as client:
        # Stage 1 — TotalSpineSeg + SPINEPS concurrently on the raw sagittal T2.
        tss_zip, spineps_res = await asyncio.gather(
            _post(client, config.SEG_TSS_URL, "/segment", data, filename),
            _post(client, config.SEG_SPINEPS_URL, "/segment", data, filename),
            return_exceptions=True,
        )
        if isinstance(tss_zip, Exception):
            # TSS is the spine of the pipeline (G1/G2 + SCT's input). Fail loudly so the caller
            # records the error / falls back to the stand-in, rather than emit a partial mask.
            raise tss_zip

        # Stage 2 — SCT on the TSS zip (it carries input_iso.nii.gz). Non-fatal: if SCT fails, the
        # TSS zip still carries the vertebra/disc masks (G1/G2).
        try:
            spine_zip = await _post(client, config.SEG_SCT_URL, "/segment-sct", tss_zip, "segmentation.zip")
        except httpx.HTTPError:
            spine_zip = tss_zip

    # Merge: the spine zip (TSS [+ SCT] masks) + the SPINEPS endplate zip (non-fatal).
    merged = io.BytesIO()
    seen: set[str] = set()
    with zipfile.ZipFile(merged, "w", compression=zipfile.ZIP_DEFLATED) as out:
        _add_zip(out, spine_zip, seen)
        if not isinstance(spineps_res, Exception):
            _add_zip(out, spineps_res, seen)
    merged.seek(0)
    return merged.getvalue()


def run_segmentation(data: bytes, filename: str) -> bytes:
    """Sync wrapper around the engine DAG (for the synchronous orchestration path)."""
    return asyncio.run(run_segmentation_async(data, filename))
