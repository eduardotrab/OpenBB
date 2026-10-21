"""What moved most in 12 months: classes, states and products (Visão 360°)."""

import datetime as dt
from dataclasses import dataclass, field

from brasil_painel.dados import classes, comparativo, regional
from brasil_painel.regional import (
    armazem,
    classes as cfg,
)
from brasil_painel.regional.ufs import BRASIL, NOMES


@dataclass(frozen=True)
class Item:
    """One line of a highlight list."""

    rotulo: str
    valor: float | None
    variacao: float
    href: str


@dataclass(frozen=True)
class Destaques:
    """The four highlight lists of the opening screen."""

    classes_piora: list[Item] = field(default_factory=list)
    ufs_piora: list[Item] = field(default_factory=list)
    produtos_alta: list[Item] = field(default_factory=list)
    produtos_baixa: list[Item] = field(default_factory=list)


def classes_que_pioraram(linhas: list[comparativo.Linha], n: int = 3) -> list[Item]:
    """Classes whose default rate rose most in 12 months (p.p.)."""
    itens = []
    for linha in linhas:
        if linha.grupo == "Brasil":
            continue
        variacao = classes.variacao_12m(linha.resumo.tendencia)
        if variacao is not None and variacao > 0:
            href = "/pessoas" if linha.grupo == "Pessoas" else "/empresas"
            itens.append(
                Item(
                    f"{linha.grupo}: {linha.resumo.classe}",
                    linha.resumo.inadimplencia,
                    variacao,
                    href,
                )
            )
    return sorted(itens, key=lambda i: i.variacao, reverse=True)[:n]


def ufs_que_pioraram(foto: regional.Retrato, n: int = 3) -> list[Item]:
    """States whose default rate rose most in 12 months (p.p.)."""
    itens = [
        Item(NOMES[uf], foto.valores.get(uf), v, "/mapa")
        for uf, v in foto.variacao_12m.items()
        if uf != BRASIL and v > 0
    ]
    return sorted(itens, key=lambda i: i.variacao, reverse=True)[:n]


def produtos_por_crescimento(
    uf: str | None = None, data: dt.date | None = None, n: int = 3
) -> tuple[list[Item], list[Item]]:
    """Products with the largest and the smallest 12-month portfolio growth (%)."""
    df = classes._ler("scr_classe")
    if uf:
        df = df[df.uf == uf]
    data = data or df.data.max()
    antes = classes._ano_antes(df.data, data)
    if antes is None:
        return [], []
    agora = df[df.data == data].groupby("produto").carteira_ativa.sum()
    passado = df[df.data == antes].groupby("produto").carteira_ativa.sum()
    crescimento = ((agora / passado - 1) * 100).dropna()
    itens = [
        Item(p, agora[p], v, "/produtos")
        for p, v in crescimento.items()
        if passado[p] > 0 and p != cfg.OUTROS  # "Outros" is a remainder, not a product
    ]
    itens.sort(key=lambda i: i.variacao, reverse=True)
    return itens[:n], list(reversed(itens[-n:]))


def calcular(uf: str | None = None, data: dt.date | None = None) -> Destaques:
    """All highlight lists for the opening screen."""
    linhas = comparativo.tabela(uf=uf, data=data)
    serie = regional.serie("inadimplencia")
    if data:
        serie = serie[serie.data <= data]
    alta, baixa = produtos_por_crescimento(uf, data)
    return Destaques(
        classes_piora=classes_que_pioraram(linhas),
        ufs_piora=ufs_que_pioraram(regional.retrato(serie)),
        produtos_alta=alta,
        produtos_baixa=baixa,
    )


@dataclass(frozen=True)
class Credito:
    """Credit strip of the opening screen."""

    total: classes.ResumoClasse
    pix_mes: float | None
    pix_data: dt.date | None


def faixa_credito(uf: str | None = None, data: dt.date | None = None) -> Credito:
    """Whole-system credit summary plus the Pix paid in the latest month."""
    total = classes.resumir_total(uf=uf, data=data)
    pix = armazem.ler("pix_uf")
    pix_mes = pix_data = None
    if pix is not None:
        pix = pix[
            (pix.uf == (uf or BRASIL))
            & pix.indicador.isin(["pix_pago_pf", "pix_pago_pj"])
        ]
        if data:
            pix = pix[pix.data <= data]
        if not pix.empty:
            pix_data = pix.data.max()
            pix_mes = pix[pix.data == pix_data].valor.sum()
    return Credito(total, pix_mes, pix_data)
