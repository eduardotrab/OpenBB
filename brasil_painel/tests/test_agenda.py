"""Release calendar: Copom (static file), Focus (rule) and IBGE (API)."""

import datetime as dt

from brasil_painel.dados.agenda import (
    Evento,
    eventos_copom,
    eventos_focus,
    eventos_ibge,
    proximos,
)

D = dt.date


def test_copom_decision_on_second_day_and_minutes_next_tuesday():
    eventos = eventos_copom([["2026-11-03", "2026-11-04"]])
    assert eventos == [
        Evento(D(2026, 11, 4), "após 18h", "Copom — decisão da Selic", "BCB"),
        Evento(D(2026, 11, 10), "8h", "Copom — ata da reunião", "BCB"),
    ]


def test_focus_every_monday_in_window():
    eventos = eventos_focus(D(2026, 10, 20), D(2026, 11, 3))
    assert [e.data for e in eventos] == [D(2026, 10, 26), D(2026, 11, 3)]
    assert eventos[0].titulo == "Boletim Focus"


def test_ibge_keeps_market_indicators_only():
    rows = [
        {
            "titulo": "Índice Nacional de Preços ao Consumidor Amplo 15",
            "data_divulgacao": "23/10/2026 12:00:00",
            "tipo": "Divulgação de Indicadores",
            "mes_referencia_inicio": 10,
            "ano_referencia_inicio": 2026,
        },
        {
            "titulo": "Contas Econômicas Ambientais",
            "data_divulgacao": "22/10/2026 13:00:00",
            "tipo": "Produtos Geocientíficos Experimentais",
            "mes_referencia_inicio": 0,
            "ano_referencia_inicio": 0,
        },
        {
            "titulo": "Pesquisa Mensal de Comércio",
            "data_divulgacao": "11/11/2026 09:00:00",
            "tipo": "Divulgação de Indicadores",
            "mes_referencia_inicio": 9,
            "ano_referencia_inicio": 2026,
        },
    ]
    eventos = eventos_ibge(rows)
    assert eventos == [
        Evento(D(2026, 10, 23), "12h", "IPCA-15 (out/2026)", "IBGE"),
        Evento(D(2026, 11, 11), "9h", "Pesquisa Mensal de Comércio (set/2026)", "IBGE"),
    ]


def test_proximos_window_and_order():
    hoje = D(2026, 10, 20)
    eventos = [
        Evento(D(2026, 10, 28), None, "fora", "X"),
        Evento(D(2026, 10, 22), None, "b", "X"),
        Evento(D(2026, 10, 20), None, "a", "X"),
        Evento(D(2026, 10, 19), None, "passado", "X"),
    ]
    assert [e.titulo for e in proximos(eventos, hoje, dias=7)] == ["a", "b"]


def test_focus_moves_to_next_business_day_on_fixed_holiday():
    eventos = eventos_focus(D(2026, 10, 27), D(2026, 11, 4))
    assert [e.data for e in eventos] == [D(2026, 11, 3)]  # 2/11 é Finados
