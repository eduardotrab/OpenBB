"""Unit tests for the CVM download helper (HTTP faked)."""

import asyncio

import openbb_core.provider.utils.helpers as core_helpers

from openbb_cvm.utils.helpers import download


class FakeResponse:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    async def read(self):
        return self._body


def _fake_request(calls, status, body=b""):
    async def fake(url, timeout, response_callback, **kwargs):
        calls.append(url)
        return await response_callback(FakeResponse(status, body), None)

    return fake


def test_download_caches_on_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_CVM_CACHE_DIR", str(tmp_path))
    calls: list = []
    monkeypatch.setattr(
        core_helpers, "amake_request", _fake_request(calls, 200, b"zip")
    )
    first = asyncio.run(download("https://x/a.zip", ttl_hours=12))
    second = asyncio.run(download("https://x/a.zip", ttl_hours=12))
    assert (first, second, len(calls)) == (b"zip", b"zip", 1)


def test_download_unpublished_month_returns_empty_and_is_not_cached(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENBB_CVM_CACHE_DIR", str(tmp_path))
    calls: list = []
    monkeypatch.setattr(core_helpers, "amake_request", _fake_request(calls, 404))
    assert asyncio.run(download("https://x/b.zip", ttl_hours=12)) == b""
    assert list(tmp_path.iterdir()) == []
