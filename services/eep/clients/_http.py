"""Bounded retry-with-backoff for the IEP HTTP clients.

Transient failures (connection errors, read timeouts, 5xx) are retried a few times with linear
backoff; a persistent failure is raised so the caller can fall back. `send_fn` is a no-arg callable
that performs one request and returns an httpx.Response — it is re-invoked per attempt, so callers
that stream a file must re-open it inside `send_fn` (the body is consumed on each try).
"""

from __future__ import annotations

import time
from typing import Callable

import httpx


def send_with_retries(
    send_fn: Callable[[], httpx.Response],
    *,
    retries: int,
    backoff_s: float,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = send_fn()
        except httpx.HTTPError as exc:  # connect error / timeout / protocol error
            last_exc = exc
            if attempt < retries:
                sleep(backoff_s * (attempt + 1))
                continue
            raise
        # Retry transient server errors; return everything else (incl. 4xx) to the caller.
        if resp.status_code >= 500 and attempt < retries:
            sleep(backoff_s * (attempt + 1))
            continue
        return resp
    assert last_exc is not None  # unreachable: loop either returns or raises
    raise last_exc
