"""Tesouro Direto Model: daily rates and prices of Brazilian retail bonds."""

# pylint: disable=unused-argument

import csv
import io
from datetime import (
    date as dateType,
    datetime,
    timedelta,
)
from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

PRICES_CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)
CACHE_TTL_HOURS = 12
DOWNLOAD_TIMEOUT = 300
DEFAULT_LOOKBACK_DAYS = 30
COLUMNS = {
    "Taxa Compra Manha": "buy_rate",
    "Taxa Venda Manha": "sell_rate",
    "PU Compra Manha": "buy_price",
    "PU Venda Manha": "sell_price",
    "PU Base Manha": "base_price",
}


def _br_date(value: str) -> dateType:
    return datetime.strptime(value, "%d/%m/%Y").date()


def _br_number(value: str) -> float | None:
    return float(value.replace(".", "").replace(",", ".")) if value else None


def parse_csv(text: str) -> list[dict]:
    """Parse the Tesouro Direto CSV (';' separated, Brazilian number format)."""
    return [
        {
            "date": _br_date(row["Data Base"]),
            "bond": row["Tipo Titulo"],
            "maturity": _br_date(row["Data Vencimento"]),
            **{name: _br_number(row[col]) for col, name in COLUMNS.items()},
        }
        for row in csv.DictReader(io.StringIO(text), delimiter=";")
    ]


class TesouroDiretoQueryParams(QueryParams):
    """Tesouro Direto Query."""

    bond: str | None = Field(
        default=None,
        description="Bond type filter, case-insensitive substring (e.g. 'Selic',"
        " 'IPCA+', 'Prefixado', 'Renda+').",
    )
    start_date: dateType | None = Field(
        default=None, description="Start date. Defaults to 30 days ago."
    )
    end_date: dateType | None = Field(
        default=None, description="End date. Defaults to today."
    )
    use_cache: bool = Field(
        default=True,
        description="Cache the full history file (~15 MB) on disk for 12 hours.",
    )


class TesouroDiretoData(Data):
    """Tesouro Direto Data (rates in % per year, prices in BRL)."""

    date: dateType = Field(description="Reference date (Data Base).")
    bond: str = Field(description="Bond type (Tipo Título).")
    maturity: dateType = Field(description="Maturity date.")
    buy_rate: float | None = Field(
        default=None, description="Rate offered to investors buying (% a.a.)."
    )
    sell_rate: float | None = Field(
        default=None, description="Rate paid to investors selling back (% a.a.)."
    )
    buy_price: float | None = Field(default=None, description="Unit buy price (PU).")
    sell_price: float | None = Field(default=None, description="Unit sell price (PU).")
    base_price: float | None = Field(default=None, description="Unit base price.")


class TesouroDiretoFetcher(Fetcher[TesouroDiretoQueryParams, list[TesouroDiretoData]]):
    """Fetch Tesouro Direto rates and prices from Tesouro Transparente."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> TesouroDiretoQueryParams:
        """Transform query, defaulting to the last 30 days."""
        query = TesouroDiretoQueryParams(**params)
        query.end_date = query.end_date or dateType.today()
        query.start_date = query.start_date or query.end_date - timedelta(
            days=DEFAULT_LOOKBACK_DAYS
        )
        return query

    @staticmethod
    async def aextract_data(
        query: TesouroDiretoQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Download (or read from cache) the full history and parse it."""
        # pylint: disable=import-outside-toplevel
        from openbb_core.provider.utils.helpers import amake_request

        from openbb_tesouro.utils.cache import cached_text

        async def response_callback(response, _):
            if response.status != 200 or "csv" not in response.headers.get(
                "Content-Type", ""
            ):
                raise OpenBBError(
                    f"Tesouro Transparente returned {response.status} without a CSV."
                )
            raw = await response.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1")

        # `amake_request` replaces `timeout` with `preferences.request_timeout`
        # (60 s by default), which is shorter than this ~80 s download.
        preferences = kwargs.pop("preferences", None) or {}
        timeout = max(DOWNLOAD_TIMEOUT, preferences.get("request_timeout") or 0)

        async def load() -> str:
            return await amake_request(  # type: ignore[return-value]
                PRICES_CSV_URL,
                timeout=timeout,
                response_callback=response_callback,
                **kwargs,
            )

        text = await cached_text(
            PRICES_CSV_URL, load, ttl_hours=CACHE_TTL_HOURS, use_cache=query.use_cache
        )
        return parse_csv(text)

    @staticmethod
    def transform_data(
        query: TesouroDiretoQueryParams, data: list[dict], **kwargs: Any
    ) -> list[TesouroDiretoData]:
        """Filter by date range and bond type; sort by date, bond, maturity."""
        bond = (query.bond or "").lower()
        rows = [
            row
            for row in data
            if query.start_date <= row["date"] <= query.end_date  # type: ignore[operator]
            and bond in row["bond"].lower()
        ]
        if not rows:
            raise OpenBBError(
                EmptyDataError("No Tesouro Direto data found for the query.")
            )
        rows.sort(key=lambda r: (r["date"], r["bond"], r["maturity"]))
        return [TesouroDiretoData(**row) for row in rows]
