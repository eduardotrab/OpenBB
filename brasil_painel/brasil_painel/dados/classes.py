"""Class summaries for the segment screens, in the format of the models.

Credit classes (individuals by income, companies by size) read `scr_classe`
(stock); rural producers read `sicor_uf` (flow contracted per month).
"""

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

from brasil_painel.regional import (
    armazem,
    classes as cfg,
)

CARTAO = "Cartão de crédito"


class DadosAusentes(Exception):
    """A dataset was never ingested."""


@dataclass(frozen=True)
class ResumoClasse:
    """What one class column shows."""

    classe: str
    data: dt.date | None
    carteira: float = 0.0
    carteira_coop: float = 0.0
    em_dia: float = 0.0
    atraso_15_90: float = 0.0
    inadimplente: float = 0.0
    share_coop: float | None = None
    inadimplencia: float | None = None
    inadimplencia_coop: float | None = None
    atraso: float | None = None
    crescimento_12m: float | None = None
    peso_cartao: float | None = None
    tendencia: list[tuple[dt.date, float | None, float | None]] = field(
        default_factory=list
    )

    @property
    def funil(self) -> list[tuple[str, float]]:
        """Stages of the portfolio funnel."""
        return [
            ("Carteira", self.carteira),
            ("Em dia", self.em_dia),
            ("Atraso 15–90 dias", self.atraso_15_90),
            ("Inadimplente", self.inadimplente),
        ]


def _ler(nome: str) -> pd.DataFrame:
    df = armazem.ler(nome)
    if df is None:
        raise DadosAusentes(
            f"Dados de '{nome}' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    return df


def _pct(parte: float, todo: float) -> float | None:
    return parte / todo * 100 if todo else None


def com_classes(grupo: str) -> pd.DataFrame:
    """`scr_classe` rows of a group (`pf` or `pj`) with a `classe` column.

    Individuals with MEI occupation also appear as the "MEI" company class.
    """
    df = _ler("scr_classe")
    if grupo == "pf":
        df = df[df.cliente == "PF"].copy()
        df["classe"] = df.porte.map(cfg.classe_pf)
    else:
        df = df[(df.cliente == "PJ") | df.mei].copy()
        df["classe"] = [
            cfg.classe_pj(p, bool(m and c == "PF"))
            for p, m, c in zip(df.porte, df.mei, df.cliente)
        ]
    return df


def _resumo(
    classe: str, df: pd.DataFrame, data: dt.date | None, produto: str | None
) -> ResumoClasse:
    if df.empty:
        return ResumoClasse(classe, data)
    data = data or df.data.max()
    filtrado = df if produto is None else df[df.produto == produto]
    mes = filtrado[filtrado.data == data]
    carteira = mes.carteira_ativa.sum()
    if not carteira:
        return ResumoClasse(classe, data)
    coop = mes[mes.cooperativa]
    inad, venc = mes.carteira_inadimplencia.sum(), mes.vencido_15_90.sum()
    um_ano = filtrado[filtrado.data == _ano_antes(filtrado.data, data)]
    antes = um_ano.carteira_ativa.sum()
    todos_produtos = df[df.data == data]
    por_mes = filtrado.groupby("data")
    coop_mes = filtrado[filtrado.cooperativa].groupby("data")
    tendencia = [
        (
            d,
            _pct(g.carteira_inadimplencia.sum(), g.carteira_ativa.sum()),
            _pct(
                coop_mes.get_group(d).carteira_inadimplencia.sum(),
                coop_mes.get_group(d).carteira_ativa.sum(),
            )
            if d in coop_mes.groups
            else None,
        )
        for d, g in por_mes
    ]
    return ResumoClasse(
        classe,
        data,
        carteira=carteira,
        carteira_coop=coop.carteira_ativa.sum(),
        em_dia=carteira - inad - venc,
        atraso_15_90=venc,
        inadimplente=inad,
        share_coop=_pct(coop.carteira_ativa.sum(), carteira),
        inadimplencia=_pct(inad, carteira),
        inadimplencia_coop=_pct(
            coop.carteira_inadimplencia.sum(), coop.carteira_ativa.sum()
        ),
        atraso=_pct(venc, carteira),
        crescimento_12m=(carteira / antes - 1) * 100 if antes else None,
        peso_cartao=_pct(
            todos_produtos[todos_produtos.produto == CARTAO].carteira_ativa.sum(),
            todos_produtos.carteira_ativa.sum(),
        ),
        tendencia=tendencia,
    )


def _ano_antes(datas: pd.Series, data: dt.date) -> dt.date | None:
    """Latest date at least 360 days before `data`."""
    candidatas = datas[datas <= data - dt.timedelta(days=360)]
    return candidatas.max() if not candidatas.empty else None


def resumir(
    grupo: str,
    classe: str,
    *,
    uf: str | None = None,
    produto: str | None = None,
    data: dt.date | None = None,
) -> ResumoClasse:
    """Summary of one class, optionally for one UF and one product."""
    df = com_classes(grupo)
    if uf:
        df = df[df.uf == uf]
    data = data or (df.data.max() if not df.empty else None)
    return _resumo(classe, df[df.classe == classe], data, produto)


def todas(grupo: str, **filtros) -> list[ResumoClasse]:
    """Every class of a group in display order (same reference date)."""
    df = com_classes(grupo)
    if filtros.get("uf"):
        df = df[df.uf == filtros["uf"]]
    data = filtros.get("data") or df.data.max()
    return [
        _resumo(c, df[df.classe == c], data, filtros.get("produto"))
        for c in cfg.ordem(grupo)
    ]


@dataclass(frozen=True)
class ResumoRural:
    """What a producer column shows (credit contracted in the month)."""

    classe: str
    data: dt.date | None
    valor: float = 0.0
    valor_coop: float = 0.0
    valor_sicoob: float = 0.0
    contratos: float = 0.0
    share_coop: float | None = None
    share_sicoob: float | None = None
    ticket_medio: float | None = None
    crescimento_12m: float | None = None
    finalidades: list[tuple[str, float]] = field(default_factory=list)
    tendencia: list[tuple[dt.date, float, float]] = field(default_factory=list)


_FINALIDADES = [
    ("Custeio", "valor_custeio"),
    ("Investimento", "valor_investimento"),
    ("Comercialização", "valor_comercializacao"),
    ("Industrialização", "valor_industrializacao"),
]


def resumir_rural(
    classe: str, *, uf: str | None = None, data: dt.date | None = None
) -> ResumoRural:
    """Summary of one producer class from SICOR."""
    df = _ler("sicor_uf")
    df = df[df.porte == classe]
    if uf:
        df = df[df.uf == uf]
    if df.empty:
        return ResumoRural(classe, data)
    colunas = [c for _, c in _FINALIDADES]
    df = df.assign(valor=df[colunas].sum(axis=1))
    data = data or df.data.max()
    mes = df[df.data == data]
    valor = mes.valor.sum()
    antes = df[df.data == _ano_antes(df.data, data)].valor.sum()
    por_mes = df.groupby("data")
    return ResumoRural(
        classe,
        data,
        valor=valor,
        valor_coop=mes[mes.cooperativa].valor.sum(),
        valor_sicoob=mes[mes.sicoob].valor.sum(),
        contratos=mes.contratos.sum(),
        share_coop=_pct(mes[mes.cooperativa].valor.sum(), valor),
        share_sicoob=_pct(mes[mes.sicoob].valor.sum(), valor),
        ticket_medio=valor / mes.contratos.sum() if mes.contratos.sum() else None,
        crescimento_12m=(valor / antes - 1) * 100 if antes else None,
        finalidades=[(nome, mes[c].sum()) for nome, c in _FINALIDADES],
        tendencia=[
            (d, g.valor.sum(), g[g.cooperativa].valor.sum()) for d, g in por_mes
        ],
    )


def todas_rurais(**filtros) -> list[ResumoRural]:
    """Every producer class in display order."""
    return [resumir_rural(c, **filtros) for c in cfg.ordem("rural")]
