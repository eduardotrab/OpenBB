"""BCB SCR.data: credit portfolio and default by month × UF × segment × PF/PJ.

The yearly zip holds one ~100 MB CSV per month; DuckDB aggregates one CSV at a
time to keep memory low (~300 MB). See docs/palacio/02-dados/scr-data.md.
"""

import datetime as dt
import tempfile
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import requests

from brasil_painel.regional import armazem

URL = "https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
NOME = "scr_uf"
CHAVE = ["data", "uf", "cooperativa", "cliente"]
SCHEMA = pa.schema(
    [
        ("data", pa.date32()),
        ("uf", pa.string()),
        ("cooperativa", pa.bool_()),
        ("cliente", pa.string()),
        ("carteira_ativa", pa.float64()),
        ("carteira_inadimplencia", pa.float64()),
        ("vencido_15_90", pa.float64()),
    ]
)
TIPOS = {
    "data_base": "DATE",
    "carteira_ativa": "DOUBLE",
    "carteira_inadimplencia": "DOUBLE",
    "vencido_de_15_ate_90_dias": "DOUBLE",
}
SQL = """
SELECT data_base AS data,
       uf,
       segmento = 'Cooperativa' AS cooperativa,
       cliente,
       sum(carteira_ativa) AS carteira_ativa,
       sum(carteira_inadimplencia) AS carteira_inadimplencia,
       sum(vencido_de_15_ate_90_dias) AS vencido_15_90
FROM read_csv(?, delim=';', decimal_separator=',', header=true, types=?)
GROUP BY ALL
ORDER BY data, uf, cooperativa, cliente
"""


def agregar_csv(caminho: Path, memoria: str = "512MB") -> pd.DataFrame:
    """Aggregate one monthly CSV."""
    with duckdb.connect() as con:
        con.execute(f"SET memory_limit='{memoria}'; SET threads=2")
        df = con.execute(SQL, [str(caminho), TIPOS]).df()
    df["data"] = df["data"].dt.date
    return df[SCHEMA.names]


def agregar_zip(arquivo: Path) -> pd.DataFrame:
    """Aggregate every monthly CSV of a yearly zip, one at a time."""
    partes = []
    with zipfile.ZipFile(arquivo) as z, tempfile.TemporaryDirectory() as tmp:
        for nome in sorted(n for n in z.namelist() if n.endswith(".csv")):
            caminho = Path(z.extract(nome, tmp))
            partes.append(agregar_csv(caminho))
            caminho.unlink()
    return juntar(partes)


def juntar(partes: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate, keeping the last row for each key (newer data wins)."""
    df = pd.concat(partes, ignore_index=True)
    df = df.drop_duplicates(CHAVE, keep="last")
    return df.sort_values(CHAVE, ignore_index=True)


def anos_padrao(hoje: dt.date | None = None) -> list[int]:
    """Last year (12-month comparisons) and this year."""
    hoje = hoje or dt.date.today()
    return [hoje.year - 1, hoje.year]


def baixar(ano: int, pasta: Path, sessao: requests.Session) -> Path | None:
    """Download the yearly zip unless the cached copy has the same size.

    Returns None when the year is not published yet (404).
    """
    url = URL.format(ano=ano)
    cabecalho = sessao.head(url, timeout=60, allow_redirects=True)
    if cabecalho.status_code == 404:
        return None
    cabecalho.raise_for_status()
    destino = pasta / f"scrdata_{ano}.zip"
    tamanho = int(cabecalho.headers.get("Content-Length", -1))
    if destino.exists() and destino.stat().st_size == tamanho:
        return destino
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".zip.tmp")
    with sessao.get(url, timeout=600, stream=True) as resposta:
        resposta.raise_for_status()
        with temporario.open("wb") as saida:
            for bloco in resposta.iter_content(1 << 20):
                saida.write(bloco)
    temporario.replace(destino)
    return destino


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    pasta_bruta: Path | None = None,
    sessao: requests.Session | None = None,
) -> pd.DataFrame:
    """Download, aggregate and store `scr_uf`; earlier years already stored are kept."""
    anos = anos or anos_padrao()
    pasta_bruta = pasta_bruta or Path("~/.cache/openbb-painel/bruto").expanduser()
    sessao = sessao or requests.Session()
    partes = []
    existente = armazem.ler(NOME, pasta)
    if existente is not None:
        partes.append(existente)
    for ano in anos:
        arquivo = baixar(ano, pasta_bruta, sessao)
        if arquivo is not None:
            partes.append(agregar_zip(arquivo))
    df = juntar(partes)
    armazem.gravar(df, NOME, SCHEMA, pasta)
    return df
