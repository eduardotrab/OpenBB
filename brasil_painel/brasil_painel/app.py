"""Dash application factory."""

from dash import Dash, html

from brasil_painel.auth import setup_auth
from brasil_painel.config import Settings
from brasil_painel.usuarios import UserStore

TITLE = "Painel Brasil"


def build_layout() -> html.Div:
    """Return the page layout."""
    return html.Div(
        [
            html.Header(
                [html.H1(TITLE), html.A("Sair", href="/logout", className="sair")],
                className="topo",
            ),
            html.Main(
                [html.H2("Cenário macro — Brasil"), html.Div(id="abertura")],
                className="conteudo",
            ),
        ]
    )


def create_app(settings: Settings | None = None) -> Dash:
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
    return app
