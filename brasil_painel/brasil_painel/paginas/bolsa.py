"""Stock market monitor (homebroker style, delayed public B3 data, no orders)."""

from dash import Dash, Input, Output, dcc, html

from brasil_painel.componentes import fs
from brasil_painel.componentes.blocos import aviso, carregando, grafico
from brasil_painel.componentes.graficos import (
    figura_candles,
    figura_intradia,
    figura_mapa_calor,
)
from brasil_painel.dados import bolsa, formato
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.dados.classes import DadosAusentes
from brasil_painel.regional import armazem

CONFIG = {"displaylogo": False, "responsive": True}
PADRAO_LISTA = 10


def _tickers() -> list[str]:
    df = armazem.ler("b3_diario")
    return sorted(df.ticker.unique()) if df is not None else []


def _padrao() -> list[str]:
    try:
        return bolsa.carteira().ticker.head(PADRAO_LISTA).tolist()
    except DadosAusentes:
        return []


def _var(v: float | None) -> html.Span:
    if v is None:
        return html.Span("sem dado")
    classe = "sobe" if v > 0 else ("desce" if v < 0 else "")
    return html.Span(
        f"{'▲' if v > 0 else ('▼' if v < 0 else '■')} {formato.numero(v, 2, sinal=True)}%",
        className=f"fs-var {classe}",
    )


def tabela_lista(quotes: list[bolsa.Cotacao]) -> html.Table:
    """Watchlist rows."""

    def n(v, casas=2):
        return formato.numero(v, casas) if v is not None else "sem dado"

    corpo = [
        html.Tr(
            [
                html.Th(q.ticker, scope="row", title=q.nome),
                html.Td(n(q.ultimo), className="num"),
                html.Td(_var(q.variacao), className="num"),
                html.Td(n(q.maxima), className="num"),
                html.Td(n(q.minima), className="num"),
                html.Td(n(q.negocios, 0), className="num"),
            ]
        )  # fmt: skip
        for q in quotes
    ]
    cabecalho = html.Tr(
        [
            html.Th(t)
            for t in ("Ativo", "Último", "Variação", "Máxima", "Mínima", "Negócios")
        ]
    )
    return html.Table(
        [html.Thead(cabecalho), html.Tbody(corpo)], className="fs-matriz fs-lista-bolsa"
    )


def layout() -> html.Div:
    """Return the page body."""
    tickers = _tickers()
    padrao = _padrao()
    return html.Div(
        [
            html.P(
                "Cotações públicas da B3 com atraso de cerca de 15 minutos; fora do pregão, o último fechamento. "
                "Esta tela acompanha o mercado e não envia ordens.",
                className="fs-explicacao",
            ),
            carregando(html.Div(id="bolsa-ibov")),
            html.Div(
                [
                    html.Section(
                        [
                            html.H2("Lista de acompanhamento"),
                            dcc.Dropdown(
                                id="bolsa-lista",
                                options=tickers,
                                value=padrao,
                                multi=True,
                                persistence=True,
                                persistence_type="local",
                                className="fs-filtro",
                            ),  # fmt: skip
                            carregando(
                                html.Div(
                                    id="bolsa-tabela", className="fs-cartao-tabela"
                                )
                            ),
                        ],
                        className="secao",
                    ),
                    html.Section(
                        [
                            html.Div(
                                [
                                    html.H2("Ativo"),
                                    dcc.Dropdown(
                                        id="bolsa-ativo",
                                        options=tickers,
                                        value=padrao[0] if padrao else None,
                                        clearable=False,
                                        className="fs-filtro fs-filtro-ativo",
                                    ),
                                ],  # fmt: skip
                                className="fs-barra-tela",
                            ),
                            carregando(html.Div(id="bolsa-detalhe")),
                        ],
                        className="secao",
                    ),
                ],
                className="fs-grade-bolsa",
            ),
            html.Section(
                [
                    html.H2("Ibovespa: maiores altas e baixas"),
                    carregando(html.Div(id="bolsa-movimentos")),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2("Mapa de calor do Ibovespa"),
                    html.P(
                        "Tamanho pelo peso no índice, cor pela variação do dia.",
                        className="nota",
                    ),
                    carregando(html.Div(id="bolsa-calor")),
                ],  # fmt: skip
                className="secao",
            ),
        ],
        className="fs-tela",
    )


def bloco_ibov() -> html.Div:
    """Ibovespa points, change and the session chart."""
    q = bolsa.cotacao("IBOV")
    pontos = bolsa.intradia("IBOV")
    kpi = fs.kpi("Ibovespa", q.ultimo if q else None, unidade="pts", casas=0,
                 nota=q.momento if q else "sem cotação")  # fmt: skip
    return html.Div(
        [
            html.Div(
                [
                    kpi,
                    html.P(
                        _var(q.variacao if q else None), className="fs-kpi-variacao"
                    ),
                ],
                className="fs-ibov-kpi",
            ),
            dcc.Graph(
                figure=figura_intradia(pontos),
                config={"displayModeBar": False},
                style={"height": "180px"},
            )
            if pontos
            else html.P("Sem negócios hoje ainda.", className="fs-vazio"),
        ],
        className="fs-faixa fs-ibov",
    )


def bloco_ativo(ticker: str) -> html.Div:
    """Quote KPIs, daily candles and the session of one asset."""
    q = bolsa.cotacao(ticker)
    df = bolsa.candles(ticker)
    pontos = bolsa.intradia(ticker)
    kpis = html.Div(
        [
            fs.kpi(
                q.nome if q else ticker,
                q.ultimo if q else None,
                unidade="R$",
                casas=2,
                nota=q.momento if q else "",
            ),
            html.Div(
                [
                    html.P("Variação", className="fs-kpi-rotulo"),
                    html.P(_var(q.variacao if q else None)),
                ]
            ),
            fs.kpi("Máxima", q.maxima if q else None, casas=2),
            fs.kpi("Mínima", q.minima if q else None, casas=2),
        ],
        className="fs-faixa",
    )
    filhos = [
        kpis,
        grafico(figura_candles(df))
        if not df.empty
        else aviso("sem histórico para este ativo"),
    ]
    if pontos:
        filhos.append(html.Div([html.P("Hoje, minuto a minuto", className="fs-mini-titulo"),
                                dcc.Graph(figure=figura_intradia(pontos), config=CONFIG, style={"height": "180px"})],
                               className="fs-cartao-grafico"))  # fmt: skip
    return html.Div(filhos, className="fs-tela")


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(Output("bolsa-ibov", "children"), Input("atualizar", "n_intervals"))
    def ibov(_):
        return bloco_ibov()

    @app.callback(Output("bolsa-tabela", "children"), Input("bolsa-lista", "value"))
    def lista(tickers):
        if not tickers:
            return html.P("Escolha ativos para acompanhar.", className="fs-vazio")
        return tabela_lista(bolsa.cotacoes(tickers))

    @app.callback(Output("bolsa-detalhe", "children"), Input("bolsa-ativo", "value"))
    def detalhe(ticker):
        if not ticker:
            return aviso(
                "dados da B3 ainda não foram baixados: rode `painel-dados atualizar b3`"
            )
        try:
            return bloco_ativo(ticker)
        except DadosAusentes as error:
            return aviso(str(error))

    @app.callback(
        Output("bolsa-movimentos", "children"),
        Output("bolsa-calor", "children"),
        Input("atualizar", "n_intervals"),
    )
    def indice(_):
        try:
            carteira = bolsa.carteira()
        except DadosAusentes as error:
            return aviso(str(error)), None
        quotes = bolsa.cotacoes(carteira.ticker.tolist())
        altas, baixas = bolsa.altas_baixas(quotes)
        movimentos = html.Div(
            [
                html.Div(
                    [
                        html.H3("Maiores altas", className="fs-destaque-titulo"),
                        tabela_lista(altas),
                    ],
                    className="fs-cartao-tabela fs-pad",
                ),  # fmt: skip
                html.Div(
                    [
                        html.H3("Maiores baixas", className="fs-destaque-titulo"),
                        tabela_lista(baixas),
                    ],
                    className="fs-cartao-tabela fs-pad",
                ),  # fmt: skip
            ],
            className="fs-grade-produtos fs-meio",
        )
        return movimentos, grafico(
            figura_mapa_calor(carteira, {q.ticker: q for q in quotes})
        )
