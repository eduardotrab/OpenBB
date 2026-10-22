"""Dash application factory."""

import contextlib
import threading
import time

from dash import Dash, Input, Output, State, dcc, html
from flask_login import current_user

from brasil_painel import navegacao
from brasil_painel.auth import setup_auth
from brasil_painel.componentes import filtros
from brasil_painel.config import Settings
from brasil_painel.dados import abertura, boletim, bolsa, mundo
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.navegacao import Pagina
from brasil_painel.paginas import (
    abertura as pagina_abertura,
    boletim as pagina_boletim,
    bolsa as pagina_bolsa,
    comparativo as pagina_comparativo,
    cooperativas as pagina_cooperativas,
    estilo as pagina_estilo,
    explorador as pagina_explorador,
    mapa as pagina_mapa,
    mundo as pagina_mundo,
    oportunidades as pagina_oportunidades,
    produtos as pagina_produtos,
    rural as pagina_rural,
)
from brasil_painel.paginas.segmento import EMPRESAS, PESSOAS
from brasil_painel.usuarios import UserStore

TITLE = "FinScope"
ATUALIZACAO_MS = 15 * 60 * 1000

PAGINAS = [
    Pagina("/", "Visão 360°", "Mercado", "radar", pagina_abertura),
    Pagina("/mundo", "Mundo", "Mercado", "globo", pagina_mundo),
    Pagina("/mapa", "Mapa", "Mercado", "mapa", pagina_mapa),
    Pagina("/pessoas", "Pessoas", "Segmentos", "pessoas", PESSOAS),
    Pagina("/empresas", "Empresas", "Segmentos", "empresas", EMPRESAS),
    Pagina("/rural", "Rural", "Segmentos", "rural", pagina_rural),
    Pagina(
        "/comparativo", "Comparativo", "Segmentos", "comparativo", pagina_comparativo
    ),
    Pagina(
        "/oportunidades", "Oportunidades", "Decisão", "decisao", pagina_oportunidades
    ),
    Pagina(
        "/cooperativas", "Cooperativas", "Decisão", "cooperativas", pagina_cooperativas
    ),
    Pagina("/produtos", "Produtos", "Produtos", "produtos", pagina_produtos),
    Pagina("/boletim", "Boletim Econômico", "Boletim", "boletim", pagina_boletim),
    Pagina("/bolsa", "Bolsa", "Bolsa", "bolsa", pagina_bolsa),
    Pagina(
        "/explorador",
        "Explorador OpenBB",
        "Explorador",
        "explorador",
        pagina_explorador,
    ),
    Pagina("/estilo", "Galeria", None, "radar", pagina_estilo),  # internal
]
POR_CAMINHO = {p.caminho: p for p in PAGINAS}


def pagina(caminho: str | None) -> tuple:
    """Body, menu and title for a path; unknown paths get a not-found message."""
    caminho = (caminho or "/").rstrip("/") or "/"
    atual = POR_CAMINHO.get(caminho)
    if atual is None:
        corpo = html.P(
            "Esta tela não existe. Escolha uma opção no menu.", className="aviso"
        )
        return corpo, navegacao.menu(PAGINAS, caminho), "Página não encontrada"
    return atual.modulo.layout(), navegacao.menu(PAGINAS, caminho), atual.titulo


def _usuario() -> str:
    """Logged-in username (empty when login is disabled, as in tests)."""
    try:
        return current_user.id if current_user.is_authenticated else ""
    except (AttributeError, RuntimeError):
        return ""


def build_layout() -> html.Div:
    """Return the shell: sidebar, top bar, page body and refresh timer."""
    return html.Div(
        [
            dcc.Location(id="url"),
            dcc.Store(id="lateral-recolhida", storage_type="local"),
            html.Aside(
                [
                    html.Div(
                        [
                            html.Span(TITLE, className="fs-marca"),
                            html.Button(
                                navegacao.icone("recolher"),
                                id="recolher",
                                className="fs-recolher",
                                title="Recolher ou abrir o menu",
                                **{"aria-label": "Recolher ou abrir o menu"},
                            ),
                        ],
                        className="fs-lateral-topo",
                    ),
                    html.Nav(id="menu", className="fs-menu", **{"aria-label": "Telas"}),
                ],
                className="fs-lateral",
            ),
            html.Div(
                [
                    html.Header(
                        [
                            html.H1(id="titulo-pagina", className="fs-titulo"),
                            html.Div(filtros.controles(), className="fs-filtros"),
                            html.Div(
                                [
                                    html.Span(_usuario(), className="fs-usuario"),
                                    html.A(
                                        [navegacao.icone("sair"), html.Span("Sair")],
                                        href="/logout",
                                        className="fs-sair",
                                    ),
                                ],
                                className="fs-conta",
                            ),
                        ],
                        className="fs-topo",
                    ),
                    html.Main(id="pagina", className="conteudo"),
                ],
                className="fs-corpo",
            ),
            dcc.Interval(id="atualizar", interval=ATUALIZACAO_MS),
        ],
        id="casca",
        className="fs-casca",
    )


def register_callbacks(app: Dash, client: OpenBBClient) -> None:
    """Routing plus the callbacks of every page."""

    @app.callback(
        Output("pagina", "children"),
        Output("menu", "children"),
        Output("titulo-pagina", "children"),
        Input("url", "pathname"),
    )
    def rotear(caminho):
        return pagina(caminho)

    @app.callback(
        Output("filtros", "data"),
        Output("selo-topo", "children"),
        Input("filtro-uf", "value"),
        Input("filtro-data", "value"),
    )
    def guardar_filtros(uf, data):
        valores = {"uf": uf or filtros.PADRAO["uf"], "data": data or ""}
        return valores, filtros.selo(valores)

    for item in PAGINAS:
        item.modulo.register(app, client)

    # Collapsing the sidebar runs in the browser and is remembered locally.
    app.clientside_callback(
        """
        function (cliques, salvo) {
            var recolhida = cliques ? !salvo : Boolean(salvo);
            return [recolhida, recolhida ? "fs-casca recolhida" : "fs-casca"];
        }
        """,
        Output("lateral-recolhida", "data"),
        Output("casca", "className"),
        Input("recolher", "n_clicks"),
        State("lateral-recolhida", "data"),
    )


def aquecer(client: OpenBBClient, intervalo: float | None = None) -> threading.Thread:
    """Fetch slow sources in the background so the first visitor does not wait.

    With `intervalo` (seconds) it repeats, refreshing the cache as it expires.
    """

    def uma_vez():
        with contextlib.suppress(FonteIndisponivel):
            abertura.tesouro(client)
        # World loaders isolate their own failures.
        mundo.cartoes(client)
        mundo.juros(client)
        mundo.inflacao(client)
        mundo.agro(client)
        # Bulletin and stock monitor: a failing source must not stop the warm-up.
        for carregar in (
            lambda: boletim.expectativas(client),
            lambda: boletim.moedas(client),
            lambda: boletim.metais_petroleo(client),
            lambda: boletim.agro(client),
            boletim.cripto,
            lambda: bolsa.cotacoes(["IBOV", *bolsa.carteira().ticker]),
        ):
            with contextlib.suppress(Exception):
                carregar()

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
