"""Summaries for the indicator cards: last value, comparison, trend, staleness."""

import datetime as dt

import pytest

from brasil_painel.dados.indicadores import (
    Ponto,
    data_de_periodo,
    resumir,
    tendencia,
)

D = dt.date


def serie(*valores, inicio=D(2026, 10, 1)):
    return [Ponto(inicio + dt.timedelta(days=i), v) for i, v in enumerate(valores)]


@pytest.mark.parametrize(
    ("atual", "anterior", "esperado"),
    [
        (5.1, 5.0, "sobe"),
        (4.9, 5.0, "desce"),
        (5.0, 5.0, "estavel"),
        (5.0001, 5.0, "estavel"),
    ],
)
def test_tendencia(atual, anterior, esperado):
    assert tendencia(atual, anterior, tolerancia=0.001) == esperado


def test_resumir_compares_with_n_steps_back():
    r = resumir(
        "Selic",
        serie(14.0, 14.0, 13.75),
        unidade="% a.a.",
        passos=2,
        max_dias=5,
        hoje=D(2026, 10, 3),
        fonte="BCB",
    )
    assert (r.valor, r.anterior, r.variacao, r.tendencia) == (
        13.75,
        14.0,
        -0.25,
        "desce",
    )
    assert r.data_ref == D(2026, 10, 3)
    assert not r.defasado


def test_resumir_compares_with_days_back_using_last_point_on_or_before():
    pontos = [
        Ponto(D(2026, 9, 1), 5.0),
        Ponto(D(2026, 9, 18), 5.2),
        Ponto(D(2026, 10, 19), 5.5),
    ]
    r = resumir(
        "Dólar",
        pontos,
        unidade="R$",
        dias=30,
        max_dias=4,
        hoje=D(2026, 10, 20),
        fonte="BCB",
    )
    assert r.anterior == 5.2
    assert r.variacao == pytest.approx(0.3)


def test_resumir_sorts_input_and_flags_stale_data():
    pontos = [Ponto(D(2026, 10, 2), 2.0), Ponto(D(2026, 10, 1), 1.0)]
    r = resumir(
        "X", pontos, unidade="", passos=1, max_dias=3, hoje=D(2026, 10, 10), fonte="F"
    )
    assert (r.valor, r.anterior, r.tendencia) == (2.0, 1.0, "sobe")
    assert r.defasado


def test_resumir_without_previous_point_has_no_trend():
    r = resumir(
        "X",
        serie(3.0),
        unidade="",
        passos=1,
        max_dias=3,
        hoje=D(2026, 10, 1),
        fonte="F",
    )
    assert (r.anterior, r.variacao, r.tendencia) == (None, None, None)


def test_resumir_empty_series_is_an_error_card():
    r = resumir(
        "X", [], unidade="", passos=1, max_dias=3, hoje=D(2026, 10, 1), fonte="F"
    )
    assert r.valor is None and r.erro


@pytest.mark.parametrize(
    ("periodo", "esperado"), [("202609", D(2026, 9, 1)), ("2026-09-30", D(2026, 9, 30))]
)
def test_data_de_periodo(periodo, esperado):
    assert data_de_periodo(periodo) == esperado


def test_percent_change_and_decimals():
    pontos = [Ponto(dt.date(2025, 9, 30), 400.0), Ponto(dt.date(2026, 9, 30), 480.0)]
    resumo = resumir(
        "Soja",
        pontos,
        unidade="US$/t",
        fonte="IMF",
        max_dias=75,
        hoje=dt.date(2026, 10, 20),
        passos=1,
        percentual=True,
        casas=1,
    )
    assert resumo.variacao == pytest.approx(20.0)
    assert (resumo.percentual, resumo.casas) == (True, 1)
