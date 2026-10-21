"""Dash application factory."""

import contextlib
import threading
import time

from dash import Dash, Input, Output, dcc, html

from brasil_painel.auth import setup_auth
from brasil_painel.config import Settings
from brasil_painel.dados import abertura, mundo
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.paginas import (
    abertura as pagina_abertura,
    estilo as pagina_estilo,
    mapa as pagina_mapa,
    mundo as pagina_mundo,
)
from brasil_painel.usuarios import UserStore

TITLE = "Painel Brasil"
ATUALIZACAO_MS = 15 * 60 * 1000

# path → (menu label or None for hidden pages, page module)
PAGINAS = {
    "/": ("Abertura", pagina_abertura),
    "/mundo": ("Mundo", pagina_mundo),
    "/mapa": ("Mapa", pagina_mapa),
    "/estilo": (None, pagina_estilo),  # internal gallery, not in the menu
}


def menu(caminho: str) -> list[dcc.Link]:
    """Navigation links; the current page is highlighted."""
    return [
        dcc.Link(
            rotulo,
            href=href,
            className="ativo" if href == caminho else "",
        )
        for href, (rotulo, _) in PAGINAS.items()
        if rotulo
    ]


def pagina(caminho: str | None) -> tuple:
    """Body and menu for a path; unknown paths get a not-found message."""
    caminho = (caminho or "/").rstrip("/") or "/"
    if caminho not in PAGINAS:
        return html.P("Página não encontrada.", className="aviso"), menu(caminho)
    return PAGINAS[caminho][1].layout(), menu(caminho)


def build_layout() -> html.Div:
    """Return the page shell: header with menu, page body and refresh timer."""
    return html.Div(
        [
            dcc.Location(id="url"),
            html.Header(
                [
                    html.H1(TITLE),
                    html.Nav(id="menu", className="menu"),
                    html.A("Sair", href="/logout", className="sair"),
                ],
                className="topo",
            ),
            html.Main(id="pagina", className="conteudo"),
            dcc.Interval(id="atualizar", interval=ATUALIZACAO_MS),
        ]
    )


def register_callbacks(app: Dash, client: OpenBBClient) -> None:
    """Routing plus the callbacks of every page."""

    @app.callback(
        Output("pagina", "children"),
        Output("menu", "children"),
        Input("url", "pathname"),
    )
    def rotear(caminho):
        return pagina(caminho)

    for _, modulo in PAGINAS.values():
        modulo.register(app, client)


def aquecer(client: OpenBBClient, intervalo: float | None = None) -> threading.Thread:
    """Fetch slow sources in the background so the first visitor does not wait.

    With `intervalo` (seconds) it repeats, refreshing the cache as it expires.
    """

    def uma_vez():
        with contextlib.suppress(FonteIndisponivel):
            abertura.tesouro(client)
        # World loaders isolate their own failures; the OECD routes take ~20 s.
        mundo.cartoes(client)
        mundo.juros(client)
        mundo.inflacao(client)
        mundo.agro(client)

    def tarefa():
        uma_vez()
        while intervalo:
            time.sleep(intervalo)
            uma_vez()

    thread = threading.Thread(target=tarefa, daemon=True, name="aquecer")
    thread.start()
    return thread


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
        suppress_callback_exceptions=True,
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
    client = client or OpenBBClient(settings.api_url)
    register_callbacks(app, client)
    if settings.aquecer:
        # Just after expiry, so each round refetches instead of hitting the cache.
        aquecer(client, intervalo=client.ttl + 5)
    return app
