"""Unit tests for the Receita federal revenue model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_receita.models.revenue import (
    ReceitaRevenueFetcher,
    ReceitaRevenueQueryParams,
    parse_number,
    parse_revenue_csv,
)

CSV = (
    "Ano;Mês;UF;IMPOSTO SOBRE IMPORTAÇÃO;IRPF;RECEITA PREVIDENCIÁRIA\n"
    "2025;Dezembro;SP;1.234,50;10;-0,01\n"
    "2026;Janeiro;SP;100,25;;7\n"
    "2026;Janeiro;RJ;50;20,5;3\n"
)


def test_parse_revenue_csv_melts_taxes_and_parses_numbers():
    rows = parse_revenue_csv(CSV)
    assert rows[:3] == [
        {
            "date": datetime.date(2025, 12, 1),
            "uf": "SP",
            "tax": "IMPOSTO SOBRE IMPORTAÇÃO",
            "value": 1234.5,
        },
        {"date": datetime.date(2025, 12, 1), "uf": "SP", "tax": "IRPF", "value": 10.0},
        {
            "date": datetime.date(2025, 12, 1),
            "uf": "SP",
            "tax": "RECEITA PREVIDENCIÁRIA",
            "value": -0.01,
        },
    ]
    assert {
        "date": datetime.date(2026, 1, 1),
        "uf": "SP",
        "tax": "IRPF",
        "value": None,
    } in rows


def test_query_defaults_to_previous_and_current_year():
    query = ReceitaRevenueFetcher.transform_query({})
    year = datetime.date.today().year
    assert (query.start_year, query.end_year) == (year - 1, year)


def test_transform_filters_years_uf_and_tax_accent_insensitive():
    query = ReceitaRevenueQueryParams(
        start_year=2026, end_year=2026, uf="sp,rj", tax="previdenciaria"
    )
    rows = ReceitaRevenueFetcher.transform_data(query, parse_revenue_csv(CSV))
    assert [(r.date, r.uf, r.value) for r in rows] == [
        (datetime.date(2026, 1, 1), "RJ", 3.0),
        (datetime.date(2026, 1, 1), "SP", 7.0),
    ]


def test_transform_without_matches_raises_empty_data():
    query = ReceitaRevenueQueryParams(start_year=2030, end_year=2030)
    with pytest.raises(OpenBBError):
        ReceitaRevenueFetcher.transform_data(query, parse_revenue_csv(CSV))


@pytest.mark.parametrize(
    ("year", "raw", "expected"),
    [
        (2001, "47,953,915", 47953915.0),
        (2002, "1,014,655,323", 1014655323.0),
        (2001, "216,648", 216648.0),
        (2001, "12,5", 12.5),
        (2010, "216,648", 216.648),
        (2010, "-7544,36", -7544.36),
        (2023, "91.155.798", 91155798.0),
        (2024, "226.708.856,85", 226708856.85),
        (2025, "231", 231.0),
        (2025, "", None),
    ],
)
def test_parse_number_follows_the_format_of_each_era(year, raw, expected):
    assert parse_number(raw, year) == expected
