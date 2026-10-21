"""Credit and activity map by state, always against the Brazil figure.

Clicking a state sets the global UF filter, so every other screen follows it.
"""

import datetime as dt

from dash import Dash, Input, Output, dcc, html, no_update

from brasil_painel.componentes import fs
from brasil_painel.componentes.blocos import aviso, carregando
from brasil_painel.componentes.graficos import SERIE_1, figura_linhas
from brasil_painel.componentes.mapa import CONFIG_MAPA, figura_mapa
from brasil_painel.dados import formato, regional
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.dados.indicadores import Ponto
from brasil_painel.paginas.segmento import TODOS, filtros_da_tela
from brasil_painel.regional import classes as cfg
from brasil_painel.regional.ufs import BRASIL, NOMES, SIGLAS

PADRAO = "inadimplencia"
CLIENTES = [
    {"label": "PF e PJ", "value": "todos"},
    {"label": "Pessoa física", "value": "PF"},
    {"label": "Pessoa jurídica", "value": "PJ"},
]
SEGMENTOS = [
    {"label": "Todo o sistema", "value": "todos"},
    {"label": "Só cooperativas", "value": "cooperativas"},
]
OCULTO, VISIVEL = {"display": "none"}, {}
CONFIG_PAINEL = {"displayModeBar": False, "responsive": True}


def _opcoes_classe() -> list[dict]:
    opcoes = [{"label": "Todas as classes", "value": TODOS}]
    for grupo, nome in (("pf", "Pessoas"), ("pj", "Empresas")):
        opcoes += [{"label": f"{nome}: {c}", "value": c} for c in cfg.principais(grupo)]
    return opcoes


def _opcoes_produto() -> list[dict]:
    return [{"label": "Todos os produtos", "value": TODOS}] + [
        {"label": nome, "value": nome} for nome, _ in cfg.PRODUTOS
    ]


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="mapa-indicador",
                        options=[
                            {"label": i.nome, "value": k}
                            for k, i in regional.INDICADORES.items()
                        ],
                        value=PADRAO,
                        clearable=False,
                        className="fs-filtro seletor-indicador",
                    ),
                    dcc.Dropdown(
                        id="mapa-classe",
                        options=_opcoes_classe(),
                        value=TODOS,
                        clearable=False,
                        className="fs-filtro fs-filtro-classe",
                    ),  # fmt: skip
                    dcc.Dropdown(
                        id="mapa-produto",
                        options=_opcoes_produto(),
                        value=TODOS,
                        clearable=False,
                        className="fs-filtro fs-filtro-produto",
                    ),  # fmt: skip
                    dcc.RadioItems(
                        id="mapa-cliente",
                        options=CLIENTES,
                        value="todos",
                        inline=True,
                        className="filtro",
                    ),
                    dcc.RadioItems(
                        id="mapa-segmento",
                        options=SEGMENTOS,
                        value="todos",
                        inline=True,
                        className="filtro",
                    ),
                ],
                className="controles-mapa",
            ),
            html.Div(id="mapa-cabecalho", className="fs-contexto"),
            html.Div(
                [
                    html.Div(
                        carregando(
                            dcc.Graph(
                                id="mapa-grafico",
                                config=CONFIG_MAPA,
                                className="fs-mapa-grafico",
                            )
                        ),
                        className="fs-mapa-area",
                    ),
                    html.Aside(
                        [
                            carregando(html.Div(id="mapa-painel")),
                            html.Div(id="mapa-ranking", className="ranking"),
                        ],
                        className="fs-mapa-lateral",
                    ),
                ],
                className="fs-mapa-grade",
            ),
        ],
        className="fs-tela",
    )


def tabela_ranking(
    foto: regional.Retrato, indicador: regional.Indicador, uf: str | None
) -> html.Table:
    """UFs from the highest value down; Brazil and the selected state are marked."""
    linhas = []
    for posicao, (sigla, valor) in enumerate(regional.ranking(foto), start=1):
        variacao = foto.variacao_12m.get(sigla)
        classe = (
            "linha-brasil"
            if sigla == BRASIL
            else ("linha-escolhida" if sigla == uf else "")
        )
        linhas.append(
            html.Tr(
                [
                    html.Td("" if sigla == BRASIL else str(posicao)),
                    html.Td(
                        "Brasil" if sigla == BRASIL else sigla,
                        title=NOMES.get(sigla, ""),
                    ),
                    html.Td(formato.numero(valor, indicador.casas), className="num"),
                    html.Td(
                        formato.numero(variacao, indicador.casas, sinal=True)
                        if variacao is not None
                        else "sem dado",
                        className="num",
                    ),
                ],
                className=classe,
            )
        )
    cabecalho = html.Tr(
        [html.Th(""), html.Th("UF"), html.Th(indicador.unidade), html.Th("12 meses")]
    )
    return html.Table([html.Thead(cabecalho), html.Tbody(linhas)])


def _pontos(df, uf: str) -> list[Ponto]:
    linhas = df[df.uf == uf]
    return [Ponto(d, v) for d, v in zip(linhas.data, linhas.valor)]


def posicao(foto: regional.Retrato, uf: str) -> int | None:
    """Rank of a state among the 27 (1 = highest value)."""
    ordem = [s for s, _ in regional.ranking(foto) if s != BRASIL]
    return ordem.index(uf) + 1 if uf in ordem else None


def painel_estado(
    df, foto: regional.Retrato, indicador: regional.Indicador, uf: str | None
) -> html.Div:
    """Card of the selected state against Brazil, with its trend."""
    if not uf or uf not in foto.valores:
        return html.Div(
            [
                html.H3("Brasil", className="fs-painel-titulo"),
                fs.kpi(
                    indicador.nome,
                    foto.brasil,
                    unidade=indicador.unidade,
                    casas=indicador.casas,
                ),
                html.P(
                    "Clique num estado do mapa para ver os números dele aqui.",
                    className="fs-explicacao",
                ),
            ],
            className="fs-painel-estado",
        )
    valor = foto.valores[uf]
    diferenca = valor - foto.brasil if foto.brasil is not None else None
    series = {"Brasil": _pontos(df, BRASIL), NOMES[uf]: _pontos(df, uf)}
    figura = figura_linhas(series, indicador.unidade, mensal=True, cores={NOMES[uf]: SERIE_1},
                           casas=indicador.casas, referencia="Brasil")  # fmt: skip
    figura.update_layout(height=230, margin=dict(l=44, r=12, t=34, b=28), annotations=[])
    return html.Div(
        [
            html.H3(NOMES[uf], className="fs-painel-titulo"),
            fs.kpi(
                indicador.nome,
                valor,
                unidade=indicador.unidade,
                casas=indicador.casas,
                variacao=foto.variacao_12m.get(uf),
                comparacao="em 12 meses",
            ),
            html.Ul(
                [
                    html.Li(
                        f"Brasil: {formato.numero(foto.brasil, indicador.casas)} {indicador.unidade}"
                    ),
                    html.Li(
                        f"Diferença para o Brasil: {formato.numero(diferenca, indicador.casas, sinal=True)}"
                        if diferenca is not None
                        else "Diferença para o Brasil: sem dado"
                    ),
                    html.Li(f"Posição: {posicao(foto, uf)}º de {len(foto.valores)}"),
                ],
                className="fs-painel-lista",
            ),
            dcc.Graph(figure=figura, config=CONFIG_PAINEL, style={"height": "230px"}),
        ],
        className="fs-painel-estado",
    )


def _serie(chave, cliente, segmento, classe, produto, data: dt.date | None):
    filtros = regional.INDICADORES[chave].filtros
    df = regional.serie(
        chave,
        cliente if "cliente" in filtros else "todos",
        segmento if "segmento" in filtros else "todos",
        classe=(classe or None) if "classe" in filtros else None,
        produto=(produto or None) if "produto" in filtros else None,
    )
    return df[df.data <= data] if data else df


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the map page."""

    @app.callback(
        Output("mapa-cliente", "style"),
        Output("mapa-segmento", "style"),
        Output("mapa-classe", "style"),
        Output("mapa-produto", "style"),
        Input("mapa-indicador", "value"),
    )
    def mostrar_filtros(chave):
        filtros = regional.INDICADORES[chave].filtros
        return tuple(
            VISIVEL if f in filtros else OCULTO
            for f in ("cliente", "segmento", "classe", "produto")
        )

    @app.callback(
        Output("mapa-grafico", "figure"),
        Output("mapa-cabecalho", "children"),
        Output("mapa-ranking", "children"),
        Output("mapa-painel", "children"),
        Input("mapa-indicador", "value"),
        Input("mapa-cliente", "value"),
        Input("mapa-segmento", "value"),
        Input("mapa-classe", "value"),
        Input("mapa-produto", "value"),
        Input("filtros", "data"),
    )
    def desenhar(chave, cliente, segmento, classe, produto, filtros):
        indicador = regional.INDICADORES[chave]
        recorte = filtros_da_tela(filtros)
        try:
            df = _serie(chave, cliente, segmento, classe, produto, recorte["data"])
            foto = regional.retrato(df)
        except regional.DadosAusentes as error:
            return {}, aviso(str(error)), None, None
        figura = figura_mapa(
            foto.valores,
            foto.brasil,
            indicador.unidade,
            casas=indicador.casas,
            divergente=indicador.divergente,
            destaque=recorte["uf"],
            altura=640,
        )
        detalhes = [d for d in (classe, produto) if d]
        cabecalho = (
            f"{indicador.nome}{' (' + ', '.join(detalhes) + ')' if detalhes else ''}. "
            f"Dado de {formato.data(foto.data, mensal=True)}. Fonte: {indicador.fonte}. {indicador.nota}"
        )
        return (
            figura,
            cabecalho,
            tabela_ranking(foto, indicador, recorte["uf"]),
            painel_estado(df, foto, indicador, recorte["uf"]),
        )

    @app.callback(
        Output("filtro-uf", "value"),
        Input("mapa-grafico", "clickData"),
        prevent_initial_call=True,
    )
    def escolher_uf(clique):
        if not clique:
            return no_update
        return SIGLAS[int(clique["points"][0]["location"])]
