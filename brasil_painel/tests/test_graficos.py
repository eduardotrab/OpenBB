"""Transformations behind the Focus and Tesouro charts."""

import datetime as dt

from brasil_painel.componentes.graficos import figura_curva, figura_focus
from brasil_painel.dados.mercado import curvas_tesouro, series_focus

D = dt.date


def test_series_focus_keeps_requested_years_sorted_by_date():
    rows = [
        {"date": "2026-10-16", "indicator": "IPCA", "reference": "2026", "median": 4.5},
        {"date": "2026-10-09", "indicator": "IPCA", "reference": "2026", "median": 4.4},
        {"date": "2026-10-16", "indicator": "IPCA", "reference": "2027", "median": 3.9},
        {"date": "2026-10-16", "indicator": "IPCA", "reference": "2030", "median": 3.5},
        {
            "date": "2026-10-16",
            "indicator": "IPCA",
            "reference": "2026",
            "median": None,
        },
    ]
    series = series_focus(rows, anos=[2026, 2027])
    assert series == {
        2026: [(D(2026, 10, 9), 4.4), (D(2026, 10, 16), 4.5)],
        2027: [(D(2026, 10, 16), 3.9)],
    }


ROWS_TESOURO = [
    {
        "date": "2026-10-15",
        "bond": "Tesouro Prefixado",
        "maturity": "2029-01-01",
        "buy_rate": 12.64,
        "sell_rate": 12.76,
    },
    {
        "date": "2026-10-15",
        "bond": "Tesouro Prefixado com Juros Semestrais",
        "maturity": "2035-01-01",
        "buy_rate": None,
        "sell_rate": 13.1,
    },
    {
        "date": "2026-10-15",
        "bond": "Tesouro Prefixado",
        "maturity": "2027-01-01",
        "buy_rate": 13.37,
        "sell_rate": 13.49,
    },
    {
        "date": "2026-10-15",
        "bond": "Tesouro IPCA+ com Juros Semestrais",
        "maturity": "2035-05-15",
        "buy_rate": 7.0,
        "sell_rate": 7.1,
    },
    {
        "date": "2026-10-15",
        "bond": "Tesouro IPCA+",
        "maturity": "2035-05-15",
        "buy_rate": 7.1,
        "sell_rate": 7.22,
    },
    {
        "date": "2026-10-15",
        "bond": "Tesouro Selic",
        "maturity": "2031-03-01",
        "buy_rate": 0.09,
        "sell_rate": 0.1,
    },
    {
        "date": "2026-10-15",
        "bond": "Tesouro Educa+",
        "maturity": "2040-01-15",
        "buy_rate": 7.0,
        "sell_rate": 7.1,
    },
    {
        "date": "2026-09-15",
        "bond": "Tesouro Prefixado",
        "maturity": "2027-01-01",
        "buy_rate": 13.9,
        "sell_rate": 14.0,
    },
    {
        "date": "2026-09-14",
        "bond": "Tesouro Prefixado",
        "maturity": "2027-01-01",
        "buy_rate": 13.8,
        "sell_rate": 13.9,
    },
]


def test_curvas_tesouro_today_and_30_days_before():
    curvas = curvas_tesouro(ROWS_TESOURO, dias=30)
    assert curvas.data == D(2026, 10, 15)
    assert curvas.data_anterior == D(2026, 9, 15)
    assert curvas.hoje["Prefixado"] == [
        (D(2027, 1, 1), 13.37),
        (D(2029, 1, 1), 12.64),
        (D(2035, 1, 1), 13.1),
    ]
    assert curvas.hoje["IPCA+"] == [(D(2035, 5, 15), 7.1)]
    assert curvas.anterior["Prefixado"] == [(D(2027, 1, 1), 13.9)]
    assert set(curvas.hoje) == {"Prefixado", "IPCA+"}


def test_figures_have_one_axis_per_panel_and_legend():
    rows = [
        {"date": "2026-10-16", "indicator": i, "reference": "2026", "median": 1.0}
        for i in ("IPCA", "Selic", "PIB Total", "Câmbio")
    ]
    fig = figura_focus(
        {
            i: series_focus(rows, anos=[2026, 2027])
            for i in ("IPCA", "Selic", "PIB Total", "Câmbio")
        }
    )
    assert len(fig.data) >= 4
    fig = figura_curva(curvas_tesouro(ROWS_TESOURO, dias=30))
    nomes = {t.name for t in fig.data}
    assert nomes == {"15/10/2026", "15/09/2026"}


def test_line_chart_labels_last_points_and_keeps_entity_colors():
    import datetime as dt

    from brasil_painel.componentes.graficos import CORES_ENTIDADE, figura_linhas
    from brasil_painel.dados.indicadores import Ponto

    series = {
        "Brasil": [Ponto(dt.date(2026, 8, 1), 4.7), Ponto(dt.date(2026, 9, 1), 4.58)],
        "China": [Ponto(dt.date(2026, 9, 1), 0.9)],
    }
    fig = figura_linhas(series, "%", mensal=True)
    assert [t.line.color for t in fig.data] == [
        CORES_ENTIDADE["Brasil"],
        CORES_ENTIDADE["China"],
    ]
    assert [a.text for a in fig.layout.annotations] == ["Brasil 4,58", "China 0,90"]
    assert len(fig.layout.yaxis.ticksuffix) == 1


def test_end_labels_are_pushed_apart():
    from brasil_painel.componentes.graficos import afastar

    assert afastar([100.0, 104.0, 50.0], 14) == [100.0, 114.0, 50.0]
