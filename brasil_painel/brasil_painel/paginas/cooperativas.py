"""Credit cooperative systems compared: Sicoob against Sicredi, Cresol, Unicred and the others."""

import re

import pandas as pd
from dash import Dash, Input, Output, dcc, html

from brasil_painel import marca
from brasil_painel.componentes import fs
from brasil_painel.componentes.blocos import aviso, carregando
from brasil_painel.componentes.graficos import (
    figura_linhas,
    figura_participacao_sistemas,
)
from brasil_painel.dados import (
    cooperativas as coop,
    formato,
)
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.dados.indicadores import Ponto
from brasil_painel.paginas.segmento import CONFIG_MINI, filtros_da_tela
from brasil_painel.regional.ufs import NOMES

UFS = set(NOMES)

RANKING = 20
SICOOB = "Sicoob"


def layout() -> html.Div:
    """Return the page body."""
    return html.Div(
        [
            html.Div(id="coop-contexto", className="fs-contexto"),
            html.Section(
                [
                    html.H2("Sistemas cooperativos"),
                    carregando(html.Div(id="coop-sistemas")),
                ],
                className="secao",
            ),
            html.Section(
                [
                    html.H2(id="coop-ranking-titulo"),
                    carregando(html.Div(id="coop-ranking")),
                ],
                className="secao",
            ),
        ],
        className="fs-tela",
    )


def _pct(v, casas: int = 1) -> str:
    return "sem dado" if v is None or pd.isna(v) else f"{formato.numero(v, casas)}%"


def _em(lugar: str) -> str:
    return "no Brasil" if lugar == "Brasil" else f"em {lugar}"


def _singulares(n: int) -> str:
    return f"{n} singular" if n == 1 else f"{n} singulares"


def _reais(v) -> str:
    return "sem dado" if v is None or pd.isna(v) else f"R$ {formato.compacto(v)}"


MINUSCULAS = {"De", "Do", "Da", "Dos", "Das", "E", "Em"}
MARCAS = [palavra for palavra in coop.cfg.configuracao()["sistemas"].values()]


def nome_curto(nome: str) -> str:
    """Trade name of a cooperative, from its legal name.

    The part with a system brand wins (SICOOB CREDICOM - COOPERATIVA … or
    COOPERATIVA … - SICREDI DEXIS); otherwise a short part that is not the legal form.
    """
    partes = [p.strip() for p in nome.split(" - ") if p.strip()]
    com_marca = [p for p in partes if any(m in p.upper() for m in MARCAS)]
    curtas = [
        p for p in partes if len(p) <= 60 and not p.upper().startswith("COOPERATIVA")
    ]
    escolhido = (com_marca or curtas or [nome])[0]
    palavras = escolhido.title().removesuffix(" Ltda.").removesuffix(" Ltda").split()
    palavras = [
        p.lower() if i and p in MINUSCULAS else p for i, p in enumerate(palavras)
    ]
    texto = " ".join(palavras)
    # state codes such as "Mt/Pa" or "Rs" back to capitals
    return re.sub(
        r"\b([A-Z][a-z])(?=(/|\b))",
        lambda m: m.group(1).upper() if m.group(1).upper() in UFS else m.group(1),
        texto,
    )


def _tabela(
    linhas: list, colunas: list[tuple[str, str, object]], classe_linha
) -> html.Table:
    """Table from (title, kind, cell) columns; kind is "nome" (row header), "num" or "texto".

    A column with no data at all is left out.
    """
    visiveis = [
        c for c in colunas if any(c[2](linha) != "sem dado" for linha in linhas)
    ]

    def celula(tipo, valor):
        if tipo == "nome":
            return html.Th(valor, scope="row")
        return html.Td(valor, className="num" if tipo == "num" else "")

    corpo = [
        html.Tr(
            [celula(tipo, f(linha)) for _, tipo, f in visiveis],
            className=classe_linha(linha),
        )
        for linha in linhas
    ]
    return html.Table(
        [html.Thead(html.Tr([html.Th(t) for t, _, _ in visiveis])), html.Tbody(corpo)],
        className="fs-matriz",
    )


def tabela_sistemas(s: pd.DataFrame) -> html.Table:
    """One row per system; Sicoob highlighted."""
    linhas = [linha.rename(sistema) for sistema, linha in s.iterrows()]
    colunas = [
        ("Sistema", "nome", lambda r: r.name),
        ("Singulares", "num", lambda r: f"{int(r.singulares)}"),
        ("Ativo", "num", lambda r: _reais(r.ativo)),
        ("Participação no ativo", "num", lambda r: _pct(r.share_ativo)),
        ("Carteira de crédito", "num", lambda r: _reais(r.carteira)),
        (
            "Crescimento da carteira em 12 meses",
            "num",
            lambda r: _pct(r.cresc_carteira),
        ),
        ("Carteira sobre captações", "num", lambda r: _pct(r.carteira_captacoes, 0)),
        ("Rentabilidade do patrimônio (ao ano)", "num", lambda r: _pct(r.roe)),
    ]
    return _tabela(
        linhas, colunas, lambda r: "fs-linha-brasil" if r.name == SICOOB else ""
    )


def bloco_sistemas(t: pd.DataFrame, lugar: str) -> html.Div:
    """KPIs of Sicoob, the systems table, the share chart and, with history, the share over time."""
    s = coop.por_sistema(t)
    if s.empty:
        return html.P(
            f"Nenhuma cooperativa singular {_em(lugar)}.", className="fs-vazio"
        )
    total_roe = s.lucro.sum() * coop._fator_anual(t.data.max()) / s.pl.sum() * 100
    kpis = []
    if SICOOB in s.index:
        sicoob = s.loc[SICOOB]
        kpis = [
            fs.kpi("Sicoob no ativo das singulares", sicoob.share_ativo, unidade="%", casas=1,
                   nota=f"{_singulares(int(sicoob.singulares))} {_em(lugar)}"),
            fs.kpi("Rentabilidade do Sicoob", sicoob.roe, unidade="% ao ano", casas=1,
                   nota=f"todas as singulares: {_pct(total_roe)}"),
        ]  # fmt: skip
    partes = [html.Div(kpis, className="fs-kpis")] if kpis else []
    partes.append(html.Div(tabela_sistemas(s), className="fs-cartao-tabela"))
    graficos = [html.Div([html.P("Participação no ativo das singulares", className="fs-mini-titulo"),
                          dcc.Graph(figure=figura_participacao_sistemas(s.share_ativo.to_dict()), config=CONFIG_MINI)], className="fs-cartao-grafico")]  # fmt: skip
    p = coop.participacao(t)
    if len(p) >= 2:
        principais = [
            x
            for x in (SICOOB, "Sicredi", "Cresol", "Unicred", coop.OUTRAS)
            if x in p.columns
        ]
        series = {n: [Ponto(d, v) for d, v in p[n].items()] for n in principais}
        cores = dict(zip(principais, marca.CATEGORICA, strict=False))
        graficos.append(html.Div([html.P("Participação no tempo", className="fs-mini-titulo"),
                                  dcc.Graph(figure=figura_linhas(series, "%", cores=cores, casas=1), config=CONFIG_MINI)],
                                 className="fs-cartao-grafico"))  # fmt: skip
    partes.append(html.Div(graficos, className="fs-grade-produtos fs-meio"))
    return html.Div(partes)


def tabela_ranking(r: pd.DataFrame) -> html.Table:
    """Largest singulars; Sicoob rows highlighted."""
    linhas = [
        linha.rename(i)
        for i, (_, linha) in enumerate(r.head(RANKING).iterrows(), start=1)
    ]
    colunas = [
        ("", "texto", lambda x: str(x.name)),
        ("Cooperativa", "nome", lambda x: nome_curto(x.nome)),
        ("Sistema", "texto", lambda x: x.sistema),
        ("Sede", "texto", lambda x: f"{x.municipio} ({x.uf})"),
        ("Ativo", "num", lambda x: _reais(x.ativo)),
        (
            "Crescimento da carteira em 12 meses",
            "num",
            lambda x: _pct(x.cresc_carteira),
        ),
        ("Rentabilidade do patrimônio (ao ano)", "num", lambda x: _pct(x.roe)),
    ]
    tabela = _tabela(
        linhas, colunas, lambda x: "fs-linha-sicoob" if x.sistema == SICOOB else ""
    )
    tabela.className = "fs-matriz fs-matriz-nichos"
    return tabela


def register(app: Dash, client: OpenBBClient) -> None:
    """Callbacks of the page."""

    @app.callback(
        Output("coop-contexto", "children"),
        Output("coop-sistemas", "children"),
        Output("coop-ranking-titulo", "children"),
        Output("coop-ranking", "children"),
        Input("filtros", "data"),
    )
    def desenhar(filtros):
        uf = filtros_da_tela(filtros)["uf"]
        lugar = NOMES.get(uf, "Brasil") if uf else "Brasil"
        try:
            t = coop.base(uf)
        except coop.DadosAusentes as error:
            return aviso(str(error)), None, "Maiores singulares", None
        if t.empty:
            return (
                f"{lugar}: sem cooperativas singulares no IF.data.",
                None,
                "Maiores singulares",
                None,
            )
        data = t.data.max()
        agora = t[t.data == data]
        outras = agora[agora.sistema == coop.OUTRAS]
        contexto = [
            html.P(f"{lugar}, balanços de {formato.data(data)} (IF.data, BCB). Só cooperativas singulares; as centrais "
                   "ficam de fora para não contar duas vezes o dinheiro das filiadas. A rentabilidade anualiza o lucro "
                   "acumulado no semestre."),
            html.P(f"O sistema vem do nome da cooperativa. {_singulares(len(outras))} ({_reais(outras.ativo.sum())} de ativo, "
                   f"{_pct(outras.ativo.sum() / agora.ativo.sum() * 100)} do total) não trazem o sistema no nome e ficam "
                   f"em \"{coop.OUTRAS}\" até a lista oficial de filiação ser carregada.", className="aviso"),
        ]  # fmt: skip
        return (
            contexto,
            bloco_sistemas(t, lugar),
            f"Maiores singulares {_em(lugar)}",
            html.Div(tabela_ranking(coop.ranking(t)), className="fs-cartao-tabela"),
        )
