"""POS terminals by UF (BCB payment-means data, quarterly)."""

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from brasil_painel.regional import armazem
from brasil_painel.regional.ufs import BRASIL

NOME = "maquininhas_uf"
URL = (
    "https://olinda.bcb.gov.br/olinda/servico/MPV_DadosAbertos/versao/v1/odata/"
    "INFRTERMDA(trimestre=@trimestre)"
)


def por_uf(linhas: list[dict]) -> pd.DataFrame:
    """POS terminals per UF and Brazil; a quarter is dated on its last month."""
    df = pd.DataFrame(linhas).rename(
        columns={"UFTerminal": "uf", "qtdTermPOS": "valor"}
    )
    brasil = df.groupby("trimestre", as_index=False)["valor"].sum()
    brasil["uf"] = BRASIL
    df = pd.concat([df[["trimestre", "uf", "valor"]], brasil])
    df["data"] = [dt.date(t // 10, (t % 10) * 3, 1) for t in df["trimestre"]]
    df["indicador"] = "maquininhas_pos"
    df["valor"] = df["valor"].astype(float)
    return armazem.ordenar_longo(df)


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Fetch every quarter since the first year (one call) and store."""
    hoje = hoje or dt.date.today()
    inicio = min(anos) if anos else hoje.year - 1
    resposta = (sessao or requests.Session()).get(
        URL,
        params={
            "@trimestre": f"'{inicio}1'",
            "$format": "json",
            "$select": "trimestre,UFTerminal,qtdTermPOS",
        },
        timeout=120,
    )
    resposta.raise_for_status()
    df = por_uf(resposta.json()["value"])
    armazem.gravar(df, NOME, armazem.SCHEMA_LONGO, pasta)
    return df
