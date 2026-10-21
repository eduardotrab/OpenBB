"""OpenBB explorer screen: browse every function like the CLI, run it, or use your own base."""

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

from brasil_painel.componentes.blocos import aviso, carregando, grafico
from brasil_painel.componentes.graficos import figura_automatica
from brasil_painel.dados import explorador, insights
from brasil_painel.dados.api import OpenBBClient

MAX_LINHAS = 5000
OCULTO, VISIVEL = {"display": "none"}, {}


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(
                [
                    dcc.Input(
                        id="exp-busca",
                        type="search",
                        debounce=True,
                        placeholder="Buscar função (ex.: cpi, treasury, focus)",
                        className="fs-busca",
                    ),  # fmt: skip
                    html.Nav(
                        id="exp-trilha",
                        className="fs-trilha",
                        **{"aria-label": "Caminho"},
                    ),
                ],
                className="fs-barra-tela",
            ),
            html.Div(
                [
                    html.Div(
                        carregando(html.Div(id="exp-lista")), className="fs-exp-lista"
                    ),
                    html.Section(
                        [
                            html.Div(id="exp-ficha"),
                            html.Div(
                                [
                                    html.Label(
                                        "Fonte de dados",
                                        htmlFor="exp-provedor",
                                        className="fs-exp-rotulo",
                                    ),
                                    dcc.Dropdown(
                                        id="exp-provedor",
                                        clearable=False,
                                        className="fs-filtro",
                                    ),
                                ],
                                className="fs-exp-campo",
                            ),
                            html.Div(id="exp-form", className="fs-exp-form"),
                            html.Div(
                                [
                                    html.Button(
                                        "Rodar", id="exp-rodar", className="fs-botao"
                                    ),
                                    html.Button(
                                        "Ver com dados de exemplo",
                                        id="exp-exemplo",
                                        className="fs-botao secundario",
                                    ),
                                    html.Button(
                                        "Enviar minha base",
                                        id="exp-abrir",
                                        className="fs-botao secundario",
                                    ),
                                ],
                                className="fs-exp-acoes",
                            ),
                        ],
                        id="exp-painel",
                        className="fs-exp-painel",
                        style=OCULTO,
                    ),
                ],
                className="fs-exp-grade",
            ),
            carregando(html.Div(id="exp-resultado")),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Enviar minha base"),
                            html.P(
                                "CSV ou Excel, até 10 MB. O arquivo é lido na memória desta sessão e não é gravado no "
                                "servidor. Baixe o modelo para ver as colunas que esta função usa.",
                                className="fs-explicacao",
                            ),
                            html.Button(
                                "Baixar modelo de colunas",
                                id="exp-modelo",
                                className="fs-botao secundario",
                            ),
                            dcc.Upload(
                                id="exp-upload",
                                children=html.Div(
                                    "Arraste o arquivo aqui ou clique para escolher"
                                ),
                                className="fs-upload",
                                max_size=insights.LIMITE_BYTES,
                            ),  # fmt: skip
                            html.Div(id="exp-upload-msg"),
                            html.Button(
                                "Fechar",
                                id="exp-fechar",
                                className="fs-botao secundario",
                            ),
                        ],
                        className="fs-modal-caixa",
                        role="dialog",
                    )
                ],
                id="exp-modal",
                className="fs-modal",
                style=OCULTO,
            ),
            dcc.Store(id="exp-caminho", data=[]),
            dcc.Store(id="exp-endpoint"),
            dcc.Store(id="exp-dados", storage_type="memory"),
            dcc.Download(id="exp-download"),
            dcc.Download(id="exp-download-modelo"),
        ],
        className="fs-tela",
    )


def trilha(caminho: list[str]) -> list:
    """Clickable path: Explorador › economy › cpi."""
    itens = [
        html.Button(
            "Explorador",
            id={"type": "exp-trilha", "nivel": 0},
            className="fs-trilha-item",
        )
    ]
    for i, parte in enumerate(caminho, start=1):
        itens += [html.Span("›", className="fs-trilha-sep"),
                  html.Button(parte, id={"type": "exp-trilha", "nivel": i}, className="fs-trilha-item")]  # fmt: skip
    return itens


def lista(funcoes: dict, caminho: list[str], busca: str | None) -> list:
    """Folders and functions of the current level, or the search results."""
    if busca and len(busca.strip()) >= 2:
        achadas = explorador.buscar(funcoes, busca)
        if not achadas:
            return [html.P("Nenhuma função encontrada.", className="fs-vazio")]
        return [
            html.P(
                f"{len(achadas)} função encontrada"
                if len(achadas) == 1
                else f"{len(achadas)} funções encontradas",
                className="fs-exp-titulo",
            )
        ] + [_item_funcao(f, True) for f in achadas]
    pastas, aqui = explorador.filhos(funcoes, tuple(caminho))
    itens = [
        html.Button(
            [
                html.Span(nome, className="fs-exp-nome"),
                html.Span(_contagem(n), className="fs-exp-conta"),
            ],
            id={"type": "exp-pasta", "alvo": "/".join([*caminho, nome])},
            className="fs-exp-item pasta",
        )  # fmt: skip
        for nome, n in pastas
    ]
    itens += [_item_funcao(f) for f in aqui]
    return itens or [html.P("Nada neste nível.", className="fs-vazio")]


def _contagem(n: int) -> str:
    return f"{n} função" if n == 1 else f"{n} funções"


def _item_funcao(f: explorador.Funcao, caminho_completo: bool = False) -> html.Button:
    rotulo = " › ".join(f.caminho) if caminho_completo else f.caminho[-1]
    return html.Button(
        html.Span(rotulo, className="fs-exp-nome"),
        id={"type": "exp-fn", "endpoint": f.endpoint},
        className="fs-exp-item funcao",
        title=f.descricao,
    )


def ajuda(texto: str, limite: int = 120) -> str:
    """First sentence of a parameter help, cut at a word; the full text stays in the tooltip."""
    frase = texto.split(". ", maxsplit=1)[0].strip()
    if len(frase) <= limite:
        return frase if frase.endswith(".") else frase + "."
    return frase[:limite].rsplit(" ", 1)[0] + "…"


def campo(p: explorador.Parametro):
    """Form control for one parameter."""
    ident = {"type": "exp-param", "nome": p.nome}
    if p.tipo == "opcoes":
        valor = p.valor
        if p.multi and valor is not None and not isinstance(valor, list):
            valor = [v for v in str(valor).split(",") if v]
        controle = dcc.Dropdown(id=ident, options=[{"label": r, "value": v} for r, v in p.opcoes], value=valor,
                                multi=p.multi, className="fs-filtro")  # fmt: skip
    elif p.tipo == "boolean":
        controle = dcc.Checklist(id=ident, options=[{"label": "sim", "value": "true"}],
                                 value=["true"] if p.valor in (True, "true") else [])  # fmt: skip
    elif p.tipo == "number":
        controle = dcc.Input(
            id=ident, type="number", value=p.valor, className="fs-entrada"
        )
    elif p.tipo == "date":
        controle = dcc.Input(
            id=ident, type="date", value=p.valor, className="fs-entrada"
        )
    else:
        controle = dcc.Input(id=ident, type="text", value=p.valor if p.valor is not None else "", className="fs-entrada",
                             placeholder="vários valores separados por vírgula" if p.tipo == "endpoint" else "")  # fmt: skip
    rotulo = p.rotulo + (" (obrigatório)" if p.obrigatorio else "")
    return html.Div(
        [
            html.Label(rotulo, className="fs-exp-rotulo", title=p.descricao),
            controle,
            html.P(ajuda(p.descricao), className="fs-exp-ajuda", title=p.descricao)
            if p.descricao
            else None,
        ],  # fmt: skip
        className="fs-exp-campo",
    )


def resultado(df: pd.DataFrame, origem: str) -> html.Div:
    """Insights, automatic chart and the table of any result."""
    analise = insights.analisar(df)
    figura = figura_automatica(df)
    tabela = dash_table.DataTable(
        data=df.head(MAX_LINHAS).to_dict("records"),
        columns=[{"name": str(c), "id": str(c)} for c in df.columns[:30]],
        page_size=12,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "Tahoma, Verdana, sans-serif",
            "fontSize": 13,
            "padding": "6px",
            "maxWidth": 260,
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },  # fmt: skip
        style_header={"fontWeight": "bold", "backgroundColor": "#EAF1F1"},
    )
    return html.Div(
        [
            html.Div(
                [
                    html.Span(origem, className="fs-exp-selo"),
                    html.Span(
                        f"{analise.linhas} linhas, {analise.colunas} colunas",
                        className="fs-exp-conta",
                    ),
                    html.Button(
                        "Baixar CSV",
                        id="exp-baixar-csv",
                        className="fs-botao secundario",
                    ),
                ],  # fmt: skip
                className="fs-exp-acoes",
            ),
            html.Ul([html.Li(f) for f in analise.frases], className="fs-exp-insights")
            if analise.frases
            else None,
            grafico(figura) if figura is not None else None,
            html.Div(tabela, className="fs-cartao-tabela fs-pad"),
        ],
        className="fs-tela",
    )


def _parametros(ids: list[dict], valores: list) -> dict:
    """Form values keyed by parameter name; a ticked checkbox becomes "true"."""
    return {
        ident["nome"]: "true" if valor == ["true"] else valor
        for ident, valor in zip(ids, valores, strict=True)
    }


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the explorer."""
    api = client.base_url

    def funcoes():
        return explorador.catalogo(api)[0]

    @app.callback(
        Output("exp-caminho", "data"),
        Output("exp-endpoint", "data"),
        Input({"type": "exp-pasta", "alvo": ALL}, "n_clicks"),
        Input({"type": "exp-trilha", "nivel": ALL}, "n_clicks"),
        Input({"type": "exp-fn", "endpoint": ALL}, "n_clicks"),
        State("exp-caminho", "data"),
        prevent_initial_call=True,
    )
    def navegar(_pastas, _trilha, _fns, caminho):
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            return no_update, no_update
        alvo = ctx.triggered_id
        if alvo["type"] == "exp-pasta":
            return alvo["alvo"].split("/"), no_update
        if alvo["type"] == "exp-trilha":
            return (caminho or [])[: alvo["nivel"]], no_update
        f = funcoes()[alvo["endpoint"]]
        return list(f.caminho[:-1]), f.endpoint

    @app.callback(
        Output("exp-trilha", "children"),
        Output("exp-lista", "children"),
        Input("exp-caminho", "data"),
        Input("exp-busca", "value"),
    )
    def listar(caminho, busca):
        try:
            return trilha(caminho or []), lista(funcoes(), caminho or [], busca)
        except Exception as error:  # noqa: BLE001 - the API may be down
            return trilha([]), aviso(f"catálogo indisponível: {error}")

    @app.callback(
        Output("exp-ficha", "children"),
        Output("exp-provedor", "options"),
        Output("exp-provedor", "value"),
        Output("exp-painel", "style"),
        Input("exp-endpoint", "data"),
    )
    def ficha(endpoint):
        if not endpoint:
            return None, [], None, OCULTO
        f = funcoes()[endpoint]
        opcoes = [
            {"label": p + (" (pesada)" if f.pesada(p) else ""), "value": p}
            for p in f.provedores
        ]
        cabecalho = html.Div([html.H2(f.nome), html.Code(" › ".join(f.caminho)),
                              html.P(f.descricao, className="fs-explicacao")])  # fmt: skip
        return cabecalho, opcoes, f.provedores[0], VISIVEL

    @app.callback(
        Output("exp-form", "children"),
        Input("exp-endpoint", "data"),
        Input("exp-provedor", "value"),
    )
    def formulario(endpoint, provedor):
        if not endpoint or not provedor:
            return None
        f = funcoes()[endpoint]
        campos = [campo(p) for p in f.variantes.get(provedor, []) if p.visivel]
        if f.pesada(provedor):
            campos.insert(
                0,
                aviso(
                    "esta fonte carrega muitos dados na memória da API; prefira outra fonte se houver"
                ),
            )
        return campos or html.P("Esta função não tem parâmetros.", className="fs-vazio")

    @app.callback(
        Output("exp-resultado", "children", allow_duplicate=True),
        Output("exp-dados", "data", allow_duplicate=True),
        Input("exp-rodar", "n_clicks"),
        State("exp-endpoint", "data"),
        State("exp-provedor", "value"),
        State({"type": "exp-param", "nome": ALL}, "value"),
        State({"type": "exp-param", "nome": ALL}, "id"),
        prevent_initial_call=True,
    )
    def rodar(_, endpoint, provedor, valores, ids):
        params = _parametros(ids, valores)
        if provedor and provedor != "padrão":
            params["provider"] = provedor
        try:
            linhas = explorador.executar(api, endpoint, params)
        except explorador.FaltaCredencial:
            return html.Div(
                [
                    aviso(
                        "esta fonte exige uma chave de acesso que o FinScope não tem"
                    ),
                    html.P(
                        'Use "Enviar minha base" para analisar um arquivo seu com estas colunas, ou '
                        '"Ver com dados de exemplo" para conhecer a função.',
                        className="fs-explicacao",
                    ),
                ]  # fmt: skip
            ), None
        except explorador.ErroExecucao as error:
            return aviso(str(error)), None
        df = pd.json_normalize(linhas)
        return resultado(df, "Dados da API"), df.head(MAX_LINHAS).to_dict("records")

    @app.callback(
        Output("exp-resultado", "children", allow_duplicate=True),
        Output("exp-dados", "data", allow_duplicate=True),
        Input("exp-exemplo", "n_clicks"),
        State("exp-endpoint", "data"),
        State("exp-provedor", "value"),
        prevent_initial_call=True,
    )
    def exemplo(_, endpoint, provedor):
        colunas = explorador.colunas(explorador.catalogo(api)[1], endpoint, provedor)
        df = insights.exemplo(colunas)
        return resultado(df, "Dados de exemplo (fictícios)"), df.to_dict("records")

    @app.callback(
        Output("exp-modal", "style", allow_duplicate=True),
        Input("exp-abrir", "n_clicks"),
        Input("exp-fechar", "n_clicks"),
        prevent_initial_call=True,
    )
    def modal(_abrir, _fechar):
        return VISIVEL if ctx.triggered_id == "exp-abrir" else OCULTO

    @app.callback(
        Output("exp-download-modelo", "data"),
        Input("exp-modelo", "n_clicks"),
        State("exp-endpoint", "data"),
        State("exp-provedor", "value"),
        prevent_initial_call=True,
    )
    def modelo(_, endpoint, provedor):
        colunas = explorador.colunas(explorador.catalogo(api)[1], endpoint, provedor)
        nome = "modelo_" + "_".join(funcoes()[endpoint].caminho) + ".csv"
        return {"content": insights.modelo_csv(colunas), "filename": nome}

    @app.callback(
        Output("exp-upload-msg", "children"),
        Output("exp-resultado", "children", allow_duplicate=True),
        Output("exp-dados", "data", allow_duplicate=True),
        Output("exp-modal", "style", allow_duplicate=True),
        Input("exp-upload", "contents"),
        State("exp-upload", "filename"),
        State("exp-endpoint", "data"),
        State("exp-provedor", "value"),
        prevent_initial_call=True,
    )
    def enviar(conteudo, nome, endpoint, provedor):
        if not conteudo:
            return no_update, no_update, no_update, no_update
        try:
            df = insights.ler_envio(conteudo, nome or "base.csv")
        except insights.BaseInvalida as error:
            return aviso(str(error)), no_update, no_update, no_update
        esperadas = [
            c
            for c, _, _ in explorador.colunas(
                explorador.catalogo(api)[1], endpoint, provedor
            )
        ]
        faltando = insights.validar(df, esperadas) if esperadas else []
        if esperadas and len(faltando) == len(esperadas):
            return (
                aviso(
                    f"nenhuma coluna do modelo foi encontrada (esperadas: {', '.join(esperadas[:8])})"
                ),
                no_update,
                no_update,
                no_update,
            )
        nota = (
            html.P(
                f"Colunas do modelo ausentes: {', '.join(faltando)}.",
                className="fs-explicacao",
            )
            if faltando
            else None
        )
        return (
            None,
            html.Div([nota, resultado(df, f"Sua base ({nome}), não gravada")]),
            df.head(MAX_LINHAS).to_dict("records"),
            OCULTO,
        )

    @app.callback(Output("exp-download", "data"), Input("exp-baixar-csv", "n_clicks"), State("exp-dados", "data"),
                  prevent_initial_call=True)  # fmt: skip
    def baixar(n, dados):
        if not n or not dados:
            return no_update
        return {
            "content": pd.DataFrame(dados).to_csv(index=False, sep=";", decimal=","),
            "filename": "finscope_explorador.csv",
        }
