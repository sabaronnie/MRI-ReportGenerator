"""Unit tests for the IEP retry-with-backoff helper (rubric S3 — retries)."""

from __future__ import annotations

import httpx
import pytest

from services.eep.clients._http import send_with_retries


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _noop_sleep(_seconds: float) -> None:  # don't actually sleep in tests
    pass


def test_succeeds_first_try():
    calls = []
    resp = send_with_retries(lambda: (calls.append(1), _Resp(200))[1], retries=2, backoff_s=0, sleep=_noop_sleep)
    assert resp.status_code == 200
    assert len(calls) == 1


def test_retries_then_succeeds_on_transport_error():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("boom")
        return _Resp(200)

    resp = send_with_retries(flaky, retries=2, backoff_s=0, sleep=_noop_sleep)
    assert resp.status_code == 200
    assert attempts["n"] == 3  # 1 initial + 2 retries


def test_retries_on_5xx_then_returns_last():
    attempts = {"n": 0}

    def server_error():
        attempts["n"] += 1
        return _Resp(503)

    resp = send_with_retries(server_error, retries=2, backoff_s=0, sleep=_noop_sleep)
    assert resp.status_code == 503
    assert attempts["n"] == 3  # exhausted retries, returns last response


def test_does_not_retry_4xx():
    attempts = {"n": 0}

    def client_error():
        attempts["n"] += 1
        return _Resp(404)

    resp = send_with_retries(client_error, retries=2, backoff_s=0, sleep=_noop_sleep)
    assert resp.status_code == 404
    assert attempts["n"] == 1  # 4xx is not transient — no retry


def test_raises_after_exhausting_transport_errors():
    def always_fail():
        raise httpx.ConnectError("down")

    with pytest.raises(httpx.HTTPError):
        send_with_retries(always_fail, retries=1, backoff_s=0, sleep=_noop_sleep)
