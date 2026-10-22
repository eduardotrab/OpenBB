"""BCB ESTBAN: balances of bank branches by municipality (monthly).

Only banks report (single credit cooperatives do not; Banco Sicoob does), and a
balance sits where the branch is, so the figures compare municipalities of one
state rather than measure "the credit of the municipality". The BCB municipality
code is linked to the IBGE one by name and UF.
"""

import datetime as dt
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd
import requests

from brasil_painel.regional import armazem, malha
from brasil_painel.regional.ufs import SIGLAS

NOME = "estban_municipio"
URL = "https://www.bcb.gov.br/content/estatisticas/estatistica_bancaria_estban/municipio/{mes:%Y%m}_ESTBAN.csv.zip"
INICIO = dt.date(2025, 6, 1)  # before the doubled files (see `corrigir_duplicacao`)
REBAIXAR = 6  # recent months downloaded again: the BCB may fix them
ATIVO = "VERBETE_399_TOTAL_DO_ATIVO"
BRASILIA = "5300108"
# accounts (column prefix) → indicator
VERBETES = {
    "credito": ["VERBETE_160"],
    "rural": ["VERBETE_163", "VERBETE_167"],
    "poupanca": ["VERBETE_420"],
    "depositos": [
        "VERBETE_401",
        "VERBETE_432",
    ],  # demand (401 to 413, one column) and time deposits
}
SICOOB = {"credito", "poupanca"}  # indicators also stored for Banco Sicoob alone
# BCB spellings that differ from the IBGE name (BCB code → IBGE code)
EXCECOES = {
    "22693": "2306306",  # Itapagé → Itapajé
    "31189": "3108909",  # Brasópolis → Brazópolis
    "24323": "5107800",  # Santo Antônio do Leverger → de Leverger
    "28082": "1506500",  # Santa Isabel do Pará → Izabel
    "51145": "1502954",  # Eldorado dos Carajás → do Carajás
    "33778": "2601607",  # Belém de São Francisco → do São Francisco
    "37877": "2608503",  # Lagoa do Itaenga → de Itaenga
    "1157": "4123303",  # Santa Cruz do Monte Castelo → de Monte Castelo
    "9300": "3305901",  # Trajano de Morais → Moraes
    "24574": "3303807",  # Parati → Paraty
    "33709": "2400208",  # Açu → Assú
    "5122": "4217204",  # São Miguel d'Oeste → do Oeste
    "32748": "3550001",  # São Luis do Paraitinga → Luiz
}


def _normalizar(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", sem_acento.upper())


def _indice_ibge() -> dict[tuple[str, str], str]:
    nomes = json.loads(malha.LISTA.read_text())
    return {(_normalizar(nome), uf): codigo for codigo, (nome, uf) in nomes.items()}


def codigo_ibge(codmun: str, municipio: str, uf: str, indice: dict) -> str | None:
    """IBGE code of a BCB municipality, or None when it cannot be linked."""
    if codmun in EXCECOES:
        return EXCECOES[codmun]
    if uf == "DF":
        return BRASILIA  # the administrative regions are all Brasília
    return indice.get((_normalizar(municipio), uf))


def ler_zip(arquivo) -> tuple[pd.DataFrame, list[str]]:
    """One month of ESTBAN by municipality and institution, plus the municipalities left unlinked."""
    with zipfile.ZipFile(arquivo) as z:
        bruto = z.read(z.namelist()[0])
    df = pd.read_csv(
        io.BytesIO(bruto),
        sep=";",
        encoding="latin-1",
        skiprows=2,
        decimal=",",
        dtype={"CODMUN": str},
    )
    df = df.rename(columns={"#DATA_BASE": "DATA_BASE"})
    indice = _indice_ibge()
    df["municipio"] = [
        codigo_ibge(c, m, u, indice)
        for c, m, u in zip(df.CODMUN, df.MUNICIPIO, df.UF, strict=True)
    ]
    sem_codigo = sorted(
        {
            f"{m} ({u})"
            for m, u, c in zip(df.MUNICIPIO, df.UF, df.municipio, strict=True)
            if pd.isna(c)
        }
    )
    df = df.dropna(subset=["municipio"])
    colunas = {
        indicador: df[[c for c in df.columns if any(c.startswith(p) for p in prefixos)]]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .sum(axis=1)
        for indicador, prefixos in VERBETES.items()
    }
    return pd.DataFrame(
        {
            "data": [dt.date(int(d) // 100, int(d) % 100, 1) for d in df.DATA_BASE],
            "municipio": df.municipio,
            "cnpj": df.CNPJ.astype(str),
            "sicoob": df.NOME_INSTITUICAO.str.upper().str.contains(
                "SICOOB", regex=False
            ),
            "ativo": pd.to_numeric(df[ATIVO], errors="coerce").fillna(0),
            **colunas,
        }
    ), sem_codigo


def corrigir_duplicacao(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[tuple[str, dt.date]]]:
    """Remove the copy of an institution's whole balance sheet booked in one municipality.

    Some BCB files add, in a single municipality (the head office, e.g.
    Brasília for Caixa and Banco do Brasil from April 2026), an extra amount
    equal to the institution's entire balance; the other municipalities are
    unaffected. Following each institution's total assets month to month, a
    jump of about ×2 starts a doubled run and a drop of about ÷2 ends it. In a
    doubled month, half of the institution's total is subtracted, column by
    column, from its municipality with the largest assets. The first month of
    the history is taken as correct.
    """
    totais = df.groupby(["cnpj", "data"]).ativo.sum().sort_index()
    corrigidos = []
    for cnpj, serie in totais.groupby(level="cnpj"):
        dobrado, anterior = False, None
        for (_, data), valor in serie.items():
            if anterior:
                razao = valor / anterior
                if 1.8 <= razao <= 2.25:
                    dobrado = True
                elif 0.44 <= razao <= 0.56:
                    dobrado = False
            if dobrado:
                corrigidos.append((cnpj, data))
            anterior = valor
    if not corrigidos:
        return df, []
    corrigido = df.copy()
    colunas = ["ativo", *VERBETES]
    for cnpj, data in corrigidos:
        linhas = corrigido[(corrigido.cnpj == cnpj) & (corrigido.data == data)]
        sede = linhas.ativo.idxmax()
        excesso = linhas[colunas].sum() / 2
        corrigido.loc[sede, colunas] = (corrigido.loc[sede, colunas] - excesso).clip(
            lower=0
        )
    return corrigido, corrigidos


def municipal(df: pd.DataFrame) -> pd.DataFrame:
    """Sum the institutions of each municipality; Banco Sicoob also apart."""
    valores = df[["data", "municipio", *VERBETES]].copy()
    for indicador in SICOOB:
        valores[f"{indicador}_sicoob"] = df[indicador].where(df.sicoob, 0.0)
    soma = valores.groupby(["data", "municipio"]).sum().reset_index()
    longo = soma.melt(
        id_vars=["data", "municipio"], var_name="indicador", value_name="valor"
    )
    longo["uf"] = longo.municipio.str[:2].astype(int).map(SIGLAS)
    longo["valor"] = longo.valor.astype(float)
    return armazem.ordenar_municipal(longo)


def baixar(
    mes: dt.date, pasta: Path | None, sessao: requests.Session, novo: bool = False
) -> bytes | None:
    """Zip of one month (cached; `novo` downloads again); None when not published yet."""
    destino = pasta / f"estban_{mes:%Y%m}.zip" if pasta else None
    if destino is not None and destino.exists() and not novo:
        return destino.read_bytes()
    resposta = sessao.get(URL.format(mes=mes), timeout=300)
    # unpublished months answer 404 with an HTML page
    if resposta.status_code == 404 or not resposta.content.startswith(b"PK"):
        return None
    resposta.raise_for_status()
    if destino is not None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(resposta.content)
    return resposta.content


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    pasta_bruta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Store every published month since `INICIO`, with doubled balances corrected."""
    hoje = hoje or dt.date.today()
    pasta_bruta = (
        pasta_bruta or Path("~/.cache/openbb-painel/bruto").expanduser()
    ) / "estban"
    sessao = sessao or requests.Session()
    meses, mes = [], INICIO
    while mes < hoje.replace(day=1):
        meses.append(mes)
        mes = (mes + dt.timedelta(days=32)).replace(day=1)
    partes = []
    for mes in meses:
        conteudo = baixar(mes, pasta_bruta, sessao, novo=mes >= meses[-REBAIXAR - 3])
        if conteudo is None:
            continue
        df, sem_codigo = ler_zip(io.BytesIO(conteudo))
        if sem_codigo:
            print(f"estban {mes:%Y-%m}: sem código IBGE: {', '.join(sem_codigo)}")  # noqa: T201
        partes.append(df)
    df, corrigidos = corrigir_duplicacao(pd.concat(partes, ignore_index=True))
    if corrigidos:
        meses_corrigidos = sorted({f"{d:%Y-%m}" for _, d in corrigidos})
        print(  # noqa: T201
            f"estban: {len(corrigidos)} instituição-mês com saldo em dobro corrigidos ({', '.join(meses_corrigidos)})"
        )
    longo = municipal(df)
    armazem.gravar(longo, NOME, armazem.SCHEMA_MUNICIPAL, pasta)
    return longo
