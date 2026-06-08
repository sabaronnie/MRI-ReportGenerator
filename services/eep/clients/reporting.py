"""HTTP client for the reporting IEP (POST /render).

The EEP orchestrates measurements -> reporting: it hands the post-interpretation contract to
this service and gets back the rendered report document + HTML artifacts.
"""

from __future__ import annotations

import httpx

from .. import config
from ._http import send_with_retries


class ReportingClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url if base_url is not None else config.REPORTING_URL).rstrip("/")
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

    def render(self, handoff: dict) -> dict | None:
        """POST the handoff contract; return {report, artifacts} or None on failure."""
        if not self.configured:
            return None

        def _send() -> httpx.Response:
            return httpx.post(f"{self.base_url}/render", json=handoff, timeout=self.timeout)

        try:
            resp = send_with_retries(_send, retries=config.IEP_RETRIES, backoff_s=config.IEP_BACKOFF_S)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None
