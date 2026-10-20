"""World page: United States, Europe, China, commodities and exchange rates."""

from dash import Dash, html

from brasil_painel.componentes.blocos import secao
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
        "Fed funds efetiva, taxa de depósito do BCE e Selic meta — % a.a.",
    ),
    (
        "Inflação em 12 meses",
        "mundo-inflacao",
        "EUA e China (OCDE), zona do euro (HICP, IMF) e Brasil (IPCA, IBGE).",
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
        [secao(titulo, id_) for titulo, id_ in BLOCOS]
        + [
            html.Div(
                [secao(titulo, id_, nota) for titulo, id_, nota in GRAFICOS],
                className="grade-graficos",
            )
        ]
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks that fill the world page."""
