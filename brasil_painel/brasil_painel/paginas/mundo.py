"""World page: United States, Europe, China, commodities and exchange rates."""

from dash import Dash, Input, Output, html

from brasil_painel.componentes.blocos import aviso, grafico, secao
from brasil_painel.componentes.cartoes import cartoes
from brasil_painel.componentes.graficos import figura_linhas
from brasil_painel.dados import mundo
from brasil_painel.dados.api import OpenBBClient

BLOCOS = [
    ("Estados Unidos", "mundo-eua"),
    ("Europa (zona do euro)", "mundo-europa"),
    ("China", "mundo-china"),
    ("Câmbio", "mundo-cambio"),
    ("Commodities do agro (US$)", "mundo-commodities"),
]

GRAFICOS = [
    (
        "Juros básicos",
        "mundo-juros",
        "Fed funds efetiva, taxa de depósito do BCE e Selic meta, em % ao ano.",
    ),
    (
        "Inflação em 12 meses",
        "mundo-inflacao",
        "EUA, China e zona do euro (HICP) pelo IMF; Brasil (IPCA, IBGE).",
    ),
    (
        "Commodities do agro",
        "mundo-agro",
        "Preço em dólar, índice base 100 = 12 meses antes (IMF, mensal).",
    ),
]


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(
                [secao(titulo, id_) for titulo, id_ in BLOCOS],
                className="grade-blocos",
            ),
            html.Div(
                [secao(titulo, id_, nota) for titulo, id_, nota in GRAFICOS],
                className="grade-graficos",
            ),
        ]
    )


def grafico_ou_aviso(series, falhas: list[str], unidade: str, **opcoes):
    """Chart of the series that loaded, plus a note naming the ones that failed."""
    if not series:
        return aviso(", ".join(falhas))
    filhos = [grafico(figura_linhas(series, unidade, **opcoes))]
    if falhas:
        filhos.append(aviso(", ".join(falhas)))
    return html.Div(filhos)


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks that fill the world page."""

    @app.callback(
        [Output(id_, "children") for _, id_ in BLOCOS],
        Input("atualizar", "n_intervals"),
    )
    def preencher_cartoes(_):
        blocos = mundo.cartoes(client)
        return [cartoes(blocos[id_]) for _, id_ in BLOCOS]

    @app.callback(Output("mundo-juros", "children"), Input("atualizar", "n_intervals"))
    def preencher_juros(_):
        return grafico_ou_aviso(*mundo.juros(client), "%", degrau=True)

    @app.callback(
        Output("mundo-inflacao", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_inflacao(_):
        return grafico_ou_aviso(*mundo.inflacao(client), "%", mensal=True)

    @app.callback(Output("mundo-agro", "children"), Input("atualizar", "n_intervals"))
    def preencher_agro(_):
        return grafico_ou_aviso(*mundo.agro(client), "", base_100=True, mensal=True)
