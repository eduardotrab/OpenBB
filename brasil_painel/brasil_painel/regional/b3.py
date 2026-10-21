"""B3 public data: daily candles (COTAHIST) and the Ibovespa portfolio (plan 18).

COTAHIST is a fixed-width text file (~800 MB a year unzipped), read as a
stream: only type-01 records of standard-lot stocks (BDI 02) in the cash
market (010) are kept.
"""

import base64
import datetime as dt
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import requests

from brasil_painel.regional import armazem

URL_COTAHIST = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"
URL_CARTEIRA = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/{consulta}"
NOME_DIARIO, NOME_IBOV = "b3_diario", "b3_ibov"
SCHEMA_DIARIO = pa.schema(
    [
        ("data", pa.date32()),
        ("ticker", pa.string()),
        ("nome", pa.string()),
        ("abertura", pa.float64()),
        ("maxima", pa.float64()),
        ("minima", pa.float64()),
        ("fechamento", pa.float64()),
        ("negocios", pa.int64()),
        ("volume", pa.float64()),
    ]
)
SCHEMA_IBOV = pa.schema(
    [
        ("data", pa.date32()),
        ("ticker", pa.string()),
        ("nome", pa.string()),
        ("tipo", pa.string()),
        ("peso", pa.float64()),
    ]
)


def _preco(campo: str) -> float:
    return int(campo) / 100


def ler_linha(linha: str) -> dict | None:
    """One COTAHIST record → dict, or None when it is not a standard-lot cash stock."""
    if linha[0:2] != "01" or linha[10:12] != "02" or linha[24:27] != "010":
        return None
    return {
        "data": dt.date(int(linha[2:6]), int(linha[6:8]), int(linha[8:10])),
        "ticker": linha[12:24].strip(),
        "nome": linha[27:39].strip(),
        "abertura": _preco(linha[56:69]),
        "maxima": _preco(linha[69:82]),
        "minima": _preco(linha[82:95]),
        "fechamento": _preco(linha[108:121]),
        "negocios": int(linha[147:152]),
        "volume": _preco(linha[170:188]),
    }


def ler_zip(arquivo: Path) -> pd.DataFrame:
    """Stream the yearly zip and keep the cash-market stocks."""
    registros = []
    with zipfile.ZipFile(arquivo) as z:
        nome = z.namelist()[0]
        with z.open(nome) as bruto:
            for linha in io.TextIOWrapper(bruto, encoding="latin-1"):
                registro = ler_linha(linha)
                if registro:
                    registros.append(registro)
    return pd.DataFrame(registros, columns=SCHEMA_DIARIO.names)


def baixar(ano: int, pasta: Path, sessao: requests.Session) -> Path | None:
    """Download the yearly file unless the cached copy has the same size."""
    url = URL_COTAHIST.format(ano=ano)
    cabecalho = sessao.head(url, timeout=60)
    if cabecalho.status_code == 404:
        return None
    cabecalho.raise_for_status()
    destino = pasta / f"COTAHIST_A{ano}.ZIP"
    tamanho = int(cabecalho.headers.get("Content-Length", -1))
    if destino.exists() and destino.stat().st_size == tamanho:
        return destino
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    with sessao.get(url, timeout=900, stream=True) as resposta:
        resposta.raise_for_status()
        with temporario.open("wb") as saida:
            for bloco in resposta.iter_content(1 << 20):
                saida.write(bloco)
    temporario.replace(destino)
    return destino


def carteira_ibov(linhas: list[dict], hoje: dt.date) -> pd.DataFrame:
    """Ibovespa portfolio rows → (date, ticker, name, type, weight %)."""
    df = pd.DataFrame(
        {
            "data": hoje,
            "ticker": [r["cod"] for r in linhas],
            "nome": [r.get("asset", "") for r in linhas],
            "tipo": [r.get("type", "") for r in linhas],
            "peso": [
                float(str(r["part"]).replace(".", "").replace(",", ".")) for r in linhas
            ],
        }
    )
    return df[SCHEMA_IBOV.names]


def atualizar(
    anos: list[int] | None = None,
    pasta: Path | None = None,
    pasta_bruta: Path | None = None,
    sessao: requests.Session | None = None,
    hoje: dt.date | None = None,
) -> pd.DataFrame:
    """Candles of last year and this year, plus today's Ibovespa portfolio."""
    hoje = hoje or dt.date.today()
    anos = anos or [hoje.year - 1, hoje.year]
    sessao = sessao or requests.Session()
    pasta_bruta = pasta_bruta or Path("~/.cache/openbb-painel/bruto").expanduser()
    partes = []
    existente = armazem.ler(NOME_DIARIO, pasta)
    if existente is not None:
        partes.append(existente[~existente.data.map(lambda d: d.year).isin(anos)])
    for ano in anos:
        arquivo = baixar(ano, pasta_bruta, sessao)
        if arquivo is not None:
            partes.append(ler_zip(arquivo))
    diario = pd.concat(partes, ignore_index=True).drop_duplicates(
        ["data", "ticker"], keep="last"
    )
    diario = diario.sort_values(["ticker", "data"], ignore_index=True)
    armazem.gravar(diario, NOME_DIARIO, SCHEMA_DIARIO, pasta)
    consulta = base64.b64encode(
        json.dumps(
            {
                "language": "pt-br",
                "pageNumber": 1,
                "pageSize": 120,
                "index": "IBOV",
                "segment": "1",
            }
        ).encode()
    ).decode()
    resposta = sessao.get(URL_CARTEIRA.format(consulta=consulta), timeout=60)
    resposta.raise_for_status()
    armazem.gravar(
        carteira_ibov(resposta.json()["results"], hoje), NOME_IBOV, SCHEMA_IBOV, pasta
    )
    return diario
