"""Unit tests for the BCB SGS time series model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_bcb.models.sgs import (
    BcbSgsFetcher,
    BcbSgsQueryParams,
    build_sgs_url,
    date_windows,
    parse_sgs_rows,
    resolve_series,
)


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("selic_target", [432]),
        ("cdi,ipca", [12, 433]),
        ("432, 25518", [432, 25518]),
        ("SELIC", [11]),
    ],
)
def test_resolve_series_accepts_names_and_codes(symbol, expected):
    assert resolve_series(symbol) == expected


def test_resolve_series_rejects_unknown_names():
    with pytest.raises(OpenBBError):
        resolve_series("not_a_series")


def test_build_sgs_url_uses_dd_mm_yyyy():
    assert build_sgs_url(
        432, datetime.date(2026, 1, 5), datetime.date(2026, 10, 16)
    ) == (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json"
        "&dataInicial=05/01/2026&dataFinal=16/10/2026"
    )


def test_date_windows_split_ranges_longer_than_10_years():
    assert date_windows(datetime.date(2000, 1, 1), datetime.date(2026, 10, 16)) == [
        (datetime.date(2000, 1, 1), datetime.date(2009, 12, 31)),
        (datetime.date(2010, 1, 1), datetime.date(2019, 12, 31)),
        (datetime.date(2020, 1, 1), datetime.date(2026, 10, 16)),
    ]


def test_date_windows_short_range_is_single_window():
    start, end = datetime.date(2026, 1, 1), datetime.date(2026, 10, 16)
    assert date_windows(start, end) == [(start, end)]


def test_parse_sgs_rows_converts_dates_and_decimal_strings():
    raw = [
        {"data": "15/10/2026", "valor": "0.055131"},
        {"data": "16/10/2026", "valor": "0.055131"},
        {"data": "17/10/2026", "valor": ""},
    ]
    assert parse_sgs_rows(432, raw) == [
        {"date": datetime.date(2026, 10, 15), "symbol": "432", "value": 0.055131},
        {"date": datetime.date(2026, 10, 16), "symbol": "432", "value": 0.055131},
    ]


def test_query_defaults_to_one_year():
    query = BcbSgsFetcher.transform_query({"symbol": "cdi"})
    assert query.end_date == datetime.date.today()
    assert query.start_date == datetime.date.today() - datetime.timedelta(days=365)


def test_transform_data_names_known_series_and_sorts():
    query = BcbSgsQueryParams(symbol="ipca,432")
    raw = [
        {"date": datetime.date(2026, 9, 1), "symbol": "433", "value": 0.48},
        {"date": datetime.date(2026, 10, 1), "symbol": "432", "value": 13.75},
        {"date": datetime.date(2026, 9, 1), "symbol": "432", "value": 14.0},
    ]
    rows = BcbSgsFetcher.transform_data(query, raw)
    assert [(r.symbol, r.name, r.date, r.value) for r in rows] == [
        ("432", "selic_target", datetime.date(2026, 9, 1), 14.0),
        ("432", "selic_target", datetime.date(2026, 10, 1), 13.75),
        ("433", "ipca", datetime.date(2026, 9, 1), 0.48),
    ]


def test_transform_data_without_rows_raises_empty_data():
    with pytest.raises(OpenBBError):
        BcbSgsFetcher.transform_data(BcbSgsQueryParams(symbol="cdi"), [])
