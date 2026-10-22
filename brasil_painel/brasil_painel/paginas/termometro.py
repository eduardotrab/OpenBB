"""Credit thermometer by state: a transparent score with adjustable weights."""

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

from brasil_painel.componentes.blocos import aviso, carregando
from brasil_painel.componentes.graficos import figura_contribuicoes
from brasil_painel.componentes.mapa import CONFIG_MAPA, figura_mapa
from brasil_painel.dados import (
    formato,
    termometro as term,
)
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.paginas.segmento import CONFIG_MINI, filtros_da_tela
from brasil_painel.regional.ufs import BRASIL, NOMES, SIGLAS


def _controles() -> list:
    return [
        html.Div(
            [
                html.Label(c["rotulo"], className="fs-exp-rotulo"),
                dcc.Slider(id={"type": "term-peso", "chave": k}, min=0, max=40, step=5, value=c["peso"],
                           marks={0: "0", 20: "20", 40: "40"}, tooltip={"placement": "bottom"}),
            ],
            className="fs-exp-campo",
        )
        for k, c in term.configuracao().items()
    ]  # fmt: skip


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.P(
                "Nota de 0 a 100 por estado. Cada indicador vira a distância do estado à média dos 27 estados, com o "
                "sinal de melhor ou pior; a nota é 50 mais a soma ponderada. Acima de 50, o estado está melhor que a "
                "média nesse conjunto. Não é uma probabilidade: cada barra mostra quantos pontos o indicador somou ou "
                "tirou.",
                className="fs-explicacao",
            ),
            html.Details(
                [
                    html.Summary("Pesos dos indicadores"),
                    html.Div(_controles(), className="fs-exp-form"),
                    html.Button(
                        "Voltar aos pesos iniciais",
                        id="term-restaurar",
                        className="fs-botao secundario",
                    ),
                ],
                className="fs-term-pesos",
            ),
            html.Div(id="term-contexto", className="fs-contexto"),
            html.Div(
                [
                    html.Div(
                        carregando(dcc.Graph(id="term-mapa", config=CONFIG_MAPA)),
                        className="fs-mapa-area",
                    ),
                    html.Aside(
                        html.Div(id="term-ranking", className="ranking"),
                        className="fs-mapa-lateral",
                    ),
                ],
                className="fs-mapa-grade",
            ),
            carregando(html.Div(id="term-estado", className="fs-mun-perfil")),
        ],
        className="fs-tela",
    )


def _valor(v, unidade: str) -> str:
    if v is None or pd.isna(v):
        return "sem dado"
    return f"{formato.numero(v, 2, sinal=unidade == 'p.p.')} {unidade}".replace(
        " %", "%"
    )


def painel_estado(
    uf: str | None, c: pd.DataFrame, nota: pd.Series, pontos: pd.DataFrame
) -> html.Div:
    """Score of one state and the points of each indicator."""
    if not uf or uf not in nota.index:
        return html.P(
            "Clique num estado do mapa para ver de onde vem a nota dele.",
            className="fs-explicacao",
        )
    config = term.configuracao()
    rotulos = [x["curto"] for x in config.values()]
    detalhes = [
        f"{NOMES[uf]}: {_valor(c.loc[uf, k], x['unidade'])}. Brasil: {_valor(c.loc[BRASIL, k], x['unidade'])}. "
        f"Melhor quando {x['melhor']}."
        for k, x in config.items()
    ]
    posicao = list(nota.sort_values(ascending=False).index).index(uf) + 1
    return html.Div(
        [
            html.H3(NOMES[uf], className="fs-painel-titulo"),
            html.P([html.Span(formato.numero(nota[uf], 0), className="fs-term-nota"), f" de 100, {posicao}º de {len(nota)}"]),
            html.Div(
                [
                    dcc.Graph(figure=figura_contribuicoes(rotulos, list(pontos.loc[uf]), detalhes), config=CONFIG_MINI),
                    html.Ul(
                        [html.Li(f"{x['rotulo']}: {_valor(c.loc[uf, k], x['unidade'])} (Brasil: {_valor(c.loc[BRASIL, k], x['unidade'])})")
                         for k, x in config.items()],
                        className="fs-painel-lista",
                    ),
                ],
                className="fs-grade-produtos fs-meio",
            ),
        ],
        className="fs-painel-estado",
    )  # fmt: skip


def ranking(nota: pd.Series, uf: str | None) -> html.Table:
    """States from the highest score down."""
    linhas = [
        html.Tr(
            [
                html.Td(str(i)),
                html.Td(sigla, title=NOMES[sigla]),
                html.Td(formato.numero(v, 0), className="num"),
            ],
            className="linha-escolhida" if sigla == uf else "",
        )
        for i, (sigla, v) in enumerate(
            nota.sort_values(ascending=False).items(), start=1
        )
    ]
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(""), html.Th("UF"), html.Th("Nota")])),
            html.Tbody(linhas),
        ]
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(
        Output("term-mapa", "figure"),
        Output("term-contexto", "children"),
        Output("term-estado", "children"),
        Output("term-ranking", "children"),
        Input({"type": "term-peso", "chave": ALL}, "value"),
        Input("filtros", "data"),
        State({"type": "term-peso", "chave": ALL}, "id"),
    )
    def desenhar(valores, filtros, ids):
        recorte = filtros_da_tela(filtros)
        pesos = {i["chave"]: v for i, v in zip(ids, valores, strict=True)}
        if not any(pesos.values()):
            return {}, aviso("todos os pesos estão em zero"), None, None
        try:
            c, nota, pontos, fontes = term.calcular(recorte["data"], pesos or None)
        except term.DadosAusentes as error:
            return {}, aviso(str(error)), None, None
        figura = figura_mapa(nota.to_dict(), 50.0, "pontos", casas=0, divergente=True, maior_melhor=True,
                             referencia="Média dos estados", destaque=recorte["uf"], altura=600)  # fmt: skip
        contexto = (
            f"Crédito (SCR) de {formato.data(fontes['scr'], mensal=True)}, Pix de {formato.data(fontes['pix'], mensal=True)}, "
            f"desemprego do trimestre até {formato.data(fontes['desemprego'], mensal=True)}."
        )
        return (
            figura,
            contexto,
            painel_estado(recorte["uf"], c, nota, pontos),
            ranking(nota, recorte["uf"]),
        )

    @app.callback(
        Output({"type": "term-peso", "chave": ALL}, "value"),
        Input("term-restaurar", "n_clicks"),
        State({"type": "term-peso", "chave": ALL}, "id"),
        prevent_initial_call=True,
    )
    def restaurar(_, ids):
        return [term.configuracao()[i["chave"]]["peso"] for i in ids]

    @app.callback(
        Output("filtro-uf", "value", allow_duplicate=True),
        Input("term-mapa", "clickData"),
        prevent_initial_call=True,
    )
    def escolher_uf(clique):
        if not clique or not ctx.triggered_id:
            return no_update
        return SIGLAS[int(clique["points"][0]["location"])]
