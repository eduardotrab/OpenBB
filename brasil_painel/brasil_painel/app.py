"""Dash application factory."""

from dash import Dash, html

from brasil_painel.config import Settings

TITLE = "Painel Brasil"


def build_layout() -> html.Div:
    """Return the page layout."""
    return html.Div(
        [
            html.Header(html.H1(TITLE), className="topo"),
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
    app.layout = build_layout
    return app
