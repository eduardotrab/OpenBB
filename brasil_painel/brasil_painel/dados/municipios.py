"""Municipal indicators of one state, against the state median.

Reads the municipal datasets (`ibge_municipio`, `pix_municipio`,
`estban_municipio`, `sicor_municipio`) and builds one table per state.
"""

import datetime as dt
import functools
import json
from dataclasses import dataclass

import pandas as pd

from brasil_painel.regional import armazem, malha


class DadosAusentes(Exception):
    """A municipal dataset was never ingested."""


@dataclass(frozen=True)
class Indicador:
    """One municipal indicator as the screen shows it."""

    nome: str
    unidade: str
    casas: int
    fonte: str
    nota: str = ""
    divergente: bool = False  # growth rates: colors around the state median


INDICADORES = {
    "pix_pj_pc": Indicador("Pix recebido por empresas, por habitante", "R$ no mês", 0, "BCB (Pix)",
                           "Sinal de faturamento local."),
    "pix_pj_cresc": Indicador("Crescimento do Pix recebido por empresas", "% em 12 meses", 1, "BCB (Pix)",
                              "Últimos 3 meses contra os mesmos meses do ano anterior.", divergente=True),
    "pix_pf_pc": Indicador("Pix recebido por pessoas, por habitante", "R$ no mês", 0, "BCB (Pix)"),
    "credito_pc": Indicador("Crédito bancário por habitante", "R$ mil", 1, "BCB (ESTBAN)",
                            "Saldo das agências de bancos no município; não inclui as cooperativas singulares."),
    "credito_cresc": Indicador("Crescimento do crédito bancário", "% em 12 meses", 1, "BCB (ESTBAN)",
                               "Saldo das agências de bancos no município.", divergente=True),
    "poupanca_pc": Indicador("Poupança por habitante", "R$ mil", 1, "BCB (ESTBAN)",
                             "Depósitos de poupança nas agências de bancos do município."),
    "rural_12m": Indicador("Crédito rural contratado em 12 meses", "R$ mi", 1, "BCB (SICOR)",
                           "Custeio e investimento, todas as instituições, inclusive cooperativas."),
    "rural_pequeno": Indicador("Parte do Pronaf no crédito rural", "%", 1, "BCB (SICOR)",
                               "Pequeno produtor (Pronaf) no custeio e investimento dos últimos 12 meses."),
    "pib_pc": Indicador("PIB por habitante", "R$ mil", 1, "IBGE", "PIB de 2023 dividido pela população estimada mais recente."),
    "populacao": Indicador("População", "habitantes", 0, "IBGE"),
}  # fmt: skip


@functools.cache
def nomes() -> dict[str, tuple[str, str]]:
    """IBGE code → (name, UF)."""
    return {
        codigo: (nome, uf)
        for codigo, (nome, uf) in json.loads(malha.LISTA.read_text()).items()
    }


def _ler(nome: str, uf: str, obrigatorio: bool = False) -> pd.DataFrame:
    """Rows of one state; a missing optional dataset reads as empty (its indicators show no data)."""
    df = armazem.ler(nome)
    if df is None and not obrigatorio:
        return pd.DataFrame(columns=armazem.SCHEMA_MUNICIPAL.names)
    if df is None:
        raise DadosAusentes(
            f"Dados de '{nome}' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    return df[df.uf == uf]


def _largo(df: pd.DataFrame, data) -> pd.DataFrame:
    """Pivot one date: indicators as columns, municipalities as rows."""
    return df[df.data == data].pivot_table(
        index="municipio", columns="indicador", values="valor", aggfunc="sum"
    )


def _meses_antes(data: dt.date, meses: int) -> dt.date:
    total = data.year * 12 + data.month - 1 - meses
    return dt.date(total // 12, total % 12 + 1, 1)


def _crescimento(agora: pd.Series, antes: pd.Series) -> pd.Series:
    return (agora / antes.where(antes > 0) - 1) * 100


def tabela(
    uf: str, data: dt.date | None = None
) -> tuple[pd.DataFrame, dict[str, dt.date]]:
    """Every indicator of every municipality of `uf`, and the reference date of each source.

    `data` (the global date filter) caps the monthly sources.
    """
    ibge = _ler("ibge_municipio", uf, obrigatorio=True)
    pix = _ler("pix_municipio", uf)
    estban = _ler("estban_municipio", uf)
    rural = _ler("sicor_municipio", uf)
    if data:
        pix, estban, rural = (d[d.data <= data] for d in (pix, estban, rural))
    codigos = [c for c, (_, u) in nomes().items() if u == uf]
    t = pd.DataFrame(index=pd.Index(codigos, name="municipio"))
    t["nome"] = [nomes()[c][0] for c in codigos]
    datas = {}

    pop = ibge[ibge.indicador == "populacao"]
    pop = pop[pop.data == pop.data.max()].set_index("municipio").valor
    pib = ibge[ibge.indicador == "pib"]
    datas["pib"] = pib.data.max()
    t["populacao"] = pop
    t["pib_pc"] = (
        pib[pib.data == datas["pib"]].set_index("municipio").valor / pop / 1000
    )

    if not pix.empty:
        ultimo = pix.data.max()
        datas["pix"] = ultimo
        recebido = pix[pix.indicador.isin(["pix_recebido_pf", "pix_recebido_pj"])]
        mes = _largo(recebido, ultimo)
        t["pix_pf_pc"] = mes.get("pix_recebido_pf") / pop
        t["pix_pj_pc"] = mes.get("pix_recebido_pj") / pop
        pj = recebido[recebido.indicador == "pix_recebido_pj"]
        recentes = [_meses_antes(ultimo, i) for i in range(3)]
        um_ano = [_meses_antes(m, 12) for m in recentes]
        soma = pj.groupby(["municipio", "data"]).valor.sum().unstack()
        if all(m in soma.columns for m in recentes + um_ano):
            t["pix_pj_cresc"] = _crescimento(
                soma[recentes].sum(axis=1), soma[um_ano].sum(axis=1)
            )

    if not estban.empty:
        ultimo = estban.data.max()
        datas["estban"] = ultimo
        agora = _largo(estban, ultimo)
        t["credito_pc"] = agora.get("credito") / pop / 1000
        t["poupanca_pc"] = agora.get("poupanca") / pop / 1000
        um_ano = _meses_antes(ultimo, 12)
        if um_ano in set(estban.data):
            t["credito_cresc"] = _crescimento(
                agora.get("credito"), _largo(estban, um_ano).get("credito")
            )

    if not rural.empty:
        ultimo = rural.data.max()
        datas["sicor"] = ultimo
        janela = rural[rural.data > _meses_antes(ultimo, 12)]
        total = janela.groupby("municipio").valor.sum()
        pequeno = (
            janela[janela.indicador.str.endswith("_pequeno")]
            .groupby("municipio")
            .valor.sum()
        )
        t["rural_12m"] = total / 1e6
        t["rural_pequeno"] = (
            pequeno.reindex(total.index).fillna(0) / total.where(total > 0) * 100
        )

    for chave in INDICADORES:
        if chave not in t:
            t[chave] = float("nan")
    return t, datas


def mediana(t: pd.DataFrame, chave: str) -> float | None:
    """State reference: the median municipality (half above, half below)."""
    valor = t[chave].median()
    return None if pd.isna(valor) else float(valor)


def posicao(t: pd.DataFrame, chave: str, municipio: str) -> tuple[int, int] | None:
    """Rank of a municipality (1 = highest) among those with data."""
    serie = t[chave].dropna().sort_values(ascending=False)
    if municipio not in serie.index:
        return None
    return list(serie.index).index(municipio) + 1, len(serie)
