"""Economic bulletin: expectations, quotes and agribusiness, printable as PDF."""

import datetime as dt

from dash import Dash, Input, Output, html

from brasil_painel.componentes.blocos import carregando
from brasil_painel.dados import boletim, formato
from brasil_painel.dados.api import OpenBBClient

SETAS = {"sobe": "▲", "desce": "▼", "estavel": "■"}
PALAVRAS = {"sobe": "alta", "desce": "queda", "estavel": "estável"}


def _semanas(e: boletim.Expectativa) -> str:
    if e.semanas == 0:
        return "sem histórico"
    return (
        f"{PALAVRAS[e.tendencia]} há {e.semanas} semana{'s' if e.semanas > 1 else ''}"
    )


def cartao_focus(itens: list[boletim.Expectativa]) -> html.Div:
    """One Focus indicator with this year and the next."""
    primeiro = itens[0]
    linhas = [
        html.Div(
            [
                html.Span(str(e.ano), className="fs-bol-ano"),
                html.Span(
                    formato.numero(e.valor, 2) if e.valor is not None else "sem dado",
                    className="fs-bol-valor",
                ),
                html.Span(
                    f"{SETAS[e.tendencia]} {_semanas(e)}",
                    className=f"fs-bol-tendencia {e.tendencia}",
                ),
            ],
            className="fs-bol-linha",
        )
        for e in itens
    ]
    return html.Div(
        [
            html.Div(
                [html.H3(primeiro.rotulo), html.Span(primeiro.unidade)],
                className="fs-bol-cabecalho",
            ),
            *linhas,
        ],
        className="fs-bol-cartao",
    )


def _var(q: boletim.Cotacao) -> str:
    if q.variacao is None:
        return "sem dado"
    seta = "▲" if q.variacao > 0 else ("▼" if q.variacao < 0 else "■")
    return f"{seta} {formato.numero(q.variacao, 2, sinal=True)}%"


def _valor(q: boletim.Cotacao, casas: int = 2) -> str:
    if q.valor is None:
        return "sem dado"
    return (
        f"{q.unidade} {formato.numero(q.valor, casas)}"
        if q.unidade in ("R$", "US$")
        else f"{formato.numero(q.valor, casas)} {q.unidade}"
    )


def tabela_cotacoes(
    cotacoes: list[boletim.Cotacao], titulo_variacao: str, casas: int = 2
) -> html.Table:
    """Quote rows: name, value, change."""
    return html.Table(
        [
            html.Thead(
                html.Tr([html.Th("Ativo"), html.Th("Valor"), html.Th(titulo_variacao)])
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Th(q.rotulo, scope="row"),
                            html.Td(_valor(q, casas), className="num"),
                            html.Td(_var(q), className="num"),
                        ]  # fmt: skip
                    )
                    for q in cotacoes
                ]
            ),
        ],
        className="fs-bol-tabela",
    )


def cartoes_cotacao(cotacoes: list[boletim.Cotacao], casas: int = 2) -> html.Div:
    """Small quote cards (crypto, agribusiness)."""
    return html.Div(
        [
            html.Div(
                [
                    html.H3(q.rotulo),
                    html.P(_valor(q, casas), className="fs-bol-valor"),
                    html.P(
                        f"{_var(q)} {'na semana' if q.periodo == 'semanal' else 'no mês'}",
                        className="fs-bol-var",
                    ),
                    html.P(
                        f"{q.fonte}, {formato.data(q.data, mensal=q.periodo == 'mensal') if q.data else 'sem data'}",
                        className="fs-bol-fonte",
                    ),  # fmt: skip
                ],
                className="fs-bol-cartao pequeno",
            )
            for q in cotacoes
        ],
        className="fs-bol-grade",
    )


def pagina(titulo: str, selo: str, corpo: list, rodape: str) -> html.Section:
    """One bulletin page: dark band, title, pill and content."""
    return html.Section(
        [
            html.Div(
                [
                    html.H2(titulo, className="fs-bol-titulo"),
                    html.Span(selo, className="fs-bol-selo"),
                ],
                className="fs-bol-topo",
            ),  # fmt: skip
            *corpo,
            html.P(rodape, className="fs-bol-rodape"),
        ],
        className="fs-bol-pagina",
    )


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(
                [
                    html.Button(
                        "Salvar em PDF", id="bol-imprimir", className="fs-botao"
                    ),
                    html.P(
                        'Abre a impressão do navegador; escolha "Salvar como PDF".',
                        className="fs-explicacao",
                    ),
                ],
                className="fs-barra-tela fs-bol-acoes",
            ),
            carregando(html.Div(id="bol-conteudo")),
            html.Div(id="bol-impressao", style={"display": "none"}),
        ],
        className="fs-tela",
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(Output("bol-conteudo", "children"), Input("atualizar", "n_intervals"))
    def preencher(_):
        hoje = dt.date.today()
        exp = boletim.expectativas(client, hoje)
        por_indicador: dict[str, list] = {}
        for e in exp:
            por_indicador.setdefault(e.rotulo, []).append(e)
        edicao = f"Atualizado em {formato.data(hoje)}"
        return [
            pagina(
                "Boletim Econômico",
                "Expectativas de mercado",
                [
                    html.P(edicao, className="fs-bol-edicao"),
                    html.Div(
                        [cartao_focus(v) for v in por_indicador.values()],
                        className="fs-bol-grade",
                    ),
                    html.P(
                        "▲ alta  ▼ queda  ■ estável, contando as semanas seguidas na mesma direção.",
                        className="fs-bol-legenda",
                    ),  # fmt: skip
                ],
                "Fonte: Banco Central do Brasil, pesquisa Focus (mediana).",
            ),
            pagina(
                "Cotações",
                "Mercados internacionais",
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3("Moedas"),
                                    tabela_cotacoes(
                                        boletim.moedas(client, hoje), "Na semana", 4
                                    ),
                                ],
                                className="fs-bol-cartao",
                            ),  # fmt: skip
                            html.Div(
                                [
                                    html.H3("Ouro e petróleo"),
                                    tabela_cotacoes(
                                        boletim.metais_petroleo(client, hoje), "No mês"
                                    ),
                                ],  # fmt: skip
                                className="fs-bol-cartao",
                            ),
                        ],
                        className="fs-bol-grade dupla",
                    ),
                    html.H3("Criptoativos", className="fs-bol-subtitulo"),
                    cartoes_cotacao(boletim.cripto()),
                ],
                "Fontes: BCE (câmbio de referência), FMI (ouro e petróleo, média mensal), Mercado Bitcoin e Binance (cripto).",
            ),
            pagina(
                "Agronegócio",
                "Mercados internacionais",
                [cartoes_cotacao(boletim.agro(client, hoje))],
                "Fonte: FMI, preços internacionais de commodities (média mensal, em dólar).",
            ),
        ]

    app.clientside_callback(
        "function (n) { if (n) { window.print(); } return ''; }",
        Output("bol-impressao", "children"),
        Input("bol-imprimir", "n_clicks"),
        prevent_initial_call=True,
    )
