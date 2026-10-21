"""Products: credit by product, rates by lender (Sicoob vs market) and payment cards."""

from dash import Dash, Input, Output, dcc, html

from brasil_painel.componentes import fs
from brasil_painel.componentes.blocos import aviso, carregando, grafico
from brasil_painel.componentes.graficos import (
    figura_ranking_juros,
    figura_share_produtos,
    figura_tendencia,
)
from brasil_painel.dados import (
    classes as dados_classes,
    formato,
    produtos,
)
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.paginas.mapa import _opcoes_classe
from brasil_painel.paginas.segmento import CONFIG_MINI, TODOS, filtros_da_tela
from brasil_painel.regional.ufs import NOMES

SEGMENTOS_JUROS = {"PESSOA FÍSICA": "PF", "PESSOA JURÍDICA": "PJ"}


def _opcoes_modalidade() -> list[dict]:
    try:
        pares = produtos.modalidades()
    except dados_classes.DadosAusentes:
        return []
    return [
        {"label": f"{SEGMENTOS_JUROS.get(s, s)}: {m}", "value": f"{s}|{m}"}
        for s, m in pares
    ]


def tabela_produtos(resumos: list[dados_classes.ResumoClasse]) -> html.Table:
    """Credit by product: portfolio, growth, default and cooperatives' share."""

    def pct(v, casas=1):
        return f"{formato.numero(v, casas)}%" if v is not None else "sem dado"

    cabecalho = html.Tr([html.Th(t) for t in ("Produto", "Carteira", "Crescimento em 12 meses", "Inadimplência",
                                               "Inadimplência nas cooperativas", "Share das cooperativas")])  # fmt: skip
    corpo = [
        html.Tr(
            [
                html.Th(r.classe, scope="row"),
                html.Td(f"R$ {formato.compacto(r.carteira)}", className="num"),
                html.Td(pct(r.crescimento_12m), className="num"),
                html.Td(pct(r.inadimplencia, 2), className="num"),
                html.Td(pct(r.inadimplencia_coop, 2), className="num"),
                html.Td(pct(r.share_coop), className="num"),
            ]
        )
        for r in resumos
    ]
    return html.Table([html.Thead(cabecalho), html.Tbody(corpo)], className="fs-matriz")


def layout() -> html.Div:
    """Return the page body."""
    modalidades = _opcoes_modalidade()
    return html.Div(
        [
            html.Section(
                [
                    html.H2("Crédito por produto"),
                    html.Div(
                        dcc.Dropdown(
                            id="prod-classe",
                            options=_opcoes_classe(),
                            value=TODOS,
                            clearable=False,
                            className="fs-filtro fs-filtro-classe",
                        ),  # fmt: skip
                        className="fs-barra-tela",
                    ),
                    html.Div(id="prod-contexto", className="fs-contexto"),
                    html.Div(
                        [
                            carregando(
                                html.Div(id="prod-tabela", className="fs-cartao-tabela")
                            ),
                            html.Div(
                                [
                                    html.P(
                                        "Share das cooperativas por produto",
                                        className="fs-mini-titulo",
                                    ),
                                    carregando(html.Div(id="prod-share")),
                                ],  # fmt: skip
                                className="fs-cartao-grafico",
                            ),
                        ],
                        className="fs-grade-produtos",
                    ),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2("Juros praticados: Banco Sicoob e mercado"),
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="prod-modalidade",
                                options=modalidades,
                                value=modalidades[0]["value"] if modalidades else None,
                                clearable=False,
                                className="fs-filtro fs-filtro-modalidade",
                            ),  # fmt: skip
                            html.P(
                                "Taxa média ao mês por instituição, no primeiro período do mês. Fonte: BCB.",
                                className="fs-explicacao",
                            ),  # fmt: skip
                        ],
                        className="fs-barra-tela",
                    ),
                    carregando(html.Div(id="prod-juros")),
                ],
                className="secao",
            ),
            html.Section(
                [html.H2("Cartões"), carregando(html.Div(id="prod-cartoes"))],
                className="secao",
            ),
        ],
        className="fs-tela",
    )


def bloco_juros(j: produtos.Juros) -> html.Div:
    """KPIs, ranking and the Sicoob vs. median trend of one product."""
    if j.inicio is None:
        return aviso("sem taxas para esta modalidade")
    kpis = html.Div(
        [
            fs.kpi(
                "Banco Sicoob",
                j.sicoob_taxa,
                unidade="% a.m.",
                casas=2,
                nota=f"{j.sicoob_posicao}º de {len(j.ranking)}"
                if j.sicoob_posicao
                else "não aparece nesta modalidade",
            ),  # fmt: skip
            fs.kpi("Mediana do mercado", j.mediana, unidade="% a.m.", casas=2),
            fs.kpi(
                "Menor taxa",
                j.ranking[0][2] if j.ranking else None,
                unidade="% a.m.",
                casas=2,
                nota=j.ranking[0][1].title() if j.ranking else "",
            ),  # fmt: skip
        ],
        className="fs-faixa",
    )
    tendencia = [(d, med, sic) for d, med, sic in j.serie]
    return html.Div(
        [
            kpis,
            html.Div(
                [
                    html.Div(
                        [
                            html.P(
                                f"Ranking em {formato.data(j.inicio)}",
                                className="fs-mini-titulo",
                            ),
                            grafico(figura_ranking_juros(j)),
                        ],
                        className="fs-cartao-grafico",
                    ),  # fmt: skip
                    html.Div(
                        [
                            html.P(
                                "Banco Sicoob e mediana do mercado (% a.m.)",
                                className="fs-mini-titulo",
                            ),
                            dcc.Graph(
                                figure=figura_tendencia(
                                    tendencia,
                                    rotulos=("Mediana do mercado", "Banco Sicoob"),
                                ),
                                config=CONFIG_MINI,
                                style={"height": "220px"},
                            ),  # fmt: skip
                        ],
                        className="fs-cartao-grafico",
                    ),
                ],
                className="fs-grade-produtos",
            ),
        ]
    )


def bloco_cartoes(c: produtos.Cartoes) -> html.Div:
    """Activation by card function, brand shares and the credit activation trend."""
    return html.Div(
        [
            html.Div(
                [
                    fs.kpi(
                        f"Cartões de {f.lower()} ativos",
                        ativos / 1e6,
                        unidade="mi",
                        casas=1,
                        nota=f"{formato.numero(ativacao, 1)}% dos {formato.compacto(emitidos)} emitidos",
                    )  # fmt: skip
                    for f, emitidos, ativos, ativacao in c.funcoes
                ],
                className="fs-faixa",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.P(
                                "Bandeiras nos cartões de crédito ativos",
                                className="fs-mini-titulo",
                            ),
                            fs.barras_comparativas(
                                [(b, v, "sistema") for b, v in c.bandeiras[:6]],
                                percentual=True,
                            ),
                        ],
                        className="fs-cartao-grafico fs-pad",
                    ),
                    html.Div(
                        [
                            html.P(
                                "Ativação dos cartões de crédito (% ativos)",
                                className="fs-mini-titulo",
                            ),
                            dcc.Graph(
                                figure=figura_tendencia(
                                    [(d, v, None) for d, v in c.serie_ativacao],
                                    rotulos=("Ativação", ""),
                                ),
                                config=CONFIG_MINI,
                                style={"height": "220px"},
                            ),
                        ],
                        className="fs-cartao-grafico",
                    ),
                ],
                className="fs-grade-produtos",
            ),
            html.P(
                f"Dado do trimestre encerrado em {formato.data(c.data, mensal=True)}. Fonte: BCB, meios de pagamento.",
                className="fs-contexto",
            ),  # fmt: skip
        ]
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(
        Output("prod-tabela", "children"),
        Output("prod-share", "children"),
        Output("prod-contexto", "children"),
        Input("prod-classe", "value"),
        Input("filtros", "data"),
    )
    def credito(classe, filtros):
        recorte = filtros_da_tela(filtros)
        try:
            resumos = produtos.por_produto(classe=classe or None, **recorte)
            total = dados_classes.resumir_total(**recorte)
        except dados_classes.DadosAusentes as error:
            return aviso(str(error)), None, None
        lugar = NOMES.get(recorte["uf"], "Brasil") if recorte["uf"] else "Brasil"
        data = total.data
        contexto = f"{lugar}, {classe or 'todas as classes'}. Carteira de {formato.data(data, mensal=True) if data else 'mês sem dado'} (SCR.data)."
        return (
            tabela_produtos(resumos),
            grafico(figura_share_produtos(resumos, total.share_coop)),
            contexto,
        )

    @app.callback(Output("prod-juros", "children"), Input("prod-modalidade", "value"))
    def taxas(valor):
        if not valor:
            return aviso(
                "taxas de juros ainda não foram baixadas: rode `painel-dados atualizar juros`"
            )
        segmento, modalidade = valor.split("|", 1)
        try:
            return bloco_juros(produtos.juros(segmento, modalidade))
        except dados_classes.DadosAusentes as error:
            return aviso(str(error))

    @app.callback(Output("prod-cartoes", "children"), Input("atualizar", "n_intervals"))
    def cartoes(_):
        try:
            return bloco_cartoes(produtos.cartoes())
        except dados_classes.DadosAusentes as error:
            return aviso(str(error))
