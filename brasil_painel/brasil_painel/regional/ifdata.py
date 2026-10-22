"""BCB IF.data: quarterly summary (Resumo) of every credit cooperative.

Fetched through the local API (`bcb/ifdata`, provider `bcb`, which caches the
slow Olinda service for 7 days). The system of each cooperative (Sicoob,
Sicredi, ...) is worked out when reading (`dados/cooperativas.py`), so the
exception list can change without fetching again.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
import pyarrow as pa

from brasil_painel.config import Settings
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.regional import armazem

NOME = "ifdata_coop"
TRIMESTRES = 9  # the latest quarter and two years back
SCHEMA = pa.schema(
    [
        ("data", pa.date32()),
        ("instituicao", pa.string()),
        ("nome", pa.string()),
        ("uf", pa.string()),
        ("municipio", pa.string()),
        ("segmento", pa.string()),
        ("conta", pa.string()),
        ("valor", pa.float64()),
    ]
)
CHAVE = ["data", "instituicao", "conta"]


def trimestres(ultimo: dt.date, n: int) -> list[str]:
    """'YYYYMM' of the latest quarter end and the n-1 before it."""
    mes = ultimo.year * 12 + ultimo.month - 1
    return [f"{(mes - 3 * i) // 12}{(mes - 3 * i) % 12 + 1:02d}" for i in range(n)]


def _linhas(resultados: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "data": dt.date.fromisoformat(r["period"]),
                "instituicao": str(r["institution"]),
                "nome": r["name"] or "",
                "uf": r["uf"] or "",
                "municipio": r["city"] or "",
                "segmento": r["segment"] or "",
                "conta": r["column"],
                "valor": float(r["value"]),
            }
            for r in resultados
            if r.get("value") is not None
        ],
        columns=SCHEMA.names,
    )
    return df


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    client: OpenBBClient | None = None,
    trimestres_: int = TRIMESTRES,
) -> pd.DataFrame:
    """Fetch the latest quarter and the stored-missing ones before it; store.

    A quarter the BCB fails to serve is skipped (kept from the store, if any).
    """
    client = client or OpenBBClient(
        Settings.from_env().api_url, ttl_segundos=0, timeout=900
    )
    ultimo = _linhas(client.get("bcb/ifdata", report="1"))
    if ultimo.empty:
        raise FonteIndisponivel("IF.data não devolveu o último trimestre")
    existente = armazem.ler(NOME, pasta)
    guardados = (
        {f"{d:%Y%m}" for d in existente.data} if existente is not None else set()
    )
    partes = ([existente] if existente is not None else []) + [ultimo]
    for periodo in trimestres(ultimo.data.max(), trimestres_)[1:]:
        if periodo in guardados:
            continue
        try:
            partes.append(_linhas(client.get("bcb/ifdata", report="1", period=periodo)))
        except FonteIndisponivel:
            continue
    df = pd.concat(partes, ignore_index=True).drop_duplicates(CHAVE, keep="last")
    primeiro = trimestres(ultimo.data.max(), trimestres_)[-1]
    df = df[[f"{d:%Y%m}" >= primeiro for d in df.data]]
    df = df.sort_values(CHAVE, ignore_index=True)
    armazem.gravar(df, NOME, SCHEMA, pasta)
    return df
