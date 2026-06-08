"""HTTP client for the measurements IEP (POST /measure)."""

from __future__ import annotations

from pathlib import Path

import httpx

from .. import config
from ._http import send_with_retries


class MeasurementsClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = (base_url if base_url is not None else config.MEASUREMENTS_URL).rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def health(self) -> bool:
        if not self.configured:
            return False
        try:
            return httpx.get(f"{self.base_url}/healthz", timeout=3.0).status_code == 200
        except httpx.HTTPError:
            return False

    def measure(self, seg_zip: Path, *, case_id: str, filename: str) -> dict | None:
        """POST a segmentation zip to the measurements IEP; return the handoff JSON or None on failure."""
        if not self.configured or not seg_zip.exists():
            return None

        def _send() -> httpx.Response:
            # Re-open the file each attempt — the body is consumed on every send.
            with seg_zip.open("rb") as fh:
                return httpx.post(
                    f"{self.base_url}/measure",
                    files={"file": (seg_zip.name, fh, "application/zip")},
                    data={"case_id": case_id, "job_id": case_id, "source_file": filename},
                    timeout=self.timeout,
                )

        try:
            resp = send_with_retries(_send, retries=config.IEP_RETRIES, backoff_s=config.IEP_BACKOFF_S)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None
