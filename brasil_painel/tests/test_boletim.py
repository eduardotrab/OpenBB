"""Bulletin calculations: weekly closes, streaks and changes."""

import datetime as dt

import pytest

from brasil_painel.dados import boletim

D = dt.date


def test_weekly_keeps_the_last_value_of_each_iso_week():
    pontos = [(D(2026, 10, 5), 1.0), (D(2026, 10, 9), 2.0), (D(2026, 10, 12), 3.0)]
    assert boletim.semanal(pontos) == [(D(2026, 10, 9), 2.0), (D(2026, 10, 12), 3.0)]


@pytest.mark.parametrize(
    ("valores", "esperado"),
    [
        ([5.0, 5.1, 5.2, 5.22], ("sobe", 3)),
        ([5.3, 5.2, 5.25, 5.22], ("desce", 1)),
        ([13.25, 13.25, 13.25], ("estavel", 2)),
        ([1.0], ("estavel", 0)),
    ],
)
def test_streak_of_weekly_moves(valores, esperado):
    semanas = [
        (D(2026, 9, 7) + dt.timedelta(weeks=i), v) for i, v in enumerate(valores)
    ]
    assert boletim.sequencia(semanas) == esperado


def test_percent_change_against_a_week_before():
    pontos = [(D(2026, 10, 1), 100.0), (D(2026, 10, 8), 102.0), (D(2026, 10, 9), 104.0)]
    assert boletim.variacao_pct(pontos, 7) == pytest.approx(4.0)
    assert boletim.variacao_pct(pontos[:1], 7) is None


def test_crypto_failures_become_empty_quotes(monkeypatch):
    import requests

    def falha(*a, **k):
        raise requests.ConnectionError("fora do ar")

    boletim._CACHE.clear()
    monkeypatch.setattr(boletim, "_candles_mercado_bitcoin", falha)
    monkeypatch.setattr(boletim, "_candles_binance", falha)
    cotacoes = boletim.cripto()
    assert [c.rotulo for c in cotacoes] == ["Bitcoin", "Ether", "BNB"]
    assert all(c.valor is None for c in cotacoes)
    boletim._CACHE.clear()
