"""Pix, POS terminals, unemployment and population by UF (long format)."""

import datetime as dt

import pytest

from brasil_painel.regional import armazem, ibge, maquininhas, pix, ufs

HOJE = dt.date(2026, 10, 20)


def test_uf_codes_cover_the_27_units():
    assert len(ufs.SIGLAS) == 27
    assert ufs.SIGLAS[31] == "MG" and ufs.NOMES["DF"] == "Distrito Federal"


def test_pix_sums_municipalities_and_drops_the_current_month():
    linhas = [
        {
            "AnoMes": 202609,
            "Estado_Ibge": 31,
            "VL_PagadorPF": 10.0,
            "VL_PagadorPJ": 1.0,
            "VL_RecebedorPF": 5.0,
            "VL_RecebedorPJ": 2.0,
        },
        {
            "AnoMes": 202609,
            "Estado_Ibge": 31,
            "VL_PagadorPF": 20.0,
            "VL_PagadorPJ": 1.0,
            "VL_RecebedorPF": 5.0,
            "VL_RecebedorPJ": 3.0,
        },
        {
            "AnoMes": 202610,
            "Estado_Ibge": 31,
            "VL_PagadorPF": 99.0,
            "VL_PagadorPJ": 9.0,
            "VL_RecebedorPF": 9.0,
            "VL_RecebedorPJ": 9.0,
        },
    ]
    df = pix.por_uf(linhas, HOJE)
    assert list(df.columns) == armazem.SCHEMA_LONGO.names
    pago_pf = df[(df.indicador == "pix_pago_pf") & (df.uf == "MG")]
    assert pago_pf.valor.tolist() == [30.0]
    assert pago_pf.data.tolist() == [dt.date(2026, 9, 1)]
    br = df[(df.indicador == "pix_recebido_pj") & (df.uf == "BR")]
    assert br.valor.tolist() == [5.0]


def test_pos_terminals_by_quarter():
    linhas = [
        {"trimestre": 20262, "UFTerminal": "PA", "qtdTermPOS": 100},
        {"trimestre": 20262, "UFTerminal": "PR", "qtdTermPOS": 300},
        {"trimestre": 20261, "UFTerminal": "PA", "qtdTermPOS": 90},
    ]
    df = maquininhas.por_uf(linhas)
    assert df[df.uf == "PA"].sort_values("data").data.tolist() == [
        dt.date(2026, 3, 1),
        dt.date(2026, 6, 1),
    ]
    assert df[(df.uf == "BR") & (df.data == dt.date(2026, 6, 1))].valor.tolist() == [
        400.0
    ]
    assert set(df.indicador) == {"maquininhas_pos"}


def test_ibge_rows_by_state_and_brazil():
    linhas = [
        {"period": "202602", "level": "N3", "location_id": "31", "value": 5.1},
        {"period": "202602", "level": "N1", "location_id": "1", "value": 5.6},
        {"period": "202601", "level": "N3", "location_id": "31", "value": None},
    ]
    df = ibge.longo(linhas, "desemprego")
    assert sorted(df.uf) == ["BR", "MG"]
    assert df.data.unique().tolist() == [dt.date(2026, 6, 1)]


@pytest.mark.parametrize(
    ("periodo", "trimestral", "data"),
    [
        ("202602", True, dt.date(2026, 6, 1)),
        ("2026", False, dt.date(2026, 1, 1)),
        ("202608", False, dt.date(2026, 8, 1)),
    ],
)
def test_ibge_period_codes(periodo, trimestral, data):
    assert ibge.data_do_periodo(periodo, trimestral) == data
