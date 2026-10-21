"""Payment cards issued and active by function and brand (BCB, quarterly)."""

import datetime as dt
from pathlib import Path

import pandas as pd
import pyarrow as pa
import requests

from brasil_painel.regional import armazem, olinda

NOME = "cartoes"
CAMINHO = "MPV_DadosAbertos/versao/v1/odata/Quantidadeetransacoesdecartoes(trimestre=@trimestre)"
CHAVE = ["data", "funcao", "bandeira"]
MEDIDAS = {
    "qtdCartoesEmitidos": "emitidos",
    "qtdCartoesAtivos": "ativos",
    "qtdTransacoesNacionais": "transacoes",
    "valorTransacoesNacionais": "valor",
}
SCHEMA = pa.schema(
    [("data", pa.date32()), ("funcao", pa.string()), ("bandeira", pa.string())]
    + [(m, pa.float64()) for m in MEDIDAS.values()]
)


def tabela(linhas: list[dict]) -> pd.DataFrame:
    """Sum products/modalities into quarter × function × brand; a quarter is dated on its last month."""
    df = pd.DataFrame(linhas).rename(
        columns={"nomeFuncao": "funcao", "nomeBandeira": "bandeira", **MEDIDAS}
    )
    df["trimestre"] = df.trimestre.astype(int)
    df["data"] = [dt.date(t // 10, (t % 10) * 3, 1) for t in df.trimestre]
    for m in MEDIDAS.values():
        df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0.0).astype(float)
    return df.groupby(CHAVE, as_index=False)[list(MEDIDAS.values())].sum()[SCHEMA.names]


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Every quarter since the first year (one call returns them all)."""
    hoje = hoje or dt.date.today()
    inicio = min(anos) if anos else hoje.year - 1
    linhas = olinda.consultar(
        CAMINHO, {"@trimestre": f"'{inicio}1'"}, sessao or requests.Session()
    )
    df = tabela(linhas)
    armazem.gravar(df, NOME, SCHEMA, pasta)
    return df
