"""Unit tests for the BCB Focus market expectations model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_bcb.models.focus import (
    BcbFocusFetcher,
    BcbFocusQueryParams,
    build_focus_url,
)

BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"


def test_build_focus_url_annual_filters_indicator_dates_and_base():
    query = BcbFocusQueryParams(
        indicator="PIB Total", start_date="2026-10-01", end_date="2026-10-09"
    )
    assert build_focus_url(query) == (
        BASE + "ExpectativasMercadoAnuais?$filter=Indicador%20eq%20%27PIB%20Total%27"
        "%20and%20Data%20ge%20%272026-10-01%27%20and%20Data%20le%20%272026-10-09%27"
        "%20and%20baseCalculo%20eq%200&$orderby=Data%20desc&$format=json"
    )


def test_build_focus_url_monthly_with_5_day_base_encodes_accents():
    query = BcbFocusQueryParams(
        indicator="Câmbio",
        frequency="monthly",
        calculation_base="5d",
        start_date="2026-10-01",
        end_date="2026-10-09",
    )
    assert build_focus_url(query) == (
        BASE + "ExpectativaMercadoMensais?$filter=Indicador%20eq%20%27C%C3%A2mbio%27"
        "%20and%20Data%20ge%20%272026-10-01%27%20and%20Data%20le%20%272026-10-09%27"
        "%20and%20baseCalculo%20eq%201&$orderby=Data%20desc&$format=json"
    )


def test_build_focus_url_selic_ignores_indicator():
    query = BcbFocusQueryParams(
        indicator="IPCA",
        frequency="selic",
        start_date="2026-10-01",
        end_date="2026-10-09",
    )
    assert build_focus_url(query) == (
        BASE + "ExpectativasMercadoSelic?$filter=Data%20ge%20%272026-10-01%27"
        "%20and%20Data%20le%20%272026-10-09%27%20and%20baseCalculo%20eq%200"
        "&$orderby=Data%20desc&$format=json"
    )


def test_query_defaults_to_ipca_annual_last_30_days():
    query = BcbFocusFetcher.transform_query({})
    assert (query.indicator, query.frequency, query.calculation_base) == (
        "IPCA",
        "annual",
        "30d",
    )
    assert query.end_date == datetime.date.today()
    assert query.start_date == datetime.date.today() - datetime.timedelta(days=30)


def test_transform_data_maps_annual_rows():
    query = BcbFocusQueryParams(indicator="IPCA")
    raw = [
        {
            "Indicador": "IPCA",
            "IndicadorDetalhe": None,
            "Data": "2026-10-09",
            "DataReferencia": "2026",
            "Media": 5.2056,
            "Mediana": 5.2245,
            "DesvioPadrao": 0.1947,
            "Minimo": 4.5,
            "Maximo": 5.875,
            "numeroRespondentes": 144,
            "baseCalculo": 0,
        }
    ]
    rows = BcbFocusFetcher.transform_data(query, raw)
    assert [r.model_dump() for r in rows] == [
        {
            "date": datetime.date(2026, 10, 9),
            "indicator": "IPCA",
            "indicator_detail": None,
            "reference": "2026",
            "mean": 5.2056,
            "median": 5.2245,
            "std_dev": 0.1947,
            "min": 4.5,
            "max": 5.875,
            "respondents": 144,
        }
    ]


def test_transform_data_selic_uses_meeting_as_reference():
    query = BcbFocusQueryParams(frequency="selic")
    raw = [
        {
            "Indicador": "Selic",
            "Data": "2026-10-09",
            "Reuniao": "R6/2028",
            "Media": 10.6847,
            "Mediana": 10.5,
            "DesvioPadrao": 0.9026,
            "Minimo": 8.5,
            "Maximo": 13.0,
            "numeroRespondentes": 88,
            "baseCalculo": 0,
        }
    ]
    rows = BcbFocusFetcher.transform_data(query, raw)
    assert [(r.indicator, r.reference, r.median) for r in rows] == [
        ("Selic", "R6/2028", 10.5)
    ]


def test_transform_data_without_rows_raises_empty_data():
    with pytest.raises(OpenBBError):
        BcbFocusFetcher.transform_data(BcbFocusQueryParams(), [])
