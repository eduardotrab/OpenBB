"""Credit cooperative systems compared (IF.data quarterly summary).

Only singular cooperatives (segment B3S) are summed: the centrals hold their
affiliates' pooled funds, so adding them would count the same money twice.
"""

import datetime as dt

import pandas as pd

from brasil_painel.regional import (
    armazem,
    classes as cfg,
)

OUTRAS = "Outras ou não identificadas"
CONTAS = {
    "Ativo Total": "ativo",
    "Carteira de Crédito": "carteira",
    "Captações": "captacoes",
    "Patrimônio Líquido": "pl",
    "Lucro Líquido": "lucro",
}


class DadosAusentes(Exception):
    """The IF.data dataset was never ingested."""


def sistema(nome: str, cnpj: str) -> str:
    """System of a cooperative: official exception first, then a brand word in the name."""
    excecoes = cfg.configuracao().get("sistemas_excecoes", {})
    if cnpj in excecoes:
        return excecoes[cnpj]
    nome = nome.upper()
    for rotulo, palavra in cfg.configuracao()["sistemas"].items():
        if palavra in nome:
            return rotulo
    return OUTRAS


def ordem_sistemas() -> list[str]:
    """Systems in display order (Sicoob first), then the unidentified."""
    return [*cfg.configuracao()["sistemas"], OUTRAS]


def largo(df: pd.DataFrame) -> pd.DataFrame:
    """One row per singular cooperative and quarter, with the summary accounts as columns."""
    singulares = df[(df.segmento == "B3S") & df.conta.isin(CONTAS)]
    t = singulares.pivot_table(
        index=["data", "instituicao", "nome", "uf", "municipio"],
        columns="conta",
        values="valor",
        aggfunc="sum",
    ).rename(columns=CONTAS)
    t = t.reindex(columns=list(CONTAS.values())).reset_index()
    t["sistema"] = [sistema(n, c) for n, c in zip(t.nome, t.instituicao, strict=True)]
    return t


def base(uf: str | None = None) -> pd.DataFrame:
    """Read the stored IF.data in the wide format, optionally for one state."""
    df = armazem.ler("ifdata_coop")
    if df is None:
        raise DadosAusentes(
            "Dados do IF.data ainda não foram baixados: rode `painel-dados atualizar ifdata`."
        )
    t = largo(df)
    return t[t.uf == uf] if uf else t


def _fator_anual(data: dt.date) -> int:
    """IF.data profit accumulates within the half-year: ×2 in June and December, ×4 in March and September."""
    return 2 if data.month in (6, 12) else 4


def _ano_antes(datas, data: dt.date) -> dt.date | None:
    alvo = [d for d in datas if (data.year - d.year) * 12 + data.month - d.month == 12]
    return alvo[0] if alvo else None


def por_sistema(t: pd.DataFrame, data: dt.date | None = None) -> pd.DataFrame:
    """One row per system on the quarter: size, share, 12-month credit growth, return on equity."""
    if t.empty:
        return pd.DataFrame()
    data = data or t.data.max()
    agora = t[t.data == data]
    soma = agora.groupby("sistema")[
        ["ativo", "carteira", "captacoes", "pl", "lucro"]
    ].sum(min_count=1)
    soma["singulares"] = agora.groupby("sistema").instituicao.nunique()
    soma["share_ativo"] = soma.ativo / soma.ativo.sum() * 100
    soma["roe"] = soma.lucro * _fator_anual(data) / soma.pl.where(soma.pl > 0) * 100
    soma["carteira_captacoes"] = (
        soma.carteira / soma.captacoes.where(soma.captacoes > 0) * 100
    )
    antes = _ano_antes(sorted(set(t.data)), data)
    if antes is not None:
        passado = t[t.data == antes].groupby("sistema").carteira.sum()
        soma["cresc_carteira"] = (soma.carteira / passado.where(passado > 0) - 1) * 100
    else:
        soma["cresc_carteira"] = float("nan")
    return soma.reindex([s for s in ordem_sistemas() if s in soma.index])


def participacao(t: pd.DataFrame) -> pd.DataFrame:
    """Share of each system in the singulars' total assets, quarter by quarter (columns = systems)."""
    soma = t.groupby(["data", "sistema"]).ativo.sum().unstack(fill_value=0)
    return soma.div(soma.sum(axis=1), axis=0) * 100


def ranking(t: pd.DataFrame, data: dt.date | None = None) -> pd.DataFrame:
    """Singulars on the quarter, largest assets first, with 12-month credit growth."""
    if t.empty:
        return t
    data = data or t.data.max()
    agora = t[t.data == data].set_index("instituicao")
    antes = _ano_antes(sorted(set(t.data)), data)
    if antes is not None:
        passado = t[t.data == antes].set_index("instituicao").carteira
        agora = agora.assign(
            cresc_carteira=(agora.carteira / passado.where(passado > 0) - 1) * 100
        )
    else:
        agora = agora.assign(cresc_carteira=float("nan"))
    agora = agora.assign(
        roe=agora.lucro * _fator_anual(data) / agora.pl.where(agora.pl > 0) * 100
    )
    return agora.sort_values("ativo", ascending=False).reset_index()
