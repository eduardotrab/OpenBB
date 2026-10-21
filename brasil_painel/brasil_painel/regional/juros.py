"""BCB interest rates by product and lender (5-business-day windows, plan 16).

Windows start every business day, so one window per month is kept: the first
one starting in the month. That gives a monthly series of rates and ranks.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
import pyarrow as pa
import requests

from brasil_painel.regional import armazem, olinda

NOME = "juros_if"
CAMINHO = "taxaJuros/versao/v2/odata/TaxasJurosDiariaPorInicioPeriodo"
CHAVE = ["inicio", "segmento", "modalidade", "instituicao"]
SCHEMA = pa.schema(
    [
        ("inicio", pa.date32()),
        ("segmento", pa.string()),
        ("modalidade", pa.string()),
        ("instituicao", pa.string()),
        ("posicao", pa.int64()),
        ("taxa_mes", pa.float64()),
        ("taxa_ano", pa.float64()),
    ]
)
MESES = 13


def primeiro_inicio(ano: int, mes: int, sessao: requests.Session) -> str | None:
    """First window start date within a month (None when not published)."""
    ini = dt.date(ano, mes, 1)
    linhas = olinda.consultar(
        CAMINHO,
        {
            "$filter": f"InicioPeriodo ge '{ini.isoformat()}' and InicioPeriodo le '{(ini + dt.timedelta(days=9)).isoformat()}'",
            "$select": "InicioPeriodo",
            "$orderby": "InicioPeriodo asc",
            "$top": "1",
        },
        sessao,
    )
    return linhas[0]["InicioPeriodo"] if linhas else None


def tabela(linhas: list[dict]) -> pd.DataFrame:
    """Olinda rows → the `juros_if` schema."""
    if not linhas:
        return pd.DataFrame(columns=SCHEMA.names)
    df = pd.DataFrame(linhas).rename(
        columns={
            "InicioPeriodo": "inicio",
            "Segmento": "segmento",
            "Modalidade": "modalidade",
            "InstituicaoFinanceira": "instituicao",
            "Posicao": "posicao",
            "TaxaJurosAoMes": "taxa_mes",
            "TaxaJurosAoAno": "taxa_ano",
        }
    )
    df["inicio"] = pd.to_datetime(df.inicio).dt.date
    df["posicao"] = df.posicao.astype("int64")
    df["taxa_mes"] = df.taxa_mes.astype(float)
    df["taxa_ano"] = df.taxa_ano.astype(float)
    return df[SCHEMA.names].drop_duplicates(CHAVE, keep="last")


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Keep the first window of each of the last 13 months (only missing ones are fetched)."""
    hoje = hoje or dt.date.today()
    sessao = sessao or requests.Session()
    existente = armazem.ler(NOME, pasta)
    meses_guardados = (
        {(d.year, d.month) for d in existente.inicio}
        if existente is not None
        else set()
    )
    partes = [existente] if existente is not None else []
    mes = hoje.replace(day=1)
    for i in range(MESES):
        alvo = (mes.year, mes.month)
        if alvo not in meses_guardados or i < 2:  # the last two may still change
            inicio = primeiro_inicio(*alvo, sessao)
            if inicio:
                partes.append(
                    tabela(
                        olinda.consultar(
                            CAMINHO, {"$filter": f"InicioPeriodo eq '{inicio}'"}, sessao
                        )
                    )
                )
        mes = (mes - dt.timedelta(days=1)).replace(day=1)
    df = pd.concat(partes, ignore_index=True)
    corte = (hoje.replace(day=1) - dt.timedelta(days=31 * MESES)).replace(day=1)
    df = (
        df[df.inicio >= corte]
        .drop_duplicates(CHAVE, keep="last")
        .sort_values(CHAVE, ignore_index=True)
    )
    armazem.gravar(df, NOME, SCHEMA, pasta)
    return df.rename(columns={"inicio": "data"})
