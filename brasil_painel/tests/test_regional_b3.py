"""B3 COTAHIST fixed-width parsing and the Ibovespa portfolio."""

import datetime as dt

import pytest

from brasil_painel.regional import b3

PETR4 = (
    "012026101402PETR4       010PETROBRAS   PN      N2   R$  000000000568800000000058110000000005674000000000577500"
    "000000058110000000005811000000000581267979000000000042367600000000244678167200000000000000009999123100000010000000"
    "000000BRPETRACNPR6230"
)


def test_fixed_width_record_of_a_cash_stock():
    r = b3.ler_linha(PETR4)
    assert (r["data"], r["ticker"], r["nome"]) == (
        dt.date(2026, 10, 14),
        "PETR4",
        "PETROBRAS",
    )
    assert (r["abertura"], r["maxima"], r["minima"], r["fechamento"]) == (
        56.88,
        58.11,
        56.74,
        58.11,
    )
    assert r["negocios"] == 67979
    assert r["volume"] == pytest.approx(2446781672.0)


def test_other_records_are_skipped():
    assert b3.ler_linha("00COTAHIST.2026BOVESPA 20261020" + " " * 200) is None
    assert b3.ler_linha(PETR4[:10] + "12" + PETR4[12:]) is None  # not BDI 02
    assert b3.ler_linha(PETR4[:24] + "070" + PETR4[27:]) is None  # options market


def test_ibov_weights_use_brazilian_decimals():
    df = b3.carteira_ibov(
        [{"cod": "ABEV3", "asset": "AMBEV S/A", "type": "ON", "part": "2,336"}],
        dt.date(2026, 10, 21),
    )
    assert df.iloc[0].peso == pytest.approx(2.336)
