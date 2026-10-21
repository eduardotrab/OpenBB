"""Opportunities: where cooperatives have room to grow and where arrears are rising."""

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

from brasil_painel import marca
from brasil_painel.componentes import fs
from brasil_painel.componentes.blocos import aviso, carregando, grafico
from brasil_painel.componentes.graficos import figura_espaco, figura_linhas
from brasil_painel.dados import (
    classes as dados_classes,
    formato,
    oportunidades as op,
)
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.dados.indicadores import Ponto
from brasil_painel.paginas.segmento import CONFIG_MINI, filtros_da_tela
from brasil_painel.regional.ufs import NOMES

LINHAS = 15
SEP = "|"
DETALHE_PADRAO = "uf_classe_produto"
OPCOES_DETALHE = [
    {"label": "Estado", "value": "uf"},
    {"label": "Estado e classe", "value": "uf_classe"},
    {"label": "Estado e produto", "value": "uf_produto"},
    {"label": "Estado, classe e produto", "value": "uf_classe_produto"},
]
OPCOES_GRUPO = [
    {"label": "Pessoas e empresas", "value": "todos"},
    {"label": "Pessoas", "value": "pf"},
    {"label": "Empresas", "value": "pj"},
]
OPCOES_SINAL = [
    {"label": "Carteira das cooperativas", "value": "cooperativas"},
    {"label": "Mercado todo", "value": "mercado"},
]
CORES = {"Cooperativas": marca.COOPERATIVAS, "Sistema": marca.SISTEMA}


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="op-detalhe",
                        options=OPCOES_DETALHE,
                        value=DETALHE_PADRAO,
                        clearable=False,
                        className="fs-filtro fs-filtro-classe",
                    ),  # fmt: skip
                    dcc.Dropdown(
                        id="op-grupo",
                        options=OPCOES_GRUPO,
                        value="todos",
                        clearable=False,
                        className="fs-filtro",
                    ),  # fmt: skip
                ],
                className="fs-barra-tela",
            ),
            html.Div(id="op-contexto", className="fs-contexto"),
            html.Section(
                [
                    html.H2("Espaço para crescer"),
                    html.P(
                        "Nichos em que o crédito cresceu em 12 meses, a inadimplência está abaixo da do Brasil no "
                        "mesmo recorte e as cooperativas têm participação menor que no país. O espaço é quanto a "
                        "carteira delas cresceria com a participação que têm no Brasil.",
                        className="fs-explicacao",
                    ),
                    carregando(html.Div(id="op-espaco")),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2("Alertas de piora"),
                    html.Div(
                        [
                            dcc.RadioItems(
                                id="op-sinal",
                                options=OPCOES_SINAL,
                                value="cooperativas",
                                inline=True,
                                className="fs-radio",
                            ),  # fmt: skip
                        ],
                        className="fs-barra-tela",
                    ),
                    html.P(
                        "Nichos em que o atraso de 15 a 90 dias subiu nos últimos 3 meses. Esse atraso vem antes da "
                        "inadimplência: onde ele mais subiu, a inadimplência subiu mais no trimestre seguinte. "
                        "A lista começa pelo valor que entrou em atraso além do nível de 3 meses antes.",
                        className="fs-explicacao",
                    ),
                    carregando(html.Div(id="op-alertas")),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2(id="op-nicho-titulo"),
                    carregando(html.Div(id="op-nicho-graficos")),
                ],
                className="secao",
            ),
            dcc.Store(id="op-nicho"),
        ],
        className="fs-tela",
    )


def rotulo(linha, chaves: tuple[str, ...]) -> str:
    """Readable niche name: state name, then class and product."""
    partes = [NOMES.get(linha["uf"], linha["uf"])] + [
        linha[c] for c in chaves if c != "uf"
    ]
    return ", ".join(partes)


def _pct(v, casas: int = 1) -> str:
    return "sem dado" if v is None or pd.isna(v) else f"{formato.numero(v, casas)}%"


def _linha(lista: str, linha, chaves: tuple[str, ...], celulas: list) -> html.Tr:
    chave = SEP.join(str(linha[c]) for c in chaves)
    return html.Tr(
        [html.Th(rotulo(linha, chaves), scope="row"), *celulas],
        id={"type": "op-linha", "lista": lista, "chave": chave},
        className="fs-linha-clicavel",
        title="Ver este nicho no tempo",
    )


def tabela_espaco(e: pd.DataFrame, chaves: tuple[str, ...]) -> html.Table:
    """Room-to-grow table: market and the cooperatives' share, here and in Brazil."""
    cabecalho = html.Tr([html.Th(t) for t in ("Nicho", "Carteira", "Crescimento em 12 meses", "Inadimplência",
                                               "No Brasil", "Share das cooperativas",
                                               "No Brasil", "Espaço")])  # fmt: skip
    corpo = [
        _linha(
            "espaco",
            linha,
            chaves,
            [
                html.Td(f"R$ {formato.compacto(linha['carteira'])}", className="num"),
                html.Td(_pct(linha["cresc_12m"]), className="num"),
                html.Td(_pct(linha["inad"], 2), className="num"),
                html.Td(_pct(linha["inad_ref"], 2), className="num"),
                html.Td(_pct(linha["share"]), className="num"),
                html.Td(_pct(linha["share_ref"]), className="num"),
                html.Td(
                    f"R$ {formato.compacto(linha['espaco'])}",
                    className="num fs-destaque",
                ),
            ],
        )  # fmt: skip
        for _, linha in e.head(LINHAS).iterrows()
    ]
    return html.Table(
        [html.Thead(cabecalho), html.Tbody(corpo)],
        className="fs-matriz fs-matriz-nichos",
    )


def tabela_alertas(a: pd.DataFrame, chaves: tuple[str, ...], sinal: str) -> html.Table:
    """Alert table: arrears 3 months ago and now, the rise and what it means in R$."""
    coop = sinal == "cooperativas"
    sufixo = "_coop" if coop else ""
    cabecalho = html.Tr([html.Th(t) for t in ("Nicho", "Carteira das cooperativas" if coop else "Carteira",
                                               "Atraso há 3 meses", "Atraso hoje", "Alta",
                                               "Valor a mais em atraso", "Inadimplência hoje")])  # fmt: skip
    corpo = [
        _linha(
            "alerta",
            linha,
            chaves,
            [
                html.Td(
                    f"R$ {formato.compacto(linha['carteira' + sufixo])}",
                    className="num",
                ),
                html.Td(_pct(linha[f"atraso{sufixo}_3m"], 2), className="num"),
                html.Td(_pct(linha["atraso" + sufixo], 2), className="num"),
                html.Td(
                    f"+{formato.numero(linha['delta'], 2)} p.p.",
                    className="num fs-destaque",
                ),
                html.Td(f"R$ {formato.compacto(linha['impacto'])}", className="num"),
                html.Td(_pct(linha["inad" + sufixo], 2), className="num"),
            ],
        )  # fmt: skip
        for _, linha in a.head(LINHAS).iterrows()
    ]
    return html.Table(
        [html.Thead(cabecalho), html.Tbody(corpo)],
        className="fs-matriz fs-matriz-nichos",
    )


def _base(grupo: str) -> pd.DataFrame:
    return op.base(None if grupo == "todos" else grupo)


def _pontos(s: pd.DataFrame, coluna: str) -> list[Ponto]:
    return [Ponto(d, v) for d, v in zip(s.data, s[coluna], strict=True) if pd.notna(v)]


def graficos_nicho(s: pd.DataFrame) -> html.Div:
    """Arrears and default of one niche, cooperatives against the whole system."""
    blocos = []
    for titulo, coluna in (
        ("Atraso de 15 a 90 dias", "atraso"),
        ("Inadimplência", "inad"),
    ):
        series = {
            "Sistema": _pontos(s, coluna),
            "Cooperativas": _pontos(s, coluna + "_coop"),
        }
        series = {nome: pontos for nome, pontos in series.items() if pontos}
        if not series:
            continue
        blocos.append(html.Div([html.P(titulo, className="fs-mini-titulo"),
                                dcc.Graph(figure=figura_linhas(series, "%", mensal=True, cores=CORES), config=CONFIG_MINI)],  # fmt: skip
                               className="fs-cartao-grafico"))  # fmt: skip
    return (
        html.Div(blocos, className="fs-grade-produtos fs-meio")
        if blocos
        else aviso("sem série para este nicho")
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(
        Output("op-espaco", "children"),
        Output("op-alertas", "children"),
        Output("op-contexto", "children"),
        Output("op-nicho", "data"),
        Input("op-detalhe", "value"),
        Input("op-grupo", "value"),
        Input("op-sinal", "value"),
        Input("filtros", "data"),
    )
    def listas(detalhe, grupo, sinal, filtros):
        recorte = filtros_da_tela(filtros)
        chaves = op.DETALHES.get(detalhe, op.DETALHES[DETALHE_PADRAO])
        try:
            df = _base(grupo)
        except dados_classes.DadosAusentes as error:
            return aviso(str(error)), None, None, None
        if recorte["data"]:
            df = df[df.data <= recorte["data"]]
        e = op.espaco(df, chaves, uf=recorte["uf"])
        a = op.alertas(df, chaves, sinal=sinal, uf=recorte["uf"])
        data = df.data.max()
        lugar = NOMES.get(recorte["uf"], "Brasil") if recorte["uf"] else "Brasil"
        contexto = f"{lugar}, carteira de {formato.data(data, mensal=True)} (SCR.data)."
        if e.empty:
            espaco = html.P(
                "Nenhum nicho atende às três condições neste recorte.",
                className="fs-vazio",
            )
        else:
            topo = e.head(10)
            espaco = html.Div(
                [
                    html.Div(
                        [
                            fs.kpi(
                                "Espaço somado",
                                e.espaco.sum() / 1e9,
                                unidade="R$ bi",
                                casas=1,
                                nota=f"{len(e)} nichos",
                            ),  # fmt: skip
                            fs.kpi(
                                "Maior espaço",
                                topo.espaco.iloc[0] / 1e9,
                                unidade="R$ bi",
                                casas=1,
                                nota=rotulo(topo.iloc[0], chaves),
                            ),  # fmt: skip
                        ],
                        className="fs-kpis",
                    ),
                    html.Div(
                        grafico(
                            figura_espaco(
                                [rotulo(r, chaves) for _, r in topo.iterrows()],
                                list(topo.espaco),
                            )
                        ),
                        className="fs-cartao-grafico",
                    ),  # fmt: skip
                    html.Div(tabela_espaco(e, chaves), className="fs-cartao-tabela"),
                ]
            )
        if a.empty:
            alertas = html.P(
                "Nenhum nicho com alta do atraso neste recorte.", className="fs-vazio"
            )
        else:
            alertas = html.Div(
                tabela_alertas(a, chaves, sinal), className="fs-cartao-tabela"
            )
        primeiro = a if not a.empty else e
        escolhido = (
            {
                "detalhe": detalhe,
                "chave": SEP.join(str(primeiro.iloc[0][c]) for c in chaves),
            }
            if not primeiro.empty
            else None
        )
        return espaco, alertas, contexto, escolhido

    @app.callback(
        Output("op-nicho", "data", allow_duplicate=True),
        Input({"type": "op-linha", "lista": ALL, "chave": ALL}, "n_clicks"),
        State("op-detalhe", "value"),
        prevent_initial_call=True,
    )
    def escolher(cliques, detalhe):
        if not ctx.triggered_id or not any(cliques):
            return no_update
        return {"detalhe": detalhe, "chave": ctx.triggered_id["chave"]}

    @app.callback(
        Output("op-nicho-titulo", "children"),
        Output("op-nicho-graficos", "children"),
        Input("op-nicho", "data"),
        State("op-grupo", "value"),
    )
    def nicho(escolhido, grupo):
        if not escolhido:
            return "Nicho no tempo", html.P(
                "Clique num nicho das tabelas para ver a evolução.",
                className="fs-vazio",
            )
        chaves = op.DETALHES[escolhido["detalhe"]]
        chave = dict(zip(chaves, escolhido["chave"].split(SEP), strict=True))
        try:
            s = op.serie_nicho(_base(grupo), chave)
        except dados_classes.DadosAusentes as error:
            return "Nicho no tempo", aviso(str(error))
        return f"{rotulo(chave, chaves)} no tempo", graficos_nicho(s)
