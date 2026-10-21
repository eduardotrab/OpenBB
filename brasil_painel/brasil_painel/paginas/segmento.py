"""Segment screens of credit classes (Individuals by income, Companies by size).

One column per class, side by side, as in the segmentation models; values are
public market data (cooperatives × the whole system), never member data.
"""

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
from brasil_painel.regional import classes as cfg
from brasil_painel.regional.ufs import BRASIL, NOMES

TODOS = ""
CONFIG_MINI = {"displayModeBar": False, "responsive": True}


def filtros_da_tela(filtros: dict | None) -> dict:
    """Global Store values → keyword filters of the data layer."""
    filtros = filtros or {}
    uf = filtros.get("uf")
    data = filtros.get("data")
    return {
        "uf": None if not uf or uf == BRASIL else uf,
        "data": dt.date.fromisoformat(data) if data else None,
    }


_variacao_12m = dados_classes.variacao_12m


def coluna(resumo: dados_classes.ResumoClasse) -> html.Section:
    """One class column: funnel, cooperatives × system, KPIs and trend."""
    subtitulo = cfg.descricao(resumo.classe)
    if not resumo.carteira:
        return fs.coluna_classe(
            resumo.classe,
            [html.P("Sem carteira com estes filtros.", className="fs-vazio")],
            subtitulo,
        )
    return fs.coluna_classe(
        resumo.classe,
        [
            fs.funil(resumo.funil, prefixo="R$ "),
            fs.barras_comparativas(
                [
                    ("Cooperativas", resumo.carteira_coop, "coop"),
                    ("Sistema", resumo.carteira, "sistema"),
                ],
                prefixo="R$ ",
            ),
            html.Div(
                [
                    fs.kpi("Share das cooperativas", resumo.share_coop, unidade="%"),
                    fs.kpi(
                        "Inadimplência",
                        resumo.inadimplencia,
                        unidade="%",
                        casas=2,
                        variacao=_variacao_12m(resumo.tendencia),
                        comparacao="p.p. em 12 meses",
                        nota=(
                            f"cooperativas: {formato.numero(resumo.inadimplencia_coop, 2)}%"
                            if resumo.inadimplencia_coop is not None
                            else ""
                        ),
                    ),
                    fs.kpi("Crescimento 12 meses", resumo.crescimento_12m, unidade="%"),
                    fs.kpi("Peso do cartão", resumo.peso_cartao, unidade="%"),
                ],
                className="fs-kpis",
            ),
            html.Div(
                [
                    html.P("Inadimplência no tempo", className="fs-mini-titulo"),
                    dcc.Graph(
                        figure=figura_tendencia(resumo.tendencia),
                        config=CONFIG_MINI,
                        style={"height": "170px"},
                    ),
                ]
            ),
        ],
        subtitulo,
    )


class Segmento:
    """Page factory for one credit group (`pf` or `pj`)."""

    def __init__(self, grupo: str, prefixo: str, explicacao: str):
        self.grupo, self.prefixo, self.explicacao = grupo, prefixo, explicacao

    def layout(self) -> html.Div:
        """Return the page body."""
        produtos = (
            [{"label": "Todos os produtos", "value": TODOS}]
            + [{"label": nome, "value": nome} for nome, _ in cfg.PRODUTOS]
            + [{"label": cfg.OUTROS, "value": cfg.OUTROS}]
        )
        return html.Div(
            [
                html.Div(
                    [
                        dcc.Dropdown(
                            id=f"{self.prefixo}-produto",
                            options=produtos,
                            value=TODOS,
                            clearable=False,
                            className="fs-filtro fs-filtro-produto",
                        ),
                        html.P(self.explicacao, className="fs-explicacao"),
                    ],
                    className="fs-barra-tela",
                ),
                html.Div(id=f"{self.prefixo}-contexto", className="fs-contexto"),
                carregando(
                    html.Div(id=f"{self.prefixo}-colunas", className="fs-colunas")
                ),
                html.Div(id=f"{self.prefixo}-resto", className="fs-resto"),
            ],
            className="fs-tela",
        )

    def register(self, app: Dash, client: OpenBBClient) -> None:
        """Callbacks of the page."""

        @app.callback(
            Output(f"{self.prefixo}-colunas", "children"),
            Output(f"{self.prefixo}-contexto", "children"),
            Output(f"{self.prefixo}-resto", "children"),
            Input(f"{self.prefixo}-produto", "value"),
            Input("filtros", "data"),
        )
        def preencher(produto, filtros):
            kwargs = filtros_da_tela(filtros)
            try:
                resumos = dados_classes.todas(
                    self.grupo, produto=produto or None, **kwargs
                )
            except dados_classes.DadosAusentes as error:
                return aviso(str(error)), None, None
            por_classe = {r.classe: r for r in resumos}
            colunas = [coluna(por_classe[c]) for c in cfg.principais(self.grupo)]
            data = next((r.data for r in resumos if r.data), None)
            lugar = NOMES.get(kwargs["uf"], "Brasil") if kwargs["uf"] else "Brasil"
            contexto = (
                f"{lugar}, {produto or 'todos os produtos'}. Carteira de "
                f"{formato.data(data, mensal=True) if data else 'mês sem dado'} (estoque, SCR.data)."
            )
            resto = [
                html.P(
                    f"{r.classe}: R$ {formato.compacto(r.carteira)} de carteira, sem faixa/porte informado.",
                    className="fs-nota-resto",
                )
                for r in resumos
                if r.classe not in cfg.principais(self.grupo) and r.carteira
            ]
            return colunas, contexto, resto


PESSOAS = Segmento(
    "pf",
    "pessoas",
    "Pessoas físicas por faixa de renda declarada à instituição (salários mínimos).",
)
EMPRESAS = Segmento(
    "pj",
    "empresas",
    "Empresas por porte; o MEI vem das pessoas físicas com ocupação MEI.",
)
