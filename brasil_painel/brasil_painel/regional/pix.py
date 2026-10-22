"""Pix value by UF and by municipality, from the BCB municipal data (Olinda, monthly)."""

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from brasil_painel.regional import armazem
from brasil_painel.regional.ufs import BRASIL, SIGLAS

NOME = "pix_uf"
NOME_MUNICIPIO = "pix_municipio"
URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
    "TransacoesPixPorMunicipio(DataBase=@DataBase)"
)
# Olinda field → indicator (R$, by the location of the payer / receiver)
CAMPOS = {
    "VL_PagadorPF": "pix_pago_pf",
    "VL_PagadorPJ": "pix_pago_pj",
    "VL_RecebedorPF": "pix_recebido_pf",
    "VL_RecebedorPJ": "pix_recebido_pj",
}


def por_uf(linhas: list[dict], hoje: dt.date) -> pd.DataFrame:
    """Sum municipalities per UF and Brazil; the current (partial) month is dropped."""
    df = pd.DataFrame(linhas)
    df = df[df["AnoMes"] < hoje.year * 100 + hoje.month]
    df["uf"] = df["Estado_Ibge"].map(SIGLAS)
    soma = df.groupby(["AnoMes", "uf"])[list(CAMPOS)].sum().reset_index()
    brasil = soma.groupby("AnoMes")[list(CAMPOS)].sum().reset_index()
    brasil["uf"] = BRASIL
    longo = pd.concat([soma, brasil]).melt(
        id_vars=["AnoMes", "uf"], var_name="campo", value_name="valor"
    )
    longo["indicador"] = longo["campo"].map(CAMPOS)
    longo["data"] = [dt.date(m // 100, m % 100, 1) for m in longo["AnoMes"]]
    longo["valor"] = longo["valor"].astype(float)
    return armazem.ordenar_longo(longo)


def por_municipio(linhas: list[dict], hoje: dt.date) -> pd.DataFrame:
    """One row per month × municipality × indicator; the current (partial) month is dropped.

    Rows without a municipality code still count in the state totals (`por_uf`).
    """
    df = pd.DataFrame(linhas).dropna(subset=["Municipio_Ibge"])
    df = df[df["AnoMes"] < hoje.year * 100 + hoje.month]
    longo = df.melt(
        id_vars=["AnoMes", "Municipio_Ibge", "Estado_Ibge"],
        value_vars=list(CAMPOS),
        var_name="campo",
        value_name="valor",
    )
    longo["municipio"] = longo["Municipio_Ibge"].astype(int).astype(str)
    longo["uf"] = longo["Estado_Ibge"].map(SIGLAS)
    longo["indicador"] = longo["campo"].map(CAMPOS)
    longo["data"] = [dt.date(m // 100, m % 100, 1) for m in longo["AnoMes"]]
    longo["valor"] = longo["valor"].astype(float)
    return armazem.ordenar_municipal(longo)


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Fetch every month since January of the first year (one call); store by UF and municipality."""
    hoje = hoje or dt.date.today()
    inicio = min(anos) if anos else hoje.year - 1
    resposta = (sessao or requests.Session()).get(
        URL,
        params={
            "@DataBase": f"'{inicio}01'",
            "$format": "json",
            "$select": "AnoMes,Municipio_Ibge,Estado_Ibge," + ",".join(CAMPOS),
        },
        timeout=300,
    )
    resposta.raise_for_status()
    linhas = resposta.json()["value"]
    df = por_uf(linhas, hoje)
    armazem.gravar(df, NOME, armazem.SCHEMA_LONGO, pasta)
    armazem.gravar(
        por_municipio(linhas, hoje), NOME_MUNICIPIO, armazem.SCHEMA_MUNICIPAL, pasta
    )
    return df
