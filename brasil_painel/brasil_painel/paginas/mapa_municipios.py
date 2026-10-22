"""Municipalities of the chosen state, below the state map (against the state median)."""

import pandas as pd
from dash import Dash, Input, Output, State, dcc, html, no_update

from brasil_painel.componentes.blocos import aviso, carregando
from brasil_painel.componentes.mapa import CONFIG_MAPA, figura_mapa_municipios
from brasil_painel.dados import (
    formato,
    municipios as mun,
)
from brasil_painel.paginas.segmento import filtros_da_tela
from brasil_painel.regional.ufs import NOMES

PADRAO = "pix_pj_pc"
RANKING = 15
OCULTO, VISIVEL = {"display": "none"}, {}
FONTES = {"pix": "Pix", "estban": "ESTBAN", "sicor": "SICOR", "pib": "PIB"}


def bloco() -> html.Section:
    """Section appended to the map page."""
    return html.Section(
        [
            html.H2("Municípios", id="mun-titulo"),
            html.P(
                "Escolha um estado no filtro do topo ou clique nele no mapa para ver os municípios.",
                id="mun-vazio",
                className="fs-explicacao",
            ),
            html.Div(
                [
                    html.Div(
                        dcc.Dropdown(
                            id="mun-indicador",
                            value=PADRAO,
                            clearable=False,
                            className="fs-filtro seletor-indicador",
                            options=[
                                {"label": i.nome, "value": k}
                                for k, i in mun.INDICADORES.items()
                            ],
                        ),  # fmt: skip
                        className="fs-barra-tela",
                    ),
                    html.Div(id="mun-contexto", className="fs-contexto"),
                    html.Div(
                        [
                            html.Div(
                                carregando(
                                    dcc.Graph(id="mun-grafico", config=CONFIG_MAPA)
                                ),
                                className="fs-mapa-area",
                            ),
                            html.Aside(
                                [html.Div(id="mun-ranking", className="ranking")],
                                className="fs-mapa-lateral",
                            ),
                        ],
                        className="fs-mapa-grade",
                    ),
                    carregando(html.Div(id="mun-painel", className="fs-mun-perfil")),
                ],
                id="mun-conteudo",
                style=OCULTO,
            ),
            dcc.Store(id="mun-escolhido"),
        ],
        className="secao",
    )


def _valor(v, ind: mun.Indicador) -> str:
    return (
        "sem dado"
        if v is None or pd.isna(v)
        else f"{formato.numero(v, ind.casas)} {ind.unidade}"
    )


def _habitantes(v) -> str:
    return "" if pd.isna(v) else formato.compacto(v)


def ranking(t: pd.DataFrame, chave: str, escolhido: str | None) -> html.Table:
    """Municipalities from the highest value down (the first 15)."""
    ind = mun.INDICADORES[chave]
    serie = t[chave].dropna().sort_values(ascending=False).head(RANKING)
    linhas = [
        html.Tr(
            [
                html.Td(str(i)),
                html.Td(t.loc[c, "nome"]),
                html.Td(formato.numero(v, ind.casas), className="num"),
                html.Td(_habitantes(t.loc[c, "populacao"]), className="num"),
            ],
            className="linha-escolhida" if c == escolhido else "",
        )
        for i, (c, v) in enumerate(serie.items(), start=1)
    ]
    cabecalho = html.Tr(
        [html.Th(""), html.Th("Município"), html.Th(ind.unidade), html.Th("Habitantes")]
    )
    return html.Table([html.Thead(cabecalho), html.Tbody(linhas)])


def painel(t: pd.DataFrame, municipio: str | None) -> html.Div:
    """Every indicator of one municipality against the state median, with its rank."""
    if not municipio or municipio not in t.index:
        return html.P(
            "Clique num município para ver o perfil dele aqui.",
            className="fs-explicacao",
        )
    linhas = []
    for chave, ind in mun.INDICADORES.items():
        lugar = mun.posicao(t, chave, municipio)
        linhas.append(
            html.Tr(
                [
                    html.Th(ind.nome, scope="row"),
                    html.Td(_valor(t.loc[municipio, chave], ind), className="num"),
                    html.Td(_valor(mun.mediana(t, chave), ind), className="num"),
                    html.Td(
                        f"{lugar[0]}º de {lugar[1]}" if lugar else "", className="num"
                    ),
                ]
            )
        )
    cabecalho = html.Tr(
        [
            html.Th(""),
            html.Th("Município"),
            html.Th("Mediana do estado"),
            html.Th("Posição"),
        ]
    )
    return html.Div(
        [
            html.H3(t.loc[municipio, "nome"], className="fs-painel-titulo"),
            html.Table(
                [html.Thead(cabecalho), html.Tbody(linhas)],
                className="fs-matriz fs-matriz-perfil",
            ),
        ],
        className="fs-painel-estado",
    )


def register(app: Dash) -> None:
    """Callbacks of the municipal block."""

    @app.callback(
        Output("mun-titulo", "children"),
        Output("mun-vazio", "style"),
        Output("mun-conteudo", "style"),
        Output("mun-grafico", "figure"),
        Output("mun-contexto", "children"),
        Output("mun-ranking", "children"),
        Output("mun-painel", "children"),
        Input("mun-indicador", "value"),
        Input("filtros", "data"),
        Input("mun-escolhido", "data"),
    )
    def desenhar(chave, filtros, escolhido):
        recorte = filtros_da_tela(filtros)
        uf = recorte["uf"]
        if not uf:
            return "Municípios", VISIVEL, OCULTO, {}, None, None, None
        titulo = f"Municípios de {NOMES[uf]}"
        try:
            t, datas = mun.tabela(uf, recorte["data"])
        except mun.DadosAusentes as error:
            return titulo, OCULTO, VISIVEL, {}, aviso(str(error)), None, None
        ind = mun.INDICADORES[chave]
        escolhido = escolhido if escolhido in t.index else None
        referencia = mun.mediana(t, chave)
        valores = t[chave].dropna().to_dict()
        figura = figura_mapa_municipios(uf, valores, t.nome.to_dict(), referencia, ind.unidade, casas=ind.casas,
                                        crescimento=ind.divergente, destaque=escolhido)  # fmt: skip
        referencias = ", ".join(
            f"{nome} de {datas[k].year if k == 'pib' else formato.data(datas[k], mensal=True)}"
            for k, nome in FONTES.items()
            if k in datas
        )
        contexto = (
            f"{ind.nome}. Mediana do estado: {_valor(referencia, ind)}. {len(valores)} de {len(t)} municípios com dado. "
            f"Fonte: {ind.fonte}. {ind.nota} Dados: {referencias}."
        )
        return (
            titulo,
            OCULTO,
            VISIVEL,
            figura,
            contexto,
            ranking(t, chave, escolhido),
            painel(t, escolhido),
        )

    @app.callback(
        Output("mun-escolhido", "data"),
        Input("mun-grafico", "clickData"),
        State("mun-escolhido", "data"),
        prevent_initial_call=True,
    )
    def escolher(clique, atual):
        if not clique:
            return no_update
        codigo = clique["points"][0]["location"]
        return None if codigo == atual else codigo
