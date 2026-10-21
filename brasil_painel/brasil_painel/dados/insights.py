"""Automatic insights for any table: the explorer's results or a user's upload (plan 19).

Everything is computed locally; an uploaded file is parsed in memory and never
written to disk (LGPD).
"""

import base64
import datetime as dt
import io
import math
import random
from dataclasses import dataclass, field

import pandas as pd

LIMITE_BYTES = 10 * 1024 * 1024
NOMES_DATA = ("date", "data", "period", "periodo", "dt")


class BaseInvalida(ValueError):
    """The uploaded file cannot be used (format, size or columns)."""


def ler_envio(conteudo: str, nome: str) -> pd.DataFrame:
    """`dcc.Upload` contents (data URL) → DataFrame; CSV (`,` or `;`) or Excel."""
    try:
        _, dados = conteudo.split(",", 1)
        bruto = base64.b64decode(dados)
    except (ValueError, TypeError) as error:
        raise BaseInvalida("o arquivo não pôde ser lido") from error
    if len(bruto) > LIMITE_BYTES:
        raise BaseInvalida("o arquivo passa de 10 MB")
    extensao = nome.lower().rsplit(".", 1)[-1]
    try:
        if extensao in ("xlsx", "xls"):
            return pd.read_excel(io.BytesIO(bruto))
        if extensao == "csv":
            texto = bruto.decode("utf-8-sig", errors="replace")
            separador = ";" if texto.count(";") > texto.count(",") else ","
            decimal = "," if separador == ";" else "."
            return pd.read_csv(io.StringIO(texto), sep=separador, decimal=decimal)
    except (ValueError, UnicodeDecodeError) as error:
        raise BaseInvalida(f"o arquivo não é um {extensao.upper()} válido") from error
    raise BaseInvalida("envie um arquivo .csv ou .xlsx")


def validar(df: pd.DataFrame, esperadas: list[str]) -> list[str]:
    """List the expected columns missing from the upload (case-insensitive)."""
    presentes = {c.strip().lower() for c in df.columns}
    return [c for c in esperadas if c.lower() not in presentes]


def coluna_data(df: pd.DataFrame) -> str | None:
    """Find the date column, by name or by successful parsing."""
    for c in df.columns:
        if str(c).lower() in NOMES_DATA:
            return c
    for c in df.columns:
        if _texto(df[c]):
            convertida = pd.to_datetime(df[c], errors="coerce")
            if convertida.notna().mean() > 0.9:
                return c
    return None


def _texto(serie: pd.Series) -> bool:
    """Text column (pandas 3 uses a string dtype, older versions `object`)."""
    return pd.api.types.is_string_dtype(serie) or pd.api.types.is_object_dtype(serie)


def numericas(df: pd.DataFrame) -> list[str]:
    """Numeric columns (at most 6) that vary; constants such as unit multipliers are left out."""
    cols = [
        c
        for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 1
    ]
    return cols[:6]


@dataclass(frozen=True)
class Insights:
    """What the automatic analysis says about a table."""

    linhas: int
    colunas: int
    periodo: tuple | None
    frases: list[str] = field(default_factory=list)


def _fmt(v: float) -> str:
    if abs(v) >= 1e4:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def analisar(df: pd.DataFrame) -> Insights:
    """Summary, trend, extremes and outliers in plain Portuguese sentences."""
    frases = []
    data = coluna_data(df)
    periodo = None
    ordenado = df
    if data:
        datas = pd.to_datetime(df[data], errors="coerce")
        ordenado = df.assign(_data=datas).dropna(subset=["_data"]).sort_values("_data")
        if not ordenado.empty:
            periodo = (ordenado._data.min().date(), ordenado._data.max().date())
            frases.append(f"Período de {periodo[0]:%d/%m/%Y} a {periodo[1]:%d/%m/%Y}.")
    categorias = [
        c
        for c in df.columns
        if _texto(df[c]) and c != data and 2 <= df[c].nunique() <= 50
    ]
    for col in numericas(df):
        valores = pd.to_numeric(ordenado[col], errors="coerce")
        if data and categorias:
            # several series (e.g. one per country): the trend uses the mean per date
            serie = valores.groupby(ordenado["_data"]).mean().dropna()
        else:
            serie = valores.dropna()
        if serie.empty:
            continue
        frase = f"{col}: último {_fmt(serie.iloc[-1])}, média {_fmt(serie.mean())}, de {_fmt(serie.min())} a {_fmt(serie.max())}."
        # a % change only makes sense for a positive level, not for rates that cross zero
        if data and len(serie) >= 3 and serie.min() > 0:
            variacao = (serie.iloc[-1] / serie.iloc[0] - 1) * 100
            if math.isfinite(variacao):
                direcao = "subiu" if variacao > 0 else "caiu"
                frase += f" No período, {direcao} {_fmt(abs(variacao))}%."
        if len(serie) >= 8 and serie.std():
            z = (serie - serie.mean()) / serie.std()
            fora = int((z.abs() > 3).sum())
            if fora:
                frase += f" {fora} valor{'es' if fora > 1 else ''} fora do padrão (mais de 3 desvios)."
        frases.append(frase)
    nums = numericas(df)
    if categorias and nums:
        cat, num = categorias[0], nums[0]
        ultimos = (
            ordenado.groupby(cat)[num].last().dropna().sort_values(ascending=False)
        )
        if len(ultimos) >= 2:
            frases.append(
                f"Maior {num}: {ultimos.index[0]} ({_fmt(ultimos.iloc[0])}). Menor: {ultimos.index[-1]} ({_fmt(ultimos.iloc[-1])})."
            )
    return Insights(len(df), len(df.columns), periodo, frases)


def exemplo(
    colunas: list[tuple[str, str, str]], n: int = 24, semente: int = 7
) -> pd.DataFrame:
    """Synthetic rows that follow the response columns (marked as an example by the screen)."""
    aleatorio = random.Random(semente)  # noqa: S311 - example data, not security
    if not colunas:
        colunas = [("date", "date", ""), ("value", "number", "")]
    hoje = dt.date.today().replace(day=1)
    dados = {}
    for nome, tipo, _ in colunas[:8]:
        if tipo in ("date", "date-time"):
            dados[nome] = [
                (hoje - dt.timedelta(days=30 * (n - i))).isoformat() for i in range(n)
            ]
        elif tipo in ("number", "integer"):
            nivel, valores = 100.0, []
            for _ in range(n):
                nivel *= 1 + aleatorio.uniform(-0.03, 0.035)
                valores.append(round(nivel, 2) if tipo == "number" else int(nivel))
            dados[nome] = valores
        elif tipo == "boolean":
            dados[nome] = [aleatorio.random() > 0.5 for _ in range(n)]
        else:
            dados[nome] = [f"Exemplo {chr(65 + i % 3)}" for i in range(n)]
    return pd.DataFrame(dados)


def modelo_csv(colunas: list[tuple[str, str, str]]) -> str:
    """Template for the user's base: the expected header plus three example rows."""
    return exemplo(colunas, n=3).to_csv(index=False, sep=";", decimal=",")
