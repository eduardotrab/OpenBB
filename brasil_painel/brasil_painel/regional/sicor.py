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
from brasil_painel.regional.ufs import SIGLAS

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


NOME_MUNICIPIO = "sicor_municipio"
URL_MUNICIPIO = (
    "https://olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata/{tabela}"
)
PORTES = {
    "Pequeno produtor": "pequeno",
    "Médio produtor": "medio",
    "Grande produtor": "grande",
}
MESES_MUNICIPIO = 24  # this harvest year and the previous one


def por_municipio(custeio: list[dict], investimento: list[dict]) -> pd.DataFrame:
    """Rural credit contracted per month × municipality × purpose × producer size.

    The investment table has only the BCB municipality code; it is linked to the
    IBGE one through the pairs of the custeio table (rows that cannot be linked
    are dropped).
    """
    pares = {c["codCadMu"]: c["codIbge"] for c in custeio}
    registros = [
        (r["AnoEmissao"], r["MesEmissao"], r["codIbge"], r["cdPrograma"], "custeio", r["VlCusteio"])
        for r in custeio
    ] + [
        (r["AnoEmissao"], r["MesEmissao"], pares[r["cdMunicipio"]], r["cdPrograma"], "investimento", r["VlInvest"])
        for r in investimento
        if r["cdMunicipio"] in pares
    ]  # fmt: skip
    if not registros:
        return pd.DataFrame(columns=armazem.SCHEMA_MUNICIPAL.names)
    df = pd.DataFrame(
        registros,
        columns=["ano", "mes", "municipio", "programa", "finalidade", "valor"],
    )
    df["indicador"] = (
        df.finalidade + "_" + df.programa.map(classes.classe_rural).map(PORTES)
    )
    df["data"] = [
        dt.date(int(a), int(m), 1) for a, m in zip(df.ano, df.mes, strict=True)
    ]
    df["municipio"] = df.municipio.astype(str)
    df["uf"] = df.municipio.str[:2].astype(int).map(SIGLAS)
    df["valor"] = df.valor.astype(float)
    soma = df.groupby(
        ["data", "municipio", "uf", "indicador"], as_index=False
    ).valor.sum()
    return armazem.ordenar_municipal(soma)


def _buscar_municipio(
    tabela: str, campos: list[str], mes: dt.date, sessao
) -> list[dict]:
    params = {
        "$format": "json",
        "$filter": f"AnoEmissao eq '{mes.year}' and MesEmissao eq '{mes.month:02d}'",
        "$select": ",".join(campos),
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe="$,'")
    resposta = sessao.get(f"{URL_MUNICIPIO.format(tabela=tabela)}?{query}", timeout=600)
    resposta.raise_for_status()
    return resposta.json()["value"]


def atualizar_municipios(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Fetch the missing months of the last 24 (plus the last two again) and store."""
    hoje = hoje or dt.date.today()
    sessao = sessao or requests.Session()
    primeiro = hoje.replace(day=1)
    for _ in range(MESES_MUNICIPIO):
        primeiro = (primeiro - dt.timedelta(days=1)).replace(day=1)
    existente = armazem.ler(NOME_MUNICIPIO, pasta)
    datas = set(existente.data) if existente is not None else set()
    novos = []
    for mes in meses_a_buscar(datas, primeiro, hoje):
        custeio = _buscar_municipio("CusteioMunicipioProduto", ["AnoEmissao", "MesEmissao", "cdPrograma", "VlCusteio", "codCadMu", "codIbge"], mes, sessao)  # fmt: skip
        invest = _buscar_municipio("InvestMunicipioProduto", ["AnoEmissao", "MesEmissao", "cdPrograma", "VlInvest", "cdMunicipio"], mes, sessao)  # fmt: skip
        if custeio or invest:
            novos.append(por_municipio(custeio, invest))
    partes = (
        [existente[existente.data >= primeiro]] if existente is not None else []
    ) + novos
    chave = ["data", "municipio", "indicador"]
    df = pd.concat(partes, ignore_index=True).drop_duplicates(chave, keep="last")
    df = armazem.ordenar_municipal(df)
    armazem.gravar(df, NOME_MUNICIPIO, armazem.SCHEMA_MUNICIPAL, pasta)
    return df
