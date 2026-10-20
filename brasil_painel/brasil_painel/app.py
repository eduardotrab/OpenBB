"""Dash application factory."""

import contextlib
import threading

from dash import Dash, Input, Output, dcc, html

from brasil_painel.auth import setup_auth
from brasil_painel.componentes import noticias as noticias_ui
from brasil_painel.componentes.cartoes import cartoes
from brasil_painel.componentes.graficos import figura_curva, figura_focus
from brasil_painel.config import Settings
from brasil_painel.dados import abertura, noticias
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.usuarios import UserStore

TITLE = "Painel Brasil"
ATUALIZACAO_MS = 15 * 60 * 1000
CONFIG_GRAFICO = {"displaylogo": False, "responsive": True}


def secao(titulo: str, id_: str, nota: str = "") -> html.Section:
    """Build a titled block whose body is filled by a callback."""
    return html.Section(
        [
            html.H2(titulo),
            html.P(nota, className="nota") if nota else None,
            dcc.Loading(html.Div(id=id_), type="dot"),
        ],
        className="secao",
    )


def aviso(texto: str) -> html.P:
    """Message shown when a source fails."""
    return html.P(f"Fonte indisponível no momento: {texto}", className="aviso")


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
                                    html.H2("Notícias"),
                                    noticias_ui.filtro(),
                                    dcc.Loading(
                                        html.Div(id="noticias-lista"), type="dot"
                                    ),
                                ],
                                className="coluna-noticias secao",
                            ),
                        ],
                        className="grade-abertura",
                    ),
                ],
                className="conteudo",
            ),
            dcc.Store(id="noticias-dados"),
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

    @app.callback(
        Output("abertura-focus", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_focus(_):
        try:
            figura = figura_focus(abertura.focus(client))
        except FonteIndisponivel as error:
            return aviso(str(error))
        return dcc.Graph(figure=figura, config=CONFIG_GRAFICO)

    @app.callback(
        Output("abertura-tesouro", "children"), Input("atualizar", "n_intervals")
    )
    def preencher_tesouro(_):
        try:
            curvas = abertura.tesouro(client)
        except FonteIndisponivel as error:
            return aviso(str(error))
        return dcc.Graph(figure=figura_curva(curvas), config=CONFIG_GRAFICO)

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


def aquecer(client: OpenBBClient) -> None:
    """Fetch slow sources in the background so the first visitor does not wait."""

    def tarefa():
        with contextlib.suppress(FonteIndisponivel):
            abertura.tesouro(client)

    threading.Thread(target=tarefa, daemon=True, name="aquecer-tesouro").start()


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
    client = client or OpenBBClient(settings.api_url)
    register_callbacks(app, client)
    if settings.aquecer:
        aquecer(client)
    return app
