"""Internal gallery of the FinScope tokens and components (sample data only)."""

import datetime as dt

from dash import Dash, html

from brasil_painel import marca
from brasil_painel.componentes import fs
from brasil_painel.dados.api import OpenBBClient

AMOSTRAS = [
    ("Turquesa", marca.TURQUESA),
    ("Verde-escuro", marca.VERDE_ESCURO),
    ("Verde-médio", marca.VERDE_MEDIO),
    ("Roxo", marca.ROXO),
    ("Verde-claro", marca.VERDE_CLARO),
    ("Brasil (referência)", marca.BRASIL),
]


def _coluna_exemplo(titulo: str, fator: float) -> html.Section:
    return fs.coluna_classe(
        titulo,
        [
            fs.funil(
                [
                    ("Carteira", 1_000e9 * fator),
                    ("Em dia", 930e9 * fator),
                    ("Atraso 15–90", 25e9 * fator),
                    ("Inadimplente", 45e9 * fator),
                ],
                prefixo="R$ ",
            ),
            fs.barras_comparativas(
                [
                    ("Cooperativas", 70e9 * fator, "coop"),
                    ("Sistema", 1_000e9 * fator, "sistema"),
                ],
                prefixo="R$ ",
            ),
            html.Div(
                [
                    fs.kpi(
                        "Share das cooperativas",
                        7.0 * fator,
                        unidade="%",
                        variacao=0.4,
                        comparacao="em 12 meses",
                    ),
                    fs.kpi(
                        "Inadimplência",
                        4.5,
                        unidade="%",
                        variacao=-0.2,
                        comparacao="em 12 meses",
                    ),
                    fs.kpi("Crescimento 12 meses", 9.8, unidade="%"),
                    fs.kpi("Peso do cartão", 14.1, unidade="%"),
                ],
                className="fs-kpis",
            ),
        ],
        subtitulo="dados de exemplo",
    )


def layout() -> html.Div:
    """Return the gallery."""
    return html.Div(
        [
            html.H2("Galeria FinScope"),
            fs.selo_datas(dt.date(2026, 10, 20), dt.date(2026, 8, 31)),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                className="fs-amostra", style={"background": cor}
                            ),
                            nome,
                            html.Code(cor),
                        ],
                        className="fs-amostra-linha",
                    )
                    for nome, cor in AMOSTRAS
                ],
                className="fs-amostras",
            ),
            html.Div(
                [_coluna_exemplo("Varejo", 1.0), _coluna_exemplo("Alta renda", 0.6)],
                className="fs-colunas",
            ),
            html.H3("Carregando"),
            fs.esqueleto(3),
        ],
        className="fs-galeria",
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """No callbacks: static gallery."""
