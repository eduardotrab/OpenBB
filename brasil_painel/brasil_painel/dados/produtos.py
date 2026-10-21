"""Product views: credit by product, interest rates by lender and payment cards (plan 16)."""

import datetime as dt
from dataclasses import dataclass, field

from brasil_painel.dados import classes
from brasil_painel.regional import (
    armazem,
    classes as cfg,
)

SICOOB = "SICOOB"


def por_produto(
    *, uf: str | None = None, classe: str | None = None, data: dt.date | None = None
) -> list[classes.ResumoClasse]:
    """One summary per credit product (largest portfolio first)."""
    if classe:
        grupo = "pf" if classe in cfg.ordem("pf") else "pj"
        df = classes.com_classes(grupo)
        df = df[df.classe == classe]
    else:
        df = classes._ler("scr_classe")
    if uf:
        df = df[df.uf == uf]
    if df.empty:
        return []
    data = data or df.data.max()
    nomes = [n for n, _ in cfg.PRODUTOS] + [cfg.OUTROS]
    resumos = [classes._resumo(n, df, data, n) for n in nomes]
    return sorted(
        (r for r in resumos if r.carteira), key=lambda r: r.carteira, reverse=True
    )


@dataclass(frozen=True)
class Juros:
    """Rates of one product in the latest window, with the Sicoob bank highlighted."""

    segmento: str
    modalidade: str
    inicio: dt.date | None
    ranking: list[tuple[int, str, float]] = field(
        default_factory=list
    )  # position, lender, % a.m.
    mediana: float | None = None
    sicoob_taxa: float | None = None
    sicoob_posicao: int | None = None
    serie: list[tuple[dt.date, float, float | None]] = field(
        default_factory=list
    )  # date, median, Sicoob


def modalidades() -> list[tuple[str, str]]:
    """(segment, product) pairs present in the latest window, Sicoob ones first."""
    df = armazem.ler("juros_if")
    if df is None:
        raise classes.DadosAusentes(
            "Dados de 'juros_if' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    ultimo = df[df.inicio == df.inicio.max()]
    com_sicoob = set(
        ultimo[ultimo.instituicao.str.upper().str.contains(SICOOB)][
            ["segmento", "modalidade"]
        ].itertuples(index=False)
    )
    pares = sorted(set(ultimo[["segmento", "modalidade"]].itertuples(index=False)))
    return [tuple(p) for p in sorted(pares, key=lambda p: (p not in com_sicoob, p))]


def juros(segmento: str, modalidade: str) -> Juros:
    """Ranking, market median and the Sicoob bank for one product."""
    df = armazem.ler("juros_if")
    if df is None:
        raise classes.DadosAusentes(
            "Dados de 'juros_if' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    df = df[(df.segmento == segmento) & (df.modalidade == modalidade)]
    if df.empty:
        return Juros(segmento, modalidade, None)
    inicio = df.inicio.max()
    atual = df[df.inicio == inicio].sort_values("posicao")
    sicoob = atual[atual.instituicao.str.upper().str.contains(SICOOB)]
    serie = []
    for d, g in df.groupby("inicio"):
        s = g[g.instituicao.str.upper().str.contains(SICOOB)]
        serie.append(
            (
                d,
                float(g.taxa_mes.median()),
                float(s.taxa_mes.iloc[0]) if not s.empty else None,
            )
        )
    return Juros(
        segmento,
        modalidade,
        inicio,
        ranking=list(zip(atual.posicao, atual.instituicao, atual.taxa_mes)),
        mediana=float(atual.taxa_mes.median()),
        sicoob_taxa=float(sicoob.taxa_mes.iloc[0]) if not sicoob.empty else None,
        sicoob_posicao=int(sicoob.posicao.iloc[0]) if not sicoob.empty else None,
        serie=serie,
    )


@dataclass(frozen=True)
class Cartoes:
    """Payment cards in the latest quarter."""

    data: dt.date | None
    funcoes: list[tuple[str, float, float, float]] = field(
        default_factory=list
    )  # function, issued, active, activation %
    bandeiras: list[tuple[str, float]] = field(
        default_factory=list
    )  # brand, share of active credit cards %
    serie_ativacao: list[tuple[dt.date, float]] = field(
        default_factory=list
    )  # credit activation % by quarter


def cartoes() -> Cartoes:
    """Activation by function, brand shares and the credit activation trend."""
    df = armazem.ler("cartoes")
    if df is None:
        raise classes.DadosAusentes(
            "Dados de 'cartoes' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    data = df.data.max()
    atual = df[df.data == data]
    por_funcao = atual.groupby("funcao")[["emitidos", "ativos"]].sum()
    funcoes = [
        (f, r.emitidos, r.ativos, r.ativos / r.emitidos * 100 if r.emitidos else 0.0)
        for f, r in por_funcao.sort_values("emitidos", ascending=False).iterrows()
    ]
    credito = atual[atual.funcao == "Crédito"].groupby("bandeira").ativos.sum()
    bandeiras = (
        [
            (b, v / credito.sum() * 100)
            for b, v in credito.sort_values(ascending=False).items()
        ]
        if credito.sum()
        else []
    )
    serie_credito = (
        df[df.funcao == "Crédito"].groupby("data")[["emitidos", "ativos"]].sum()
    )
    serie = [
        (d, r.ativos / r.emitidos * 100)
        for d, r in serie_credito.iterrows()
        if r.emitidos
    ]
    return Cartoes(data, funcoes, bandeiras, serie)
