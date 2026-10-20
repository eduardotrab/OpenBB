"""World page data: unit handling, FX, step series and the 12-month index."""

import datetime as dt

import pytest

from brasil_painel.dados import mundo
from brasil_painel.dados.api import FonteIndisponivel
from brasil_painel.dados.indicadores import Ponto

HOJE = dt.date(2026, 10, 20)


class FakeClient:
    """Answer by route (and `symbol`/`country` when given)."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    def get(self, path, **params):
        self.chamadas.append((path, params))
        for chave in (
            (path, params.get("symbol")),
            (path, params.get("country")),
            (path, None),
        ):
            if chave in self.respostas:
                return self.respostas[chave]
        raise FonteIndisponivel(path)


def test_commodity_rows_keep_only_dollar_prices():
    rows = [
        {
            "date": "2026-09-30",
            "symbol": "PCPS::PSOYB",
            "unit": "Unit prices - Index",
            "value": 132.8,
        },
        {
            "date": "2026-09-30",
            "symbol": "PCPS::PSOYB",
            "unit": "percent change",
            "value": 7.3,
        },
        {
            "date": "2026-09-30",
            "symbol": "PCPS::PSOYB",
            "unit": "Unit prices - US dollars",
            "value": 481.7,
        },
        {
            "date": "2026-08-31",
            "symbol": "PCPS::PSOYB",
            "unit": "Unit prices - US dollars",
            "value": 449.0,
        },
        {
            "date": "2026-09-30",
            "symbol": "PCPS::PMAIZMT",
            "unit": "Unit prices - US dollars",
            "value": 236.9,
        },
    ]
    series = mundo.precos_commodities(rows)
    assert series["PCPS::PSOYB"] == [
        Ponto(dt.date(2026, 8, 31), 449.0),
        Ponto(dt.date(2026, 9, 30), 481.7),
    ]
    assert list(series) == ["PCPS::PSOYB", "PCPS::PMAIZMT"]


def test_by_country_scales_fractions_to_percent():
    rows = [
        {"date": "2026-09-01", "country": "United States", "value": 0.0374},
        {
            "date": "2026-09-01",
            "country": "China (People’s Republic of)",
            "value": 0.009,
        },
        {"date": "2026-08-01", "country": "United States", "value": 0.034},
    ]
    series = mundo.por_pais(rows, escala=100)
    assert [p.valor for p in series["United States"]] == pytest.approx([3.4, 3.74])
    assert series["China (People’s Republic of)"][0].valor == pytest.approx(0.9)


def test_step_series_is_extended_to_today():
    mudancas = [Ponto(dt.date(2025, 6, 11), 2.0), Ponto(dt.date(2026, 9, 16), 2.5)]
    assert mundo.degraus(mudancas, HOJE)[-1] == Ponto(HOJE, 2.5)
    assert mundo.degraus([Ponto(HOJE, 2.5)], HOJE) == [Ponto(HOJE, 2.5)]


def test_monthly_points_are_dated_on_day_one():
    assert mundo.inicio_do_mes([Ponto(dt.date(2026, 9, 30), 3.7)]) == [
        Ponto(dt.date(2026, 9, 1), 3.7)
    ]


def test_clip_starts_with_the_rate_in_force():
    mudancas = [
        Ponto(dt.date(1999, 1, 1), 2.0),
        Ponto(dt.date(2025, 6, 11), 2.0),
        Ponto(dt.date(2026, 9, 16), 2.5),
    ]
    inicio = dt.date(2024, 10, 20)
    assert mundo.recortar(mudancas, inicio) == [
        Ponto(inicio, 2.0),
        Ponto(dt.date(2025, 6, 11), 2.0),
        Ponto(dt.date(2026, 9, 16), 2.5),
    ]


def test_index_base_100_twelve_months_before_last_point():
    pontos = [
        Ponto(dt.date(2025, 8, 31), 380.0),
        Ponto(dt.date(2025, 9, 30), 400.0),
        Ponto(dt.date(2026, 3, 31), 440.0),
        Ponto(dt.date(2026, 9, 30), 480.0),
    ]
    indice = mundo.indice_base_100(pontos)
    assert indice[0] == Ponto(dt.date(2025, 9, 30), 100.0)
    assert indice[-1].valor == 120.0
    assert mundo.indice_base_100([]) == []


def _respostas():
    return {
        ("fixedincome/rate/effr", None): [
            {"date": "2025-10-16", "rate": 0.0433},
            {"date": "2026-10-16", "rate": 0.0388},
        ],
        ("fixedincome/government/treasury_rates", None): [
            {"date": "2026-09-16", "year_10": 0.0480},
            {"date": "2026-10-16", "year_10": 0.0509},
        ],
        ("economy/indicators", "FM::B.U2.EUR.4F.KR.DFR.LEV"): [
            {"date": "1999-01-01", "value": 2.0},
            {"date": "2025-06-11", "value": 2.0},
            {"date": "2026-09-16", "value": 2.5},
        ],
        ("currency/price/historical", "EURUSD"): [
            {"date": "2026-09-18", "close": 1.10},
            {"date": "2026-10-19", "close": 1.1225},
        ],
    }


def test_cards_group_by_block_and_isolate_failures():
    blocos = mundo.cartoes(FakeClient(_respostas()), HOJE)
    assert list(blocos) == [
        "mundo-eua",
        "mundo-europa",
        "mundo-china",
        "mundo-cambio",
        "mundo-commodities",
    ]
    eua = {c.nome: c for c in blocos["mundo-eua"]}
    assert round(eua["Fed funds (efetiva)"].valor, 2) == 3.88
    assert round(eua["Fed funds (efetiva)"].variacao, 2) == -0.45
    assert round(eua["Treasury 10 anos"].variacao, 2) == 0.29
    assert eua["Inflação 12 meses"].erro
    bce = blocos["mundo-europa"][0]
    assert (bce.valor, bce.variacao, bce.data_ref) == (2.5, 0.5, HOJE)
    eurusd = blocos["mundo-cambio"][0]
    assert eurusd.casas == 4 and round(eurusd.variacao, 2) == 2.05
    assert eurusd.percentual


def test_charts_report_missing_series():
    respostas = _respostas() | {
        ("bcb/sgs", "432"): [{"date": "2026-10-20", "value": 13.75}],
    }
    series, falhas = mundo.juros(FakeClient(respostas), HOJE)
    assert list(series) == ["Fed funds", "BCE (depósito)", "Selic meta"]
    assert series["BCE (depósito)"][-1] == Ponto(HOJE, 2.5)
    assert series["BCE (depósito)"][0] == Ponto(dt.date(2024, 10, 20), 2.0)
    series, falhas = mundo.inflacao(FakeClient(respostas), HOJE)
    assert series == {}
    assert falhas == ["EUA", "China", "Zona do euro", "Brasil"]


def test_gdp_cards_use_the_imf_projection_for_this_year():
    respostas = {
        ("economy/indicators", "WEO::NGDP_RPCH"): [
            {
                "date": "2025-12-31",
                "country": "China, People's Republic of",
                "unit": "Percent",
                "value": 5.0,
            },
            {
                "date": "2026-12-31",
                "country": "China, People's Republic of",
                "unit": "Percent",
                "value": 4.47,
            },
            {
                "date": "2026-12-31",
                "country": "United States",
                "unit": "Percent",
                "value": 2.33,
            },
        ],
        ("economy/indicators", "LS::U"): [
            {"date": "2025-08-31", "symbol": "LS::U", "unit": "Percent", "value": 4.3},
            {
                "date": "2026-08-31",
                "symbol": "LS::U",
                "unit": "Percent change",
                "value": -4.6,
            },
            {"date": "2026-08-31", "symbol": "LS::U", "unit": "Percent", "value": 4.1},
        ],
    }
    blocos = mundo.cartoes(FakeClient(respostas), HOJE)
    china = {c.nome: c for c in blocos["mundo-china"]}["PIB 2026 (projeção)"]
    assert (china.valor, china.anual, china.comparacao) == (4.47, True, "vs. 2025")
    assert round(china.variacao, 2) == -0.53
    eua = {c.nome: c for c in blocos["mundo-eua"]}
    assert eua["Desemprego"].valor == 4.1
    assert round(eua["Desemprego"].variacao, 2) == -0.2
    assert eua["PIB 2026 (projeção)"].tendencia is None
