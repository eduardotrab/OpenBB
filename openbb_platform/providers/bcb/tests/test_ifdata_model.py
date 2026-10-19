"""Unit tests for the BCB IF.data model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_bcb.models.ifdata import (
    BcbIfDataFetcher,
    BcbIfDataQueryParams,
    build_cadastro_url,
    build_values_url,
    latest_available_period,
)

BASE = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (datetime.date(2026, 10, 19), "202606"),
        (datetime.date(2026, 9, 12), "202603"),
        (datetime.date(2026, 9, 13), "202606"),
        (datetime.date(2026, 2, 1), "202509"),
    ],
)
def test_latest_available_period_is_last_quarter_end_75_days_ago(today, expected):
    assert latest_available_period(today) == expected


def test_query_normalizes_period_and_cnpj():
    query = BcbIfDataFetcher.transform_query(
        {"period": "2026-06", "institution": "02.217.068/0001-08"}
    )
    assert (query.period, query.institution) == ("202606", "02217068")


def test_query_rejects_month_that_is_not_a_quarter_end():
    with pytest.raises(ValueError):
        BcbIfDataQueryParams(period="202605")


def test_query_defaults():
    query = BcbIfDataFetcher.transform_query({})
    assert (query.report, query.institution_type, query.segment) == (
        1,
        "individual",
        "cooperatives",
    )
    assert query.period == latest_available_period(datetime.date.today())


def test_build_cadastro_url_filters_cooperative_segments():
    query = BcbIfDataQueryParams(period="202606")
    assert build_cadastro_url(query) == (
        BASE + "IfDataCadastro(AnoMes=@AnoMes)?@AnoMes=202606"
        "&$filter=Tcb%20eq%20%27B3S%27%20or%20Tcb%20eq%20%27B3C%27&$format=json"
    )


def test_build_cadastro_url_institution_wins_over_segment():
    query = BcbIfDataQueryParams(period="202606", institution="02217068")
    assert build_cadastro_url(query) == (
        BASE + "IfDataCadastro(AnoMes=@AnoMes)?@AnoMes=202606"
        "&$filter=CodInst%20eq%20%2702217068%27&$format=json"
    )


def test_build_cadastro_url_all_segments_has_no_filter():
    query = BcbIfDataQueryParams(period="202606", segment="all")
    assert build_cadastro_url(query) == (
        BASE + "IfDataCadastro(AnoMes=@AnoMes)?@AnoMes=202606&$format=json"
    )


def test_build_values_url_maps_type_and_report():
    query = BcbIfDataQueryParams(
        period="202606", report=4, institution_type="prudential", institution="02217068"
    )
    assert build_values_url(query) == (
        BASE + "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,"
        "Relatorio=@Relatorio)?@AnoMes=202606&@TipoInstituicao=1&@Relatorio='4'"
        "&$filter=CodInst%20eq%20%2702217068%27&$format=json"
    )


CADASTRO = [
    {
        "CodInst": "02217068",
        "NomeInstituicao": "SICOOB CREDITABIL",
        "Tcb": "B3S",
        "Uf": "MG",
        "Municipio": "Belo Horizonte",
        "Situacao": "A",
    },
    {
        "CodInst": "11111111",
        "NomeInstituicao": "COOP SP",
        "Tcb": "B3S",
        "Uf": "SP",
        "Municipio": "São Paulo",
        "Situacao": "A",
    },
]


def _value(cod, column, saldo):
    return {
        "TipoInstituicao": 3,
        "CodInst": cod,
        "AnoMes": "202606",
        "NomeRelatorio": "Resumo",
        "NumeroRelatorio": "1",
        "Grupo": None,
        "Conta": "x",
        "NomeColuna": column,
        "DescricaoColuna": "d",
        "Saldo": saldo,
    }


VALUES = [
    _value("02217068", "Ativo Total", 91470436.17),
    _value("11111111", "Ativo Total", 5.0),
    _value("99999999", "Ativo Total", 1e12),  # bank, not in the cooperative cadastro
]


def test_transform_data_joins_cadastro_and_drops_institutions_outside_it():
    query = BcbIfDataQueryParams(period="202606")
    rows = BcbIfDataFetcher.transform_data(
        query, {"cadastro": CADASTRO, "values": VALUES}
    )
    assert [
        (r.institution, r.name, r.segment, r.uf, r.column, r.value) for r in rows
    ] == [
        ("02217068", "SICOOB CREDITABIL", "B3S", "MG", "Ativo Total", 91470436.17),
        ("11111111", "COOP SP", "B3S", "SP", "Ativo Total", 5.0),
    ]
    assert rows[0].period == datetime.date(2026, 6, 30)
    assert rows[0].report == "Resumo"


def test_transform_data_filters_uf():
    query = BcbIfDataQueryParams(period="202606", uf="sp")
    rows = BcbIfDataFetcher.transform_data(
        query, {"cadastro": CADASTRO, "values": VALUES}
    )
    assert [r.institution for r in rows] == ["11111111"]


def test_transform_data_without_rows_raises_empty_data():
    query = BcbIfDataQueryParams(period="202606")
    with pytest.raises(OpenBBError):
        BcbIfDataFetcher.transform_data(query, {"cadastro": CADASTRO, "values": []})
