"""BCB PTAX Currency Historical Model."""

# pylint: disable=unused-argument

from datetime import (
    date as dateType,
    datetime,
    timedelta,
)
from typing import Any, Literal

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.currency_historical import (
    CurrencyHistoricalData,
    CurrencyHistoricalQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

PTAX_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
CLOSING_BULLETIN = "Fechamento"
DEFAULT_LOOKBACK_DAYS = 30


def split_ptax_symbol(symbol: str) -> str:
    """Return the foreign currency of a pair quoted in BRL (``USDBRL`` -> ``USD``)."""
    if len(symbol) == 3 and symbol != "BRL":
        return symbol
    if len(symbol) == 6 and symbol.endswith("BRL") and symbol[:3] != "BRL":
        return symbol[:3]
    raise OpenBBError(
        f"Invalid PTAX pair '{symbol}'. PTAX rates are quoted in BRL: use XXXBRL"
        " (e.g. 'USDBRL') or the foreign currency code (e.g. 'USD')."
    )


def build_ptax_url(currency: str, start_date: dateType, end_date: dateType) -> str:
    """Build the Olinda ``CotacaoMoedaPeriodo`` URL (dates as MM-DD-YYYY)."""
    return (
        f"{PTAX_BASE_URL}CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,"
        "dataFinalCotacao=@dataFinalCotacao)"
        f"?@moeda='{currency}'&@dataInicial='{start_date:%m-%d-%Y}'"
        f"&@dataFinalCotacao='{end_date:%m-%d-%Y}'&$format=json"
    )


class BcbCurrencyHistoricalQueryParams(CurrencyHistoricalQueryParams):
    """BCB PTAX Currency Historical Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    bulletin: Literal["close", "all"] = Field(
        default="close",
        description="'close' returns the official closing PTAX (one row per day);"
        " 'all' returns every bulletin of the day (opening and intermediate).",
    )


class BcbCurrencyHistoricalData(CurrencyHistoricalData):
    """BCB PTAX Currency Historical Data. ``close`` is the PTAX sell rate."""

    symbol: str = Field(description="Currency pair, quoted in BRL.")
    bid: float | None = Field(default=None, description="PTAX buy rate.")
    bulletin: str | None = Field(default=None, description="BCB bulletin type.")


class BcbCurrencyHistoricalFetcher(
    Fetcher[BcbCurrencyHistoricalQueryParams, list[BcbCurrencyHistoricalData]]
):
    """Fetch PTAX exchange rates from the BCB Olinda API."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> BcbCurrencyHistoricalQueryParams:
        """Transform query, defaulting to the last 30 days."""
        query = BcbCurrencyHistoricalQueryParams(**params)
        query.end_date = query.end_date or dateType.today()
        query.start_date = query.start_date or query.end_date - timedelta(
            days=DEFAULT_LOOKBACK_DAYS
        )
        return query

    @staticmethod
    async def aextract_data(
        query: BcbCurrencyHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the raw PTAX bulletins for each requested currency."""
        # pylint: disable=import-outside-toplevel
        import asyncio

        from openbb_core.provider.utils.helpers import amake_request

        async def response_callback(response, _):
            if "json" not in response.headers.get("Content-Type", ""):
                raise OpenBBError(
                    f"BCB Olinda returned {response.status} with non-JSON content."
                )
            return (await response.json())["value"]

        async def get_currency(currency: str) -> list[dict]:
            url = build_ptax_url(currency, query.start_date, query.end_date)  # type: ignore[arg-type]
            rows = await amake_request(
                url, timeout=30, response_callback=response_callback, **kwargs
            )
            return [{**row, "_currency": currency} for row in rows]  # type: ignore[dict-item]

        currencies = sorted(
            {split_ptax_symbol(s) for s in str(query.symbol).split(",") if s}
        )
        batches = await asyncio.gather(*[get_currency(c) for c in currencies])
        return [row for batch in batches for row in batch]

    @staticmethod
    def transform_data(
        query: BcbCurrencyHistoricalQueryParams, data: list[dict], **kwargs: Any
    ) -> list[BcbCurrencyHistoricalData]:
        """Keep the requested bulletins and map them to the standard model."""
        results: list[dict] = []
        for pair in str(query.symbol).split(","):
            if not pair:
                continue
            currency = split_ptax_symbol(pair)
            for row in data:
                if row["_currency"] != currency:
                    continue
                if query.bulletin == "close" and row["tipoBoletim"] != CLOSING_BULLETIN:
                    continue
                timestamp = datetime.fromisoformat(row["dataHoraCotacao"])
                results.append(
                    {
                        "date": timestamp.date()
                        if query.bulletin == "close"
                        else timestamp,
                        "symbol": f"{currency}BRL",
                        "close": row["cotacaoVenda"],
                        "bid": row["cotacaoCompra"],
                        "bulletin": row["tipoBoletim"],
                    }
                )

        if not results:
            raise OpenBBError(
                EmptyDataError(
                    "No PTAX data found for the requested pair(s) and dates."
                )
            )
        results.sort(key=lambda r: (r["symbol"], str(r["date"])))
        return [BcbCurrencyHistoricalData.model_validate(r) for r in results]
