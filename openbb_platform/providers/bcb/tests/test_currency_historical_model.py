"""Unit tests for the BCB PTAX currency historical model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_bcb.models.currency_historical import (
    BcbCurrencyHistoricalFetcher,
    BcbCurrencyHistoricalQueryParams,
    build_ptax_url,
    split_ptax_symbol,
)


def _row(buy, sell, when, bulletin):
    return {
        "paridadeCompra": 1.0,
        "paridadeVenda": 1.0,
        "cotacaoCompra": buy,
        "cotacaoVenda": sell,
        "dataHoraCotacao": when,
        "tipoBoletim": bulletin,
    }


RAW = [
    {
        **_row(5.0595, 5.0601, "2026-10-15 10:03:45.504865", "Abertura"),
        "_currency": "USD",
    },
    {
        **_row(5.0518, 5.0524, "2026-10-15 11:10:13.747529", "Intermediário"),
        "_currency": "USD",
    },
    {
        **_row(5.0610, 5.0616, "2026-10-15 13:10:35.446900", "Fechamento"),
        "_currency": "USD",
    },
    {
        **_row(5.0700, 5.0706, "2026-10-16 13:09:12.100000", "Fechamento"),
        "_currency": "USD",
    },
    {
        **_row(5.8800, 5.8830, "2026-10-15 13:10:35.446900", "Fechamento"),
        "_currency": "EUR",
    },
]


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [("USDBRL", "USD"), ("USD", "USD"), ("eurbrl", "EUR"), ("EUR-BRL", "EUR")],
)
def test_split_ptax_symbol_returns_foreign_currency(symbol, expected):
    assert split_ptax_symbol(symbol.upper().replace("-", "")) == expected


@pytest.mark.parametrize("symbol", ["BRLUSD", "USDEUR", "USDBR", "BRL"])
def test_split_ptax_symbol_rejects_pairs_not_quoted_in_brl(symbol):
    with pytest.raises(OpenBBError):
        split_ptax_symbol(symbol)


def test_build_ptax_url_uses_olinda_mm_dd_yyyy_dates():
    url = build_ptax_url("USD", datetime.date(2026, 10, 1), datetime.date(2026, 10, 17))
    assert url == (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,"
        "dataFinalCotacao=@dataFinalCotacao)"
        "?@moeda='USD'&@dataInicial='10-01-2026'&@dataFinalCotacao='10-17-2026'"
        "&$format=json"
    )


def test_query_defaults_to_last_30_days_closing_bulletin():
    query = BcbCurrencyHistoricalFetcher.transform_query({"symbol": "usd-brl"})
    assert query.symbol == "USDBRL"
    assert query.bulletin == "close"
    assert query.end_date == datetime.date.today()
    assert query.start_date == datetime.date.today() - datetime.timedelta(days=30)


def test_transform_data_keeps_only_closing_bulletin_with_sell_rate_as_close():
    query = BcbCurrencyHistoricalQueryParams(
        symbol="USDBRL", start_date="2026-10-15", end_date="2026-10-16"
    )
    rows = BcbCurrencyHistoricalFetcher.transform_data(query, RAW)
    assert [(r.date, r.symbol, r.close, r.bid) for r in rows] == [
        (datetime.date(2026, 10, 15), "USDBRL", 5.0616, 5.0610),
        (datetime.date(2026, 10, 16), "USDBRL", 5.0706, 5.0700),
    ]


def test_transform_data_all_bulletins_keeps_intraday_timestamps():
    query = BcbCurrencyHistoricalQueryParams(
        symbol="USDBRL", start_date="2026-10-15", end_date="2026-10-15", bulletin="all"
    )
    rows = BcbCurrencyHistoricalFetcher.transform_data(query, RAW)
    assert [(r.date, r.bulletin) for r in rows] == [
        (datetime.datetime(2026, 10, 15, 10, 3, 45, 504865), "Abertura"),
        (datetime.datetime(2026, 10, 15, 11, 10, 13, 747529), "Intermediário"),
        (datetime.datetime(2026, 10, 15, 13, 10, 35, 446900), "Fechamento"),
        (datetime.datetime(2026, 10, 16, 13, 9, 12, 100000), "Fechamento"),
    ]


def test_transform_data_multiple_symbols_sorted_by_symbol_then_date():
    query = BcbCurrencyHistoricalQueryParams(
        symbol="USDBRL,EURBRL", start_date="2026-10-15", end_date="2026-10-16"
    )
    rows = BcbCurrencyHistoricalFetcher.transform_data(query, RAW)
    assert [(r.symbol, r.date, r.close) for r in rows] == [
        ("EURBRL", datetime.date(2026, 10, 15), 5.8830),
        ("USDBRL", datetime.date(2026, 10, 15), 5.0616),
        ("USDBRL", datetime.date(2026, 10, 16), 5.0706),
    ]


def test_transform_data_without_rows_raises_empty_data():
    query = BcbCurrencyHistoricalQueryParams(symbol="USDBRL")
    with pytest.raises(OpenBBError):
        BcbCurrencyHistoricalFetcher.transform_data(query, [])
