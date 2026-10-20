"""IBGE series by UF and Brazil, through the local OpenBB API (`ibge/aggregates`)."""

import datetime as dt
from pathlib import Path

import pandas as pd

from brasil_painel.config import Settings
from brasil_painel.dados.api import OpenBBClient
from brasil_painel.regional import armazem
from brasil_painel.regional.ufs import BRASIL, SIGLAS

# dataset → (table, variable, periods, quarterly)
SERIES = {
    "desemprego": (4099, 4099, "-8", True),  # PNAD Contínua, quarterly rate (%)
    "populacao": (6579, 9324, "-1", False),  # yearly population estimate
}


def data_do_periodo(periodo: str, trimestral: bool) -> dt.date:
    """'YYYYQQ' → first day of the quarter's last month; 'YYYY'; 'YYYYMM'."""
    ano = int(periodo[:4])
    if len(periodo) == 4:
        return dt.date(ano, 1, 1)
    numero = int(periodo[4:])
    return dt.date(ano, numero * 3 if trimestral else numero, 1)


def longo(linhas: list[dict], indicador: str, trimestral: bool = True) -> pd.DataFrame:
    """Rows of `ibge/aggregates` (levels N1 and N3) in the long format."""
    registros = [
        {
            "data": data_do_periodo(r["period"], trimestral),
            "uf": BRASIL if r["level"] == "N1" else SIGLAS[int(r["location_id"])],
            "indicador": indicador,
            "valor": float(r["value"]),
        }
        for r in linhas
        if r.get("value") is not None
    ]
    return armazem.ordenar_longo(pd.DataFrame(registros))


def _atualizar(
    nome: str, pasta: Path | None, client: OpenBBClient | None
) -> pd.DataFrame:
    tabela, variavel, periodos, trimestral = SERIES[nome]
    client = client or OpenBBClient(Settings.from_env().api_url, ttl_segundos=0)
    linhas = []
    for nivel in ("N1", "N3"):
        linhas += client.get(
            "ibge/aggregates",
            table=str(tabela),
            variables=str(variavel),
            periods=periodos,
            level=nivel,
            locations="all",
        )
    df = longo(linhas, nome, trimestral)
    armazem.gravar(df, f"{nome}_uf", armazem.SCHEMA_LONGO, pasta)
    return df


def atualizar_desemprego(anos=None, pasta=None, client=None) -> pd.DataFrame:
    """Store the unemployment rate by UF and Brazil (last 8 quarters)."""
    return _atualizar("desemprego", pasta, client)


def atualizar_populacao(anos=None, pasta=None, client=None) -> pd.DataFrame:
    """Store the population estimate by UF and Brazil (for per-capita figures)."""
    return _atualizar("populacao", pasta, client)
