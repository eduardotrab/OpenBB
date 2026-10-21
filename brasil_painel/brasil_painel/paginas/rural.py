"""Rural screen: credit contracted by small, medium and large producers (SICOR)."""

import datetime as dt

from dash import Dash, Input, Output, dcc, html

from brasil_painel.componentes import fs
from brasil_painel.componentes.blocos import aviso, carregando
from brasil_painel.componentes.graficos import figura_tendencia
from brasil_painel.dados import (
    classes as dados_classes,
    formato,
)
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.paginas.segmento import CONFIG_MINI, filtros_da_tela
from brasil_painel.regional import classes as cfg
from brasil_painel.regional.ufs import NOMES


def mes_sicor(data: dt.date | None) -> dt.date | None:
    """SICOR months are dated on day 1; the global filter uses the month end."""
    return data.replace(day=1) if data else None


def coluna(r: dados_classes.ResumoRural) -> html.Section:
    """One producer column: lenders, purposes, KPIs and the monthly trend."""
    subtitulo = cfg.descricao(r.classe)
    if not r.valor:
        return fs.coluna_classe(
            r.classe,
            [html.P("Sem contratos com estes filtros.", className="fs-vazio")],
            subtitulo,
        )
    tendencia = [(d, total / 1e9, coop / 1e9) for d, total, coop in r.tendencia]
    return fs.coluna_classe(
        r.classe,
        [
            fs.barras_comparativas(
                [
                    ("Sicoob", r.valor_sicoob, "coop"),
                    ("Cooperativas", r.valor_coop, "medio"),
                    ("Sistema", r.valor, "sistema"),
                ],
                prefixo="R$ ",
            ),
            html.Div(
                [
                    fs.kpi("Share das cooperativas", r.share_coop, unidade="%"),
                    fs.kpi("Share do Sicoob", r.share_sicoob, unidade="%"),
                    fs.kpi("Contratos", r.contratos, casas=0),
                    fs.kpi(
                        "Ticket médio",
                        r.ticket_medio / 1000 if r.ticket_medio else None,
                        unidade="mil R$",
                        casas=0,
                    ),
                ],
                className="fs-kpis",
            ),
            html.Div(
                [
                    html.P("Por finalidade", className="fs-mini-titulo"),
                    fs.barras_comparativas(
                        [
                            (nome, valor, "sistema")
                            for nome, valor in r.finalidades
                            if valor
                        ],
                        prefixo="R$ ",
                    ),
                ]
            ),
            fs.kpi(
                "Contra o mesmo mês do ano anterior",
                r.crescimento_12m,
                unidade="%",
            ),
            html.Div(
                [
                    html.P("Contratado por mês (R$ bi)", className="fs-mini-titulo"),
                    dcc.Graph(
                        figure=figura_tendencia(tendencia, unidade="bi"),
                        config=CONFIG_MINI,
                        style={"height": "170px"},
                    ),
                ]
            ),
        ],
        subtitulo,
    )


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(
                html.P(
                    "Crédito rural contratado no mês (fluxo do SICOR), por porte do produtor. "
                    "Diferente das telas Pessoas e Empresas, que mostram a carteira (estoque).",
                    className="fs-explicacao",
                ),
                className="fs-barra-tela",
            ),
            html.Div(id="rural-contexto", className="fs-contexto"),
            carregando(html.Div(id="rural-colunas", className="fs-colunas")),
        ],
        className="fs-tela",
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(
        Output("rural-colunas", "children"),
        Output("rural-contexto", "children"),
        Input("filtros", "data"),
    )
    def preencher(filtros):
        kwargs = filtros_da_tela(filtros)
        kwargs["data"] = mes_sicor(kwargs["data"])
        try:
            resumos = dados_classes.todas_rurais(**kwargs)
        except dados_classes.DadosAusentes as error:
            return aviso(str(error)), None
        data = next((r.data for r in resumos if r.data), None)
        lugar = NOMES.get(kwargs["uf"], "Brasil") if kwargs["uf"] else "Brasil"
        mes = formato.data(data, mensal=True) if data else "mês sem dado"
        return [
            coluna(r) for r in resumos
        ], f"{lugar}. Contratado em {mes} (SICOR, BCB)."
