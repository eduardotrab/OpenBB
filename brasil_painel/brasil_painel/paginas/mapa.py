"""Credit and activity map by state, always against the Brazil figure."""

from dash import Dash, Input, Output, dcc, html, no_update

from brasil_painel.componentes.blocos import aviso, carregando, grafico
from brasil_painel.componentes.graficos import SERIE_1, figura_linhas
from brasil_painel.componentes.mapa import CONFIG_MAPA, figura_mapa
from brasil_painel.dados import formato, regional
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.dados.indicadores import Ponto
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


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Section(
                [
                    html.H2("Mapa por estado"),
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="mapa-indicador",
                                options=[
                                    {"label": i.nome, "value": chave}
                                    for chave, i in regional.INDICADORES.items()
                                ],
                                value=PADRAO,
                                clearable=False,
                                className="seletor-indicador",
                            ),
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
                    html.Div(id="mapa-cabecalho", className="nota"),
                    html.Div(
                        [
                            carregando(
                                dcc.Graph(id="mapa-grafico", config=CONFIG_MAPA)
                            ),
                            html.Div(id="mapa-ranking", className="ranking"),
                        ],
                        className="grade-mapa",
                    ),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2(id="mapa-titulo-evolucao"),
                    html.P(
                        "Clique num estado do mapa para compará-lo com o Brasil.",
                        className="nota",
                    ),
                    carregando(html.Div(id="mapa-evolucao")),
                ],
                className="secao",
            ),
            dcc.Store(id="mapa-uf"),
        ]
    )


def tabela_ranking(foto: regional.Retrato, indicador: regional.Indicador) -> html.Table:
    """UFs from the highest value down; the Brazil row is highlighted."""
    linhas = []
    for posicao, (uf, valor) in enumerate(regional.ranking(foto), start=1):
        variacao = foto.variacao_12m.get(uf)
        linhas.append(
            html.Tr(
                [
                    html.Td("" if uf == BRASIL else str(posicao)),
                    html.Td("Brasil" if uf == BRASIL else uf, title=NOMES.get(uf, "")),
                    html.Td(formato.numero(valor, indicador.casas), className="num"),
                    html.Td(
                        formato.numero(variacao, indicador.casas, sinal=True)
                        if variacao is not None
                        else "sem dado",
                        className="num",
                    ),
                ],
                className="linha-brasil" if uf == BRASIL else "",
            )
        )
    cabecalho = html.Tr(
        [html.Th(""), html.Th("UF"), html.Th(indicador.unidade), html.Th("12 meses")]
    )
    return html.Table([html.Thead(cabecalho), html.Tbody(linhas)])


def _pontos(df, uf: str) -> list[Ponto]:
    linhas = df[df.uf == uf]
    return [Ponto(d, v) for d, v in zip(linhas.data, linhas.valor)]


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the map page."""

    @app.callback(
        Output("mapa-cliente", "style"),
        Output("mapa-segmento", "style"),
        Input("mapa-indicador", "value"),
    )
    def mostrar_filtros(chave):
        filtros = regional.INDICADORES[chave].filtros
        return (
            VISIVEL if "cliente" in filtros else OCULTO,
            VISIVEL if "segmento" in filtros else OCULTO,
        )

    @app.callback(
        Output("mapa-grafico", "figure"),
        Output("mapa-cabecalho", "children"),
        Output("mapa-ranking", "children"),
        Input("mapa-indicador", "value"),
        Input("mapa-cliente", "value"),
        Input("mapa-segmento", "value"),
    )
    def desenhar_mapa(chave, cliente, segmento):
        indicador = regional.INDICADORES[chave]
        try:
            foto = regional.retrato(regional.serie(chave, cliente, segmento))
        except regional.DadosAusentes as error:
            return {}, aviso(str(error)), None
        figura = figura_mapa(
            foto.valores,
            foto.brasil,
            indicador.unidade,
            casas=indicador.casas,
            divergente=indicador.divergente,
        )
        brasil = (
            f"Brasil: {formato.numero(foto.brasil, indicador.casas)} {indicador.unidade}"
            if foto.brasil is not None
            else ""
        )
        cabecalho = [
            html.Strong(f"Dado de {formato.data(foto.data, mensal=True)}"),
            f". {brasil}. Fonte: {indicador.fonte}.",
            html.Br(),
            indicador.nota,
        ]
        return figura, cabecalho, tabela_ranking(foto, indicador)

    @app.callback(Output("mapa-uf", "data"), Input("mapa-grafico", "clickData"))
    def escolher_uf(clique):
        if not clique:
            return no_update
        return SIGLAS[int(clique["points"][0]["location"])]

    @app.callback(
        Output("mapa-titulo-evolucao", "children"),
        Output("mapa-evolucao", "children"),
        Input("mapa-indicador", "value"),
        Input("mapa-cliente", "value"),
        Input("mapa-segmento", "value"),
        Input("mapa-uf", "data"),
    )
    def evolucao(chave, cliente, segmento, uf):
        indicador = regional.INDICADORES[chave]
        titulo = f"{indicador.nome}: {NOMES[uf] if uf else 'Brasil'} ao longo do tempo"
        try:
            df = regional.serie(chave, cliente, segmento)
        except regional.DadosAusentes as error:
            return titulo, aviso(str(error))
        series = {"Brasil": _pontos(df, BRASIL)}
        cores = {}
        if uf:
            series[NOMES[uf]] = _pontos(df, uf)
            cores[NOMES[uf]] = SERIE_1
        figura = figura_linhas(
            series,
            indicador.unidade,
            mensal=True,
            cores=cores,
            casas=indicador.casas,
            referencia="Brasil",
        )
        return titulo, grafico(figura)
