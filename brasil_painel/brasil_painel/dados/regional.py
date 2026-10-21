"""Map indicators by UF computed from the regional store (ADR 0006).

Every series has a "BR" row taken from the national total, never from an
average of the states.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from brasil_painel.dados import classes as dados_classes
from brasil_painel.regional import (
    armazem,
    classes as cfg,
)
from brasil_painel.regional.ufs import BRASIL

FILTROS_SCR = ("cliente", "segmento", "classe", "produto")


class DadosAusentes(Exception):
    """A dataset was never ingested."""


@dataclass(frozen=True)
class Indicador:
    """How an indicator is labelled, coloured and computed."""

    nome: str
    unidade: str
    fonte: str
    calcular: Callable[..., pd.DataFrame]
    casas: int = 2
    divergente: bool = False  # above Brazil is worse → diverging scale
    filtros: tuple[str, ...] = ()
    nota: str = ""


def _ler(nome: str) -> pd.DataFrame:
    df = armazem.ler(nome)
    if df is None:
        raise DadosAusentes(
            f"Dados de '{nome}' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    return df


def _scr(cliente: str, segmento: str, recorte: dict | None = None) -> pd.DataFrame:
    """Credit rows filtered by client type, segment and, optionally, class/product.

    Class or product filters need the detailed `scr_classe`; otherwise the
    small per-UF dataset is enough.
    """
    recorte = recorte or {}
    classe, produto = recorte.get("classe"), recorte.get("produto")
    if classe or produto:
        df = _ler("scr_classe")
        if classe:
            grupo = "pf" if classe in cfg.ordem("pf") else "pj"
            df = dados_classes.com_classes(grupo)
            df = df[df.classe == classe]
        if produto:
            df = df[df.produto == produto]
    else:
        df = _ler("scr_uf")
    if cliente != "todos":
        df = df[df.cliente == cliente]
    if segmento == "cooperativas":
        df = df[df.cooperativa]
    return df


def _com_brasil(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Sum by date × UF and add the national total as UF "BR"."""
    por_uf = df.groupby(["data", "uf"], as_index=False)[colunas].sum()
    brasil = df.groupby("data", as_index=False)[colunas].sum().assign(uf=BRASIL)
    return pd.concat([por_uf, brasil], ignore_index=True)


def _populacao() -> pd.Series:
    pop = _ler("populacao_uf")
    return pop[pop.data == pop.data.max()].set_index("uf").valor


def _resultado(df: pd.DataFrame, valor: pd.Series) -> pd.DataFrame:
    return (
        df.assign(valor=valor)[["data", "uf", "valor"]]
        .dropna()
        .sort_values(["uf", "data"], ignore_index=True)
    )


def _inadimplencia(
    cliente: str, segmento: str, recorte: dict | None = None
) -> pd.DataFrame:
    df = _com_brasil(
        _scr(cliente, segmento, recorte), ["carteira_ativa", "carteira_inadimplencia"]
    )
    return _resultado(df, df.carteira_inadimplencia / df.carteira_ativa * 100)


def _carteira_per_capita(
    cliente: str, segmento: str, recorte: dict | None = None
) -> pd.DataFrame:
    df = _com_brasil(_scr(cliente, segmento, recorte), ["carteira_ativa"])
    return _resultado(df, df.carteira_ativa / df.uf.map(_populacao()))


def _participacao_coop(
    cliente: str, _segmento: str, recorte: dict | None = None
) -> pd.DataFrame:
    scr = _scr(cliente, "todos", recorte)
    total = _com_brasil(scr, ["carteira_ativa"])
    coop = _com_brasil(scr[scr.cooperativa], ["carteira_ativa"])
    df = total.merge(coop, on=["data", "uf"], how="left", suffixes=("", "_coop"))
    return _resultado(df, df.carteira_ativa_coop.fillna(0) / df.carteira_ativa * 100)


def _longo(nome: str, indicador: str, por_habitantes: float | None = None):
    def calcular(
        _cliente: str, _segmento: str, _recorte: dict | None = None
    ) -> pd.DataFrame:
        df = _ler(nome)
        df = df[df.indicador == indicador]
        valor = df.valor
        if por_habitantes:
            valor = valor / df.uf.map(_populacao()) * por_habitantes
        return _resultado(df, valor)

    return calcular


INDICADORES = {
    "inadimplencia": Indicador(
        "Inadimplência de crédito (> 90 dias)",
        "%",
        "BCB, SCR.data",
        _inadimplencia,
        divergente=True,
        filtros=FILTROS_SCR,
        nota="Carteira vencida há mais de 90 dias ÷ carteira ativa.",
    ),
    "carteira_per_capita": Indicador(
        "Carteira de crédito por habitante",
        "R$",
        "BCB, SCR.data; IBGE (população)",
        _carteira_per_capita,
        casas=0,
        filtros=FILTROS_SCR,
    ),
    "participacao_coop": Indicador(
        "Participação das cooperativas na carteira",
        "%",
        "BCB, SCR.data",
        _participacao_coop,
        casas=1,
        filtros=("cliente", "classe", "produto"),
    ),
    "pix_pago_pf": Indicador(
        "Pix pago por pessoas físicas, por habitante (mês)",
        "R$",
        "BCB, Pix por município; IBGE (população)",
        _longo("pix_uf", "pix_pago_pf", por_habitantes=1),
        casas=0,
        nota="Pelo município de quem paga.",
    ),
    "pix_recebido_pj": Indicador(
        "Pix recebido por empresas, por habitante (mês)",
        "R$",
        "BCB, Pix por município; IBGE (população)",
        _longo("pix_uf", "pix_recebido_pj", por_habitantes=1),
        casas=0,
        nota="Proxy do faturamento das empresas, pelo município de quem recebe.",
    ),
    "maquininhas": Indicador(
        "Maquininhas (POS) por mil habitantes",
        "por mil hab.",
        "BCB, meios de pagamento; IBGE (população)",
        _longo("maquininhas_uf", "maquininhas_pos", por_habitantes=1000),
        casas=0,
    ),
    "desemprego": Indicador(
        "Desemprego",
        "%",
        "IBGE, PNAD Contínua (trimestral)",
        _longo("desemprego_uf", "desemprego"),
        casas=1,
        divergente=True,
    ),
}


def serie(
    indicador: str,
    cliente: str = "todos",
    segmento: str = "todos",
    *,
    classe: str | None = None,
    produto: str | None = None,
) -> pd.DataFrame:
    """Columns data, uf, valor (including "BR")."""
    recorte = {"classe": classe, "produto": produto}
    return INDICADORES[indicador].calcular(cliente, segmento, recorte)


@dataclass(frozen=True)
class Retrato:
    """The latest date of a series: values by UF, Brazil and 12-month change."""

    data: dt.date
    valores: dict[str, float]
    brasil: float | None
    variacao_12m: dict[str, float]


def retrato(df: pd.DataFrame) -> Retrato:
    """Latest date; the change compares with the last date ≥ 360 days before."""
    ultima = df.data.max()
    atual = df[df.data == ultima].set_index("uf").valor
    anteriores = df[df.data <= ultima - dt.timedelta(days=360)]
    variacao = {}
    if not anteriores.empty:
        antes = (
            anteriores[anteriores.data == anteriores.data.max()].set_index("uf").valor
        )
        variacao = (atual - antes).dropna().to_dict()
    return Retrato(
        data=ultima,
        valores=atual.drop(BRASIL, errors="ignore").to_dict(),
        brasil=atual.get(BRASIL),
        variacao_12m=variacao,
    )


def ranking(foto: Retrato) -> list[tuple[str, float]]:
    """UFs from the highest value down, with Brazil in its place."""
    linhas = list(foto.valores.items())
    if foto.brasil is not None:
        linhas.append((BRASIL, foto.brasil))
    return sorted(linhas, key=lambda x: x[1], reverse=True)
