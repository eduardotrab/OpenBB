"""Unit tests for the Tesouro Direto model (no network)."""

import asyncio
import datetime
import os
import time

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_tesouro.models.direto import (
    TesouroDiretoFetcher,
    TesouroDiretoQueryParams,
    parse_csv,
)
from openbb_tesouro.utils.cache import cached_text

CSV = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha\n"
    "Tesouro Selic;01/03/2029;15/10/2026;0,05;0,06;20073,14;20058,12;20058,12\n"
    "Tesouro IPCA+;15/05/2035;15/10/2026;7,10;7,22;2300,10;2280,00;2280,00\n"
    "Tesouro IPCA+;15/05/2035;14/10/2026;7,08;7,20;2301,00;2281,00;2281,00\n"
    "Tesouro IPCA+;15/05/2035;01/01/2020;3,00;3,10;1000,00;990,00;990,00\n"
    "Tesouro Prefixado;01/01/2029;15/10/2026;;;;850,00;850,00\n"
)


def test_parse_csv_converts_brazilian_numbers_and_dates():
    rows = parse_csv(CSV)
    assert rows[0] == {
        "date": datetime.date(2026, 10, 15),
        "bond": "Tesouro Selic",
        "maturity": datetime.date(2029, 3, 1),
        "buy_rate": 0.05,
        "sell_rate": 0.06,
        "buy_price": 20073.14,
        "sell_price": 20058.12,
        "base_price": 20058.12,
    }
    assert (rows[-1]["buy_rate"], rows[-1]["buy_price"]) == (None, None)


def test_query_defaults_to_last_30_days():
    query = TesouroDiretoFetcher.transform_query({})
    assert query.end_date == datetime.date.today()
    assert query.start_date == datetime.date.today() - datetime.timedelta(days=30)


def test_transform_data_filters_dates_and_bond_substring_sorted():
    query = TesouroDiretoQueryParams(
        bond="ipca+", start_date="2026-10-01", end_date="2026-10-15"
    )
    rows = TesouroDiretoFetcher.transform_data(query, parse_csv(CSV))
    assert [(r.date, r.bond, r.sell_rate) for r in rows] == [
        (datetime.date(2026, 10, 14), "Tesouro IPCA+", 7.20),
        (datetime.date(2026, 10, 15), "Tesouro IPCA+", 7.22),
    ]


def test_transform_data_without_matches_raises_empty_data():
    query = TesouroDiretoQueryParams(start_date="2030-01-01", end_date="2030-01-31")
    with pytest.raises(OpenBBError):
        TesouroDiretoFetcher.transform_data(query, parse_csv(CSV))


def test_cached_text_reuses_file_within_ttl(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_TESOURO_CACHE_DIR", str(tmp_path))
    calls: list = []

    async def loader():
        calls.append(1)
        return "csv"

    first = asyncio.run(cached_text("k", loader, ttl_hours=12))
    second = asyncio.run(cached_text("k", loader, ttl_hours=12))
    assert (first, second, len(calls)) == ("csv", "csv", 1)
    entry = next(tmp_path.iterdir())
    old = time.time() - 13 * 3600
    os.utime(entry, (old, old))
    asyncio.run(cached_text("k", loader, ttl_hours=12))
    assert len(calls) == 2


def test_download_timeout_is_not_cut_by_request_timeout_preference(monkeypatch):
    """The 60 s default of `preferences.request_timeout` must not cut the slow download."""
    from openbb_core.provider.utils import helpers

    captured: dict = {}

    async def fake_request(url, **kwargs):
        captured.update(kwargs)
        return CSV

    monkeypatch.setattr(helpers, "amake_request", fake_request)
    query = TesouroDiretoQueryParams(use_cache=False)
    asyncio.run(
        TesouroDiretoFetcher.aextract_data(
            query, None, preferences={"request_timeout": 60}
        )
    )
    assert "preferences" not in captured
    assert captured["timeout"] >= 300
