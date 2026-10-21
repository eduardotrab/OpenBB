"""Opening screen: Brazilian macro cards, Focus, Tesouro curve, agenda and news."""

from dash import Dash, Input, Output, dcc, html

from brasil_painel.componentes import (
    fs,
    noticias as noticias_ui,
)
from brasil_painel.componentes.agenda import agenda as agenda_ui
from brasil_painel.componentes.blocos import aviso, carregando, grafico, secao
from brasil_painel.componentes.cartoes import cartoes
from brasil_painel.componentes.graficos import figura_curva, figura_focus
from brasil_painel.dados import (
    abertura,
    agenda,
    classes as dados_classes,
    destaques,
    formato,
    mundo as dados_mundo,
    noticias,
)
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.paginas.segmento import filtros_da_tela

MUNDO_RESUMO = [
    ("mundo-eua", "Fed funds (efetiva)"),
    ("mundo-europa", "Taxa de depósito do BCE"),
    ("mundo-cambio", "EUR/USD"),
    ("mundo-commodities", "Soja"),
]


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            secao("Cenário macro do Brasil", "abertura-cartoes"),
            secao("Crédito", "abertura-credito"),
            html.Div(
                [
                    html.Div(
                        [
                            secao(
                                "O que mudou em 12 meses",
                                "abertura-destaques",
                                "Onde a inadimplência mais subiu e quais produtos mais cresceram ou encolheram.",
                            ),
                            secao("Mundo em resumo", "abertura-mundo"),
                            secao(
                                "Expectativas de mercado (Focus)",
                                "abertura-focus",
                                "Mediana das projeções para este ano e o próximo. Fonte: BCB, pesquisa diária.",
                            ),
                            secao(
                                "Curva de juros do Tesouro Direto",
                                "abertura-tesouro",
                                "Taxa de compra por vencimento: última data e 30 dias antes.",
                            ),
                        ],
                        className="coluna-principal",
                    ),
                    html.Aside(
                        [
                            html.H2("Agenda dos próximos 7 dias"),
                            carregando(html.Div(id="agenda-lista")),
                            html.H2("Notícias"),
                            noticias_ui.filtro(),
                            carregando(html.Div(id="noticias-lista")),
                        ],
                        className="coluna-noticias secao",
                    ),
                ],
                className="grade-abertura",
            ),
            dcc.Store(id="noticias-dados"),
        ]
    )


def faixa_credito(credito: destaques.Credito) -> html.Div:
    """KPI strip of the whole credit system (follows the global filters)."""
    t = credito.total
    return html.Div(
        [
            fs.kpi(
                "Carteira de crédito",
                t.carteira / 1e12 if t.carteira else None,
                unidade="R$ tri",
                casas=2,
                variacao=t.crescimento_12m,
                sufixo_variacao="%",
                comparacao="em 12 meses",
            ),  # fmt: skip
            fs.kpi(
                "Inadimplência",
                t.inadimplencia,
                unidade="%",
                casas=2,
                variacao=dados_classes.variacao_12m(t.tendencia),
                comparacao="p.p. em 12 meses",
            ),  # fmt: skip
            fs.kpi("Share das cooperativas", t.share_coop, unidade="%"),
            fs.kpi("Atraso de 15 a 90 dias", t.atraso, unidade="%", casas=2),
            fs.kpi(
                "Pix pago no mês",
                credito.pix_mes / 1e12 if credito.pix_mes else None,
                unidade="R$ tri",
                casas=2,
                nota=formato.data(credito.pix_data, mensal=True)
                if credito.pix_data
                else "",
            ),
        ],
        className="fs-faixa",
    )


def lista_destaques(titulo: str, itens: list[destaques.Item], unidade: str) -> html.Div:
    """One highlight list with arrows, values and a link to the right screen."""
    if not itens:
        return html.Div(
            [
                html.H3(titulo, className="fs-destaque-titulo"),
                html.P("Nada a destacar.", className="fs-vazio"),
            ]
        )
    return html.Div(
        [
            html.H3(titulo, className="fs-destaque-titulo"),
            html.Ul(
                [
                    html.Li(
                        dcc.Link(
                            [
                                html.Span(item.rotulo, className="fs-destaque-rotulo"),
                                html.Span(
                                    f"{'▲' if item.variacao > 0 else '▼'} {formato.numero(item.variacao, 2 if unidade == 'p.p.' else 1, sinal=True)} {unidade}",
                                    className="fs-destaque-valor",
                                ),
                            ],
                            href=item.href,
                        )
                    )
                    for item in itens
                ],
                className="fs-destaque-lista",
            ),
        ]
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks that fill the opening screen."""

    @app.callback(
        Output("abertura-cartoes", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_cartoes(_):
        return cartoes(abertura.indicadores(client))

    @app.callback(
        Output("abertura-focus", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_focus(_):
        try:
            figura = figura_focus(abertura.focus(client))
        except FonteIndisponivel as error:
            return aviso(str(error))
        return grafico(figura)

    @app.callback(
        Output("abertura-tesouro", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_tesouro(_):
        try:
            curvas = abertura.tesouro(client)
        except FonteIndisponivel as error:
            return aviso(str(error))
        return grafico(figura_curva(curvas))

    @app.callback(
        Output("abertura-credito", "children"),
        Output("abertura-destaques", "children"),
        Input("filtros", "data"),
    )
    def preencher_credito(filtros):
        recorte = filtros_da_tela(filtros)
        try:
            credito = destaques.faixa_credito(**recorte)
            d = destaques.calcular(**recorte)
        except dados_classes.DadosAusentes as error:
            return aviso(str(error)), None
        listas = html.Div(
            [
                lista_destaques(
                    "Classes com mais alta da inadimplência", d.classes_piora, "p.p."
                ),
                lista_destaques(
                    "Estados com mais alta da inadimplência", d.ufs_piora, "p.p."
                ),
                lista_destaques("Produtos que mais cresceram", d.produtos_alta, "%"),
                lista_destaques("Produtos que menos cresceram", d.produtos_baixa, "%"),
            ],
            className="fs-destaques",
        )
        return faixa_credito(credito), listas

    @app.callback(
        Output("abertura-mundo", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_mundo(_):
        blocos = dados_mundo.cartoes(client)
        escolhidos = []
        for bloco, nome in MUNDO_RESUMO:
            escolhidos += [r for r in blocos.get(bloco, []) if r.nome == nome]
        return html.Div(
            [
                cartoes(escolhidos),
                dcc.Link("Ver a tela Mundo", href="/mundo", className="fs-link"),
            ]
        )

    @app.callback(Output("agenda-lista", "children"), Input("atualizar", "n_intervals"))
    def preencher_agenda(_):
        eventos, falhas = agenda.semana()
        return agenda_ui(eventos, falhas)

    @app.callback(Output("noticias-dados", "data"), Input("atualizar", "n_intervals"))
    def carregar_noticias(_):
        itens, falhas = noticias.coletar(client)
        return {"itens": noticias_ui.para_store(itens), "falhas": falhas}

    @app.callback(
        Output("noticias-lista", "children"),
        Input("noticias-filtro", "value"),
        Input("noticias-dados", "data"),
    )
    def mostrar_noticias(origens, dados):
        if not dados:
            return None
        return noticias_ui.lista(dados["itens"], origens or [], dados["falhas"])
