"""Dash application factory."""

from dash import Dash, Input, Output, dcc, html

from brasil_painel.auth import setup_auth
from brasil_painel.componentes.cartoes import cartoes
from brasil_painel.config import Settings
from brasil_painel.dados import abertura
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.usuarios import UserStore

TITLE = "Painel Brasil"
ATUALIZACAO_MS = 15 * 60 * 1000


def build_layout() -> html.Div:
    """Return the page layout."""
    return html.Div(
        [
            html.Header(
                [html.H1(TITLE), html.A("Sair", href="/logout", className="sair")],
                className="topo",
            ),
            html.Main(
                [
                    html.H2("Cenário macro — Brasil"),
                    dcc.Loading(html.Div(id="abertura-cartoes"), type="dot"),
                ],
                className="conteudo",
            ),
            dcc.Interval(id="atualizar", interval=ATUALIZACAO_MS),
        ]
    )


def register_callbacks(app: Dash, client: OpenBBClient) -> None:
    """Callbacks that fill the opening screen."""

    @app.callback(
        Output("abertura-cartoes", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_cartoes(_):
        return cartoes(abertura.indicadores(client))


def create_app(
    settings: Settings | None = None, client: OpenBBClient | None = None
) -> Dash:
    """Create the Dash app; every asset is served locally (no CDN)."""
    settings = settings or Settings.from_env()
    app = Dash(
        __name__,
        title=TITLE,
        serve_locally=True,
        update_title=None,
    )
    app.server.config["PAINEL_SETTINGS"] = settings
    if settings.users_file is not None:
        if not settings.secret_key:
            raise RuntimeError("Defina PAINEL_SECRET_KEY (chave das sessões de login).")
        setup_auth(
            app.server,
            UserStore(settings.users_file),
            settings.secret_key,
            https=settings.https,
        )
    app.layout = build_layout
    register_callbacks(app, client or OpenBBClient(settings.api_url))
    return app
