"""Segmentation orchestration — fan out to the 3 engines IN PARALLEL, then combine their masks.

The 3 engines (TotalSpineSeg, SCT, SPINEPS) are independent services that each take the raw sagittal
T2 NIfTI and return a zip of their output masks. The EEP calls all three **concurrently**
(asyncio.gather over httpx.AsyncClient) — this is the "parallel model interaction" the rubric asks of
the EEP (§4.3) — waits for all, and merges their zips into the single segmentation zip the
measurements IEP already consumes.

NOTE: the exact output filenames each engine emits are owned by the science chat (see the seg-services
handoff). measurements reads: step2_output.nii.gz, step1_levels.nii.gz (TSS); sct_canal_seg.nii.gz,
sct_spinalcord_seg.nii.gz (SCT); + the SPINEPS instance/endplate output (G4 Cobb). The merge below is
filename-agnostic: it copies whatever each engine returns, so it stays correct once those are confirmed.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import httpx

from .. import config
from ._http import send_with_retries  # noqa: F401  (kept for parity; async path below)

# (engine name, base URL) — order is cosmetic; all run concurrently.
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


async def _segment_one(name: str, url: str, data: bytes, filename: str) -> tuple[str, bytes]:
    async with httpx.AsyncClient(timeout=config.SEG_TIMEOUT_S) as client:
        resp = await client.post(
            f"{url}/segment",
            files={"file": (filename, data, "application/gzip")},
        )
        resp.raise_for_status()
        return name, resp.content  # each engine returns a zip of its masks


async def run_segmentation_async(data: bytes, filename: str) -> bytes:
    """Fan out to all configured engines in parallel; return one merged segmentation zip."""
    tasks = [_segment_one(name, url, data, filename) for name, url in _engines() if url]
    results = await asyncio.gather(*tasks)  # <-- the parallel model interaction

    merged = io.BytesIO()
    with zipfile.ZipFile(merged, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for _name, zip_bytes in results:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                for member in z.namelist():
                    if member.endswith("/"):
                        continue
                    out.writestr(member, z.read(member))
    merged.seek(0)
    return merged.getvalue()


def run_segmentation(data: bytes, filename: str) -> bytes:
    """Sync wrapper around the parallel fan-out (for the synchronous orchestration path)."""
    return asyncio.run(run_segmentation_async(data, filename))
