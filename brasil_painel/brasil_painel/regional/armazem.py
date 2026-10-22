"""Local store of the regional datasets: one Parquet file per dataset."""

import functools
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DIRETORIO_PADRAO = "~/.local/share/openbb-painel/regional"

# Shared long format: one value per date × UF ("BR" = official national figure).
SCHEMA_LONGO = pa.schema(
    [
        ("data", pa.date32()),
        ("uf", pa.string()),
        ("indicador", pa.string()),
        ("valor", pa.float64()),
    ]
)

# Municipal long format: `municipio` is the 7-digit IBGE code.
SCHEMA_MUNICIPAL = pa.schema(
    [
        ("data", pa.date32()),
        ("municipio", pa.string()),
        ("uf", pa.string()),
        ("indicador", pa.string()),
        ("valor", pa.float64()),
    ]
)


class SchemaInvalido(ValueError):
    """The data does not match the dataset contract; nothing was written."""


def diretorio() -> Path:
    """Store directory (`PAINEL_DADOS_DIR`, default under ~/.local/share)."""
    return Path(os.environ.get("PAINEL_DADOS_DIR", DIRETORIO_PADRAO)).expanduser()


def gravar(
    df: pd.DataFrame, nome: str, schema: pa.Schema, pasta: Path | None = None
) -> Path:
    """Validate against `schema` and atomically replace `<nome>.parquet`."""
    if list(df.columns) != schema.names:
        raise SchemaInvalido(f"{nome}: colunas {list(df.columns)} ≠ {schema.names}")
    try:
        tabela = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    except (pa.ArrowInvalid, pa.ArrowTypeError) as error:
        raise SchemaInvalido(f"{nome}: {error}") from error
    nulos = [c for c in schema.names if tabela.column(c).null_count]
    if nulos:
        raise SchemaInvalido(f"{nome}: valores vazios em {nulos}")
    pasta = pasta or diretorio()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{nome}.parquet"
    temporario = pasta / f"{nome}.parquet.tmp"
    pq.write_table(tabela, temporario)
    os.replace(temporario, destino)
    return destino


def ler(nome: str, pasta: Path | None = None) -> pd.DataFrame | None:
    """Read a dataset, or None when it was never ingested.

    Cached by file modification time; callers get a copy they may change.
    """
    caminho = (pasta or diretorio()) / f"{nome}.parquet"
    if not caminho.exists():
        return None
    return _ler_arquivo(str(caminho), caminho.stat().st_mtime_ns).copy()


@functools.lru_cache(maxsize=16)
def _ler_arquivo(caminho: str, _modificado: int) -> pd.DataFrame:
    return pq.read_table(caminho).to_pandas()


def ordenar_longo(df: pd.DataFrame) -> pd.DataFrame:
    """Columns and row order of the long format."""
    return df[SCHEMA_LONGO.names].sort_values(
        ["indicador", "uf", "data"], ignore_index=True
    )


def ordenar_municipal(df: pd.DataFrame) -> pd.DataFrame:
    """Columns and row order of the municipal format."""
    return df[SCHEMA_MUNICIPAL.names].sort_values(
        ["indicador", "municipio", "data"], ignore_index=True
    )
