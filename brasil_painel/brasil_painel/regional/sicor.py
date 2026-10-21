"""BCB SICOR: rural credit contracted per month × UF × producer size × lender.

Flow (what was contracted in the month), unlike the SCR.data stock. One month
per request (~70 s), so updates are incremental: missing months plus the last
two, which the BCB may still revise.
"""

import datetime as dt
import urllib.parse
from pathlib import Path

import pandas as pd
import pyarrow as pa
import requests

from brasil_painel.regional import armazem, classes

NOME = "sicor_uf"
URL = (
    "https://olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata/SegmentoIFRegiaoUF"
)
FINALIDADES = ["Custeio", "Investimento", "Comercializacao", "Industrializacao"]
ATIVIDADES = {"1": "Agrícola", "2": "Pecuária"}
CHAVE = ["data", "uf", "porte", "atividade", "cooperativa", "sicoob"]
SCHEMA = pa.schema(
    [
        ("data", pa.date32()),
        ("uf", pa.string()),
        ("porte", pa.string()),
        ("atividade", pa.string()),
        ("cooperativa", pa.bool_()),
        ("sicoob", pa.bool_()),
        *[(f"valor_{f.lower()}", pa.float64()) for f in FINALIDADES],
        ("contratos", pa.float64()),
    ]
)
REVISAR = 2  # last stored months fetched again


def agregar(linhas: list[dict]) -> pd.DataFrame:
    """Sum the lender rows by month, UF, producer size, activity and lender type."""
    if not linhas:
        return pd.DataFrame(columns=SCHEMA.names)
    df = pd.DataFrame(linhas)
    cooperativos = set(classes.configuracao()["cooperativas"]["sicor_segmentos"])
    marca_sicoob = classes.configuracao()["cooperativas"]["sicoob_no_nome"]
    df["data"] = [
        dt.date(int(a), int(m), 1) for a, m in zip(df.AnoEmissao, df.MesEmissao)
    ]
    df["uf"] = df.nomeUF
    df["porte"] = df.cdPrograma.map(classes.classe_rural)
    df["atividade"] = df.Atividade.astype(str).map(ATIVIDADES).fillna("Outra")
    df["cooperativa"] = df.nomeSegmento.isin(cooperativos)
    df["sicoob"] = df.nomeIF.str.upper().str.contains(marca_sicoob, regex=False)
    for f in FINALIDADES:
        df[f"valor_{f.lower()}"] = df[f"Vl{f}"].astype(float)
    df["contratos"] = df[[f"Qtd{f}" for f in FINALIDADES]].sum(axis=1).astype(float)
    medidas = [c for c in SCHEMA.names if c not in CHAVE]
    return df.groupby(CHAVE, as_index=False)[medidas].sum()[SCHEMA.names]


def buscar_mes(ano: int, mes: int, sessao: requests.Session) -> list[dict]:
    """All lender rows of one month (empty when not published yet)."""
    campos = [
        "AnoEmissao", "MesEmissao", "nomeUF", "nomeIF", "nomeSegmento", "cdPrograma", "Atividade",
        *[f"Vl{f}" for f in FINALIDADES], *[f"Qtd{f}" for f in FINALIDADES],
    ]  # fmt: skip
    params = {
        "$format": "json",
        "$filter": f"AnoEmissao eq '{ano}' and MesEmissao eq '{mes:02d}'",
        "$select": ",".join(campos),
    }
    # Olinda rejects "+" for spaces (400): encode them as %20.
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe="$,'")
    resposta = sessao.get(f"{URL}?{query}", timeout=600)
    resposta.raise_for_status()
    return resposta.json()["value"]


def meses_a_buscar(
    existentes: set[dt.date], inicio: dt.date, hoje: dt.date
) -> list[dt.date]:
    """Months from `inicio` to last month that are missing, plus the last stored ones."""
    meses, atual = [], inicio
    ultimo = (hoje.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    while atual <= ultimo:
        meses.append(atual)
        atual = (atual + dt.timedelta(days=32)).replace(day=1)
    revisar = set(sorted(existentes)[-REVISAR:])
    return [m for m in meses if m not in existentes or m in revisar]


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Fetch the missing months since January of the first year and store."""
    hoje = hoje or dt.date.today()
    sessao = sessao or requests.Session()
    inicio = dt.date(min(anos) if anos else hoje.year - 1, 1, 1)
    existente = armazem.ler(NOME, pasta)
    datas = set(existente.data) if existente is not None else set()
    novos = []
    for mes in meses_a_buscar(datas, inicio, hoje):
        linhas = buscar_mes(mes.year, mes.month, sessao)
        if linhas:
            novos.append(agregar(linhas))
    partes = ([existente] if existente is not None else []) + novos
    df = pd.concat(partes, ignore_index=True).drop_duplicates(CHAVE, keep="last")
    df = df.sort_values(CHAVE, ignore_index=True)
    armazem.gravar(df, NOME, SCHEMA, pasta)
    return df
