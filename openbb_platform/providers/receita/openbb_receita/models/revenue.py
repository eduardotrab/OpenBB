"""Receita Federal Revenue Model: monthly federal tax revenue by state."""

# pylint: disable=unused-argument

import csv
import hashlib
import io
import os
import re
import time
import unicodedata
from datetime import date as dateType
from pathlib import Path
from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

REVENUE_CSV_URL = "https://www.gov.br/receitafederal/dados/arrecadacao-estado.csv"
CACHE_TTL_HOURS = 24
MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
KEY_COLUMNS = ("Ano", "Mês", "UF")


def fold(text: str) -> str:
    """Lowercase and strip accents."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


LAST_US_FORMAT_YEAR = 2002


def parse_number(value: str, year: int) -> float | None:
    """Parse a revenue cell; the file mixes number formats by era.

    Up to 2002 commas are thousands separators ('47,953,915'), except a single
    comma followed by 1-2 digits, which is a decimal ('12,5'). From 2003 on the
    format is Brazilian: '.' thousands and ',' decimal ('226.708.856,85').
    Rule derived from profiling the source file on 2026-10-19.
    """
    if not value:
        return None
    if year <= LAST_US_FORMAT_YEAR and not re.fullmatch(r"-?\d+,\d{1,2}", value):
        return float(value.replace(",", ""))
    return float(value.replace(".", "").replace(",", "."))


def parse_revenue_csv(text: str) -> list[dict]:
    """Melt the wide CSV (one column per tax) into one row per month, UF and tax."""
    rows = []
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        date = dateType(int(row["Ano"]), MONTHS[fold(row["Mês"])], 1)
        for tax, value in row.items():
            if tax not in KEY_COLUMNS:
                rows.append(
                    {
                        "date": date,
                        "uf": row["UF"],
                        "tax": tax,
                        "value": parse_number(value, date.year),
                    }
                )
    return rows


def _cache_path() -> Path:
    base = Path(
        os.environ.get(
            "OPENBB_RECEITA_CACHE_DIR", Path.home() / ".cache" / "openbb_receita"
        )
    )
    return base / f"{hashlib.sha256(REVENUE_CSV_URL.encode()).hexdigest()}.csv"


class ReceitaRevenueQueryParams(QueryParams):
    """Receita Federal Revenue Query."""

    __json_schema_extra__ = {"uf": {"multiple_items_allowed": True}}

    start_year: int | None = Field(
        default=None, description="First year (from 2000). Defaults to last year."
    )
    end_year: int | None = Field(
        default=None, description="Last year. Defaults to the current year."
    )
    uf: str | None = Field(
        default=None, description="State(s), comma-separated (e.g. 'SP,RJ')."
    )
    tax: str | None = Field(
        default=None,
        description="Tax column filter, case and accent insensitive substring"
        " (e.g. 'IRPF', 'previdenciaria', 'COFINS').",
    )
    use_cache: bool = Field(
        default=True, description="Cache the source file on disk for 24 hours."
    )


class ReceitaRevenueData(Data):
    """Receita Federal Revenue Data (nominal BRL)."""

    date: dateType = Field(description="Month (first day).")
    uf: str = Field(description="State (UF).")
    tax: str = Field(description="Tax / revenue line, as named by the Receita.")
    value: float | None = Field(default=None, description="Revenue in BRL.")


class ReceitaRevenueFetcher(
    Fetcher[ReceitaRevenueQueryParams, list[ReceitaRevenueData]]
):
    """Fetch monthly federal tax revenue by state from the Receita Federal."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> ReceitaRevenueQueryParams:
        """Transform query, defaulting to last year and the current year."""
        query = ReceitaRevenueQueryParams(**params)
        query.end_year = query.end_year or dateType.today().year
        query.start_year = query.start_year or query.end_year - 1
        return query

    @staticmethod
    async def aextract_data(
        query: ReceitaRevenueQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Download (or read from cache) the CSV and melt it."""
        # pylint: disable=import-outside-toplevel
        from openbb_core.provider.utils.helpers import amake_request

        path = _cache_path()
        if (
            query.use_cache
            and path.exists()
            and time.time() - path.stat().st_mtime < CACHE_TTL_HOURS * 3600
        ):
            return parse_revenue_csv(path.read_text(encoding="utf-8"))

        async def response_callback(response, _):
            if response.status != 200:
                raise OpenBBError(f"Receita Federal returned {response.status}.")
            return (await response.read()).decode("latin-1")

        text: str = await amake_request(  # type: ignore[assignment]
            REVENUE_CSV_URL,
            timeout=120,
            response_callback=response_callback,
            # gov.br answers 401 to the core default "Accept: application/json".
            headers={"Accept": "text/csv,*/*"},
            **kwargs,
        )
        if query.use_cache and text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return parse_revenue_csv(text)

    @staticmethod
    def transform_data(
        query: ReceitaRevenueQueryParams, data: list[dict], **kwargs: Any
    ) -> list[ReceitaRevenueData]:
        """Filter by years, UF and tax; sort by date, UF and tax."""
        ufs = {u.strip().upper() for u in query.uf.split(",")} if query.uf else None
        tax = fold(query.tax) if query.tax else None
        rows = [
            r
            for r in data
            if query.start_year <= r["date"].year <= query.end_year  # type: ignore[operator]
            and (ufs is None or r["uf"] in ufs)
            and (tax is None or tax in fold(r["tax"]))
        ]
        if not rows:
            raise OpenBBError(EmptyDataError("No federal revenue found for the query."))
        rows.sort(key=lambda r: (r["date"], r["uf"], r["tax"]))
        return [ReceitaRevenueData(**r) for r in rows]
