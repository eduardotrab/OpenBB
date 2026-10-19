"""The revenue download must not ask gov.br for JSON (it answers 401)."""

import asyncio

import openbb_core.provider.utils.helpers as core_helpers

from openbb_receita.models.revenue import (
    ReceitaRevenueFetcher,
    ReceitaRevenueQueryParams,
)


class FakeResponse:
    status = 200

    async def read(self):
        return "Ano;Mês;UF;IRPF\n2026;Março;SP;1,5\n".encode("latin-1")


def test_download_sends_csv_accept_header(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBB_RECEITA_CACHE_DIR", str(tmp_path))
    seen: dict = {}

    async def fake(url, timeout, response_callback, **kwargs):
        seen.update(kwargs.get("headers") or {})
        return await response_callback(FakeResponse(), None)

    monkeypatch.setattr(core_helpers, "amake_request", fake)
    query = ReceitaRevenueQueryParams(start_year=2026, end_year=2026, use_cache=False)
    rows = asyncio.run(ReceitaRevenueFetcher.aextract_data(query, None))
    assert "json" not in seen.get("Accept", "application/json")
    assert rows[0]["value"] == 1.5
