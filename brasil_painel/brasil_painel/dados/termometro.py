"""Credit thermometer by state: a transparent composite score.

Each component becomes the state's distance to the mean of the 27 states in
standard deviations (capped), signed so that positive is better; the score is
50 plus 10 times the weighted sum, and every component shows its points.
"""

import datetime as dt
import functools
from pathlib import Path

import pandas as pd
import tomllib

from brasil_painel.regional import armazem
from brasil_painel.regional.ufs import BRASIL, NOMES

ARQUIVO = Path(__file__).with_name("termometro.toml")
LIMITE = 2.5  # standard deviations; one extreme state must not dominate
ESCALA = 10  # points per standard deviation


class DadosAusentes(Exception):
    """A dataset of the thermometer was never ingested."""


@functools.cache
def configuracao() -> dict:
    """Components with label, unit, direction and initial weight."""
    return tomllib.loads(ARQUIVO.read_text(encoding="utf-8"))


def notas(
    componentes: pd.DataFrame, config: dict | None = None, pesos: dict | None = None
) -> tuple[pd.Series, pd.DataFrame]:
    """Score (0 to 100) and points per component for each state (rows of `componentes`)."""
    config = config or configuracao()
    pesos = {k: float((pesos or {}).get(k, c["peso"])) for k, c in config.items()}
    total = sum(pesos.values()) or 1.0
    pontos = pd.DataFrame(index=componentes.index)
    for chave, c in config.items():
        serie = componentes[chave]
        desvio = serie.std(ddof=0)
        z = (serie - serie.mean()) / desvio if desvio else serie * 0
        z = z.clip(-LIMITE, LIMITE).fillna(0)
        if c["melhor"] == "menor":
            z = -z
        pontos[chave] = ESCALA * pesos[chave] / total * z
    nota = (50 + pontos.sum(axis=1)).clip(0, 100)
    return nota, pontos


def _ler(nome: str) -> pd.DataFrame:
    df = armazem.ler(nome)
    if df is None:
        raise DadosAusentes(
            f"Dados de '{nome}' ainda não foram baixados: rode `painel-dados atualizar`."
        )
    return df


def _meses_antes(data: dt.date, meses: int) -> dt.date:
    total = data.year * 12 + data.month - 1 - meses
    return dt.date(total // 12, total % 12 + 1, data.day if meses % 12 == 0 else 1)


def _anterior(datas, data, meses: int):
    """Latest stored date at least `meses` months before `data`."""
    limite = data - dt.timedelta(days=meses * 30 - 5)
    candidatas = [d for d in datas if d <= limite]
    return max(candidatas) if candidatas else None


def componentes(data: dt.date | None = None) -> tuple[pd.DataFrame, dict[str, dt.date]]:
    """Raw value of every component for the 27 states and Brazil ("BR"), and the date of each source."""
    scr = _ler("scr_uf")
    if data:
        scr = scr[scr.data <= data]
    por_uf = scr.groupby(["data", "uf"])[
        ["carteira_ativa", "carteira_inadimplencia", "vencido_15_90"]
    ].sum()
    brasil = por_uf.groupby(level="data").sum()
    brasil.index = pd.MultiIndex.from_product(
        [brasil.index, [BRASIL]], names=["data", "uf"]
    )
    tudo = pd.concat([por_uf, brasil])
    datas = sorted(set(tudo.index.get_level_values("data")))
    ultima = datas[-1]

    def taxa(d, coluna):
        mes = tudo.xs(d, level="data")
        return mes[coluna] / mes.carteira_ativa * 100

    c = pd.DataFrame(index=[*sorted(NOMES), BRASIL])
    c["inadimplencia"] = taxa(ultima, "carteira_inadimplencia")
    um_ano, tres = _anterior(datas, ultima, 12), _anterior(datas, ultima, 3)
    c["inadimplencia_12m"] = (
        c.inadimplencia - taxa(um_ano, "carteira_inadimplencia")
        if um_ano
        else float("nan")
    )
    c["atraso_3m"] = (
        taxa(ultima, "vencido_15_90") - taxa(tres, "vencido_15_90")
        if tres
        else float("nan")
    )
    c["carteira"] = (
        (
            tudo.xs(ultima, level="data").carteira_ativa
            / tudo.xs(um_ano, level="data").carteira_ativa
            - 1
        )
        * 100
        if um_ano
        else float("nan")
    )
    fontes = {"scr": ultima}

    desemprego = _ler("desemprego_uf")
    if data:
        desemprego = desemprego[desemprego.data <= data]
    fontes["desemprego"] = desemprego.data.max()
    c["desemprego"] = (
        desemprego[desemprego.data == fontes["desemprego"]].set_index("uf").valor
    )

    pix = _ler("pix_uf")
    pix = pix[pix.indicador == "pix_recebido_pj"]
    if data:
        pix = pix[pix.data <= data]
    soma = pix.pivot_table(index="uf", columns="data", values="valor", aggfunc="sum")
    meses = sorted(soma.columns)
    fontes["pix"] = meses[-1]
    recentes = meses[-3:]
    um_ano_antes = [_meses_antes(m, 12) for m in recentes]
    if all(m in soma.columns for m in um_ano_antes):
        c["pix_pj"] = (
            soma[recentes].sum(axis=1) / soma[um_ano_antes].sum(axis=1) - 1
        ) * 100
    else:
        c["pix_pj"] = float("nan")
    return c[list(configuracao())], fontes


def calcular(data: dt.date | None = None, pesos: dict | None = None):
    """Components, score and points of the 27 states (Brazil kept apart for reference)."""
    c, fontes = componentes(data)
    estados = c.drop(index=BRASIL)
    nota, pontos = notas(estados, pesos=pesos)
    return c, nota, pontos, fontes
