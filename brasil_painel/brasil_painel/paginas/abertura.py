"""Opening screen: Brazilian macro cards, Focus, Tesouro curve, agenda and news."""

from dash import Dash, Input, Output, dcc, html

from brasil_painel.componentes import noticias as noticias_ui
from brasil_painel.componentes.agenda import agenda as agenda_ui
from brasil_painel.componentes.blocos import aviso, grafico, secao
from brasil_painel.componentes.cartoes import cartoes
from brasil_painel.componentes.graficos import figura_curva, figura_focus
from brasil_painel.dados import abertura, agenda, noticias
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            secao("Cenário macro — Brasil", "abertura-cartoes"),
            html.Div(
                [
                    html.Div(
                        [
                            secao(
                                "Expectativas de mercado (Focus)",
                                "abertura-focus",
                                "Mediana das projeções para este ano e o próximo"
                                " — BCB, pesquisa diária.",
                            ),
                            secao(
                                "Curva de juros — Tesouro Direto",
                                "abertura-tesouro",
                                "Taxa de compra por vencimento: última data"
                                " vs. 30 dias antes.",
                            ),
                        ],
                        className="coluna-principal",
                    ),
                    html.Aside(
                        [
                            html.H2("Agenda — próximos 7 dias"),
                            dcc.Loading(html.Div(id="agenda-lista"), type="dot"),
                            html.H2("Notícias"),
                            noticias_ui.filtro(),
                            dcc.Loading(html.Div(id="noticias-lista"), type="dot"),
                        ],
                        className="coluna-noticias secao",
                    ),
                ],
                className="grade-abertura",
            ),
            dcc.Store(id="noticias-dados"),
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
