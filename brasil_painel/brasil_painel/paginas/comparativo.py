"""Every class side by side against Brazil: matrix, risk × growth and rural."""

from dash import Dash, Input, Output, dcc, html

from brasil_painel.componentes.blocos import aviso, carregando, grafico
from brasil_painel.componentes.graficos import figura_posicionamento
from brasil_painel.dados import (
    classes as dados_classes,
    comparativo,
    formato,
)
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.paginas.rural import mes_sicor
from brasil_painel.paginas.segmento import TODOS, filtros_da_tela
from brasil_painel.regional import classes as cfg
from brasil_painel.regional.ufs import NOMES

# (header, attribute, decimals, risk: higher than Brazil is worse)
COLUNAS = [
    ("Carteira", "carteira", None, False),
    ("Share das cooperativas", "share_coop", 1, False),
    ("Inadimplência", "inadimplencia", 2, True),
    ("Inadimplência nas cooperativas", "inadimplencia_coop", 2, True),
    ("Atraso de 15 a 90 dias", "atraso", 2, True),
    ("Crescimento em 12 meses", "crescimento_12m", 1, False),
    ("Peso do cartão", "peso_cartao", 1, False),
]
RUIM, BOM = (180, 67, 44), (0, 54, 65)  # terracotta above Brazil, dark green below


def cor_risco(valor: float | None, base: float | None, escala: float) -> str | None:
    """Cell background by distance to Brazil (diverging, light enough for dark text)."""
    if valor is None or base is None or not escala:
        return None
    intensidade = min(abs(valor - base) / escala, 1) * 0.32
    r, g, b = RUIM if valor > base else BOM
    return f"rgba({r}, {g}, {b}, {intensidade:.2f})"


def _celula(valor, casas, risco, base, escala) -> html.Td:
    if valor is None:
        return html.Td("sem dado", className="num vazio")
    if casas is None:
        return html.Td(f"R$ {formato.compacto(valor)}", className="num")
    texto = f"{formato.numero(valor, casas)}%"
    if risco and base is not None and abs(valor - base) > 1e-9:
        texto = f"{'▲' if valor > base else '▼'} {texto}"
    cor = cor_risco(valor, base, escala) if risco else None
    estilo = {"background": cor} if cor and abs(valor - base) > 1e-9 else None
    return html.Td(texto, className="num", style=estilo)


def matriz(linhas: list[comparativo.Linha]) -> html.Table:
    """Classes in rows, indicators in columns; Brazil first as the reference."""
    brasil = linhas[0].resumo
    escalas = {}
    for _, attr, _, risco in COLUNAS:
        if risco:
            base = getattr(brasil, attr)
            difs = [abs(getattr(item.resumo, attr) - base) for item in linhas[1:]
                    if getattr(item.resumo, attr) is not None and base is not None]  # fmt: skip
            escalas[attr] = max(difs, default=0)
    corpo, grupo_atual = [], None
    for linha in linhas:
        if linha.grupo not in ("Brasil", grupo_atual):
            grupo_atual = linha.grupo
            corpo.append(
                html.Tr(
                    html.Th(
                        grupo_atual,
                        colSpan=len(COLUNAS) + 1,
                        className="fs-grupo-linha",
                    )
                )
            )
        r = linha.resumo
        corpo.append(
            html.Tr(
                [html.Th(r.classe, scope="row")]
                + [
                    _celula(
                        getattr(r, attr),
                        casas,
                        risco,
                        getattr(brasil, attr),
                        escalas.get(attr),
                    )
                    for _, attr, casas, risco in COLUNAS
                ],
                className="fs-linha-brasil" if linha.grupo == "Brasil" else None,
            )
        )
    cabecalho = html.Tr([html.Th("Classe")] + [html.Th(t) for t, *_ in COLUNAS])
    return html.Table([html.Thead(cabecalho), html.Tbody(corpo)], className="fs-matriz")


def bloco_rural(rurais: list[dados_classes.ResumoRural]) -> html.Table:
    """Rural credit contracted in the month (flow), Brazil first."""
    cabecalho = html.Tr(
        [
            html.Th(t)
            for t in (
                "Porte",
                "Contratado no mês",
                "Share das cooperativas",
                "Share do Sicoob",
                "Ticket médio",
                "Contra o mesmo mês do ano anterior",
            )
        ]  # fmt: skip
    )

    def pct(v):
        return f"{formato.numero(v, 1)}%" if v is not None else "sem dado"

    corpo = [
        html.Tr(
            [
                html.Th(r.classe, scope="row"),
                html.Td(f"R$ {formato.compacto(r.valor)}", className="num"),
                html.Td(pct(r.share_coop), className="num"),
                html.Td(pct(r.share_sicoob), className="num"),
                html.Td(
                    f"R$ {formato.compacto(r.ticket_medio)}"
                    if r.ticket_medio
                    else "sem dado",
                    className="num",
                ),
                html.Td(pct(r.crescimento_12m), className="num"),
            ],
            className="fs-linha-brasil" if i == 0 else None,
        )
        for i, r in enumerate(rurais)
    ]
    return html.Table([html.Thead(cabecalho), html.Tbody(corpo)], className="fs-matriz")


def layout() -> html.Div:
    """Return the page body."""
    produtos = [{"label": "Todos os produtos", "value": TODOS}] + [
        {"label": nome, "value": nome} for nome, _ in cfg.PRODUTOS
    ]
    return html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(
                        id="comp-produto",
                        options=produtos,
                        value=TODOS,
                        clearable=False,
                        className="fs-filtro fs-filtro-produto",
                    ),  # fmt: skip
                    html.P(
                        "Cada classe contra o Brasil. A cor aparece só nos indicadores de risco: "
                        "terracota quando a classe está pior que o Brasil, verde-escuro quando está melhor.",
                        className="fs-explicacao",
                    ),
                ],
                className="fs-barra-tela",
            ),
            html.Div(id="comp-contexto", className="fs-contexto"),
            carregando(html.Div(id="comp-matriz", className="fs-cartao-tabela")),
            html.Section(
                [
                    html.H2("Onde cada classe está: risco e crescimento"),
                    carregando(html.Div(id="comp-posicionamento")),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2("Rural: crédito contratado no mês"),
                    carregando(html.Div(id="comp-rural", className="fs-cartao-tabela")),
                ],
                className="secao",
            ),
        ],
        className="fs-tela",
    )


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(
        Output("comp-matriz", "children"),
        Output("comp-posicionamento", "children"),
        Output("comp-rural", "children"),
        Output("comp-contexto", "children"),
        Input("comp-produto", "value"),
        Input("filtros", "data"),
    )
    def preencher(produto, filtros):
        kwargs = filtros_da_tela(filtros)
        try:
            linhas = comparativo.tabela(produto=produto or None, **kwargs)
            rurais = comparativo.rurais(uf=kwargs["uf"], data=mes_sicor(kwargs["data"]))
        except dados_classes.DadosAusentes as error:
            return aviso(str(error)), None, None, None
        data = linhas[0].resumo.data
        lugar = NOMES.get(kwargs["uf"], "Brasil") if kwargs["uf"] else "Brasil"
        contexto = (
            f"{lugar}, {produto or 'todos os produtos'}. Carteira de "
            f"{formato.data(data, mensal=True) if data else 'mês sem dado'} (SCR.data)."
        )
        return (
            matriz(linhas),
            grafico(figura_posicionamento(linhas)),
            bloco_rural(rurais),
            contexto,
        )
