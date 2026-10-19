"""Unit tests for the BCB disk cache."""

import asyncio
import json
import os
import time

from openbb_bcb.utils.cache import cached_rows


def _loader(calls, rows):
    async def load():
        calls.append(1)
        return rows

    return load


def test_second_call_reads_from_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_BCB_CACHE_DIR", str(tmp_path))
    calls: list = []
    rows = [{"a": 1}]
    first = asyncio.run(cached_rows("k", _loader(calls, rows), ttl_days=7))
    second = asyncio.run(cached_rows("k", _loader(calls, rows), ttl_days=7))
    assert (first, second, len(calls)) == (rows, rows, 1)
    assert json.loads(next(tmp_path.iterdir()).read_text()) == rows


def test_expired_entry_is_reloaded(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_BCB_CACHE_DIR", str(tmp_path))
    calls: list = []
    asyncio.run(cached_rows("k", _loader(calls, [{"a": 1}]), ttl_days=7))
    entry = next(tmp_path.iterdir())
    old = time.time() - 8 * 86400
    os.utime(entry, (old, old))
    fresh = asyncio.run(cached_rows("k", _loader(calls, [{"a": 2}]), ttl_days=7))
    assert (fresh, len(calls)) == ([{"a": 2}], 2)


def test_use_cache_false_bypasses_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_BCB_CACHE_DIR", str(tmp_path))
    calls: list = []
    asyncio.run(cached_rows("k", _loader(calls, [{"a": 1}]), use_cache=False))
    assert (len(calls), list(tmp_path.iterdir())) == (1, [])


def test_empty_result_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_BCB_CACHE_DIR", str(tmp_path))
    calls: list = []
    asyncio.run(cached_rows("k", _loader(calls, []), ttl_days=7))
    asyncio.run(cached_rows("k", _loader(calls, []), ttl_days=7))
    assert len(calls) == 2
