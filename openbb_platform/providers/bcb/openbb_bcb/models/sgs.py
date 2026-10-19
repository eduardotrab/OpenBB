"""BCB SGS Time Series Model (Sistema Gerenciador de Séries Temporais)."""

# pylint: disable=unused-argument

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

SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs."
MAX_WINDOW_YEARS = 10
DEFAULT_LOOKBACK_DAYS = 365
SGS_SERIES = {
    "usd_brl": 1,
    "selic": 11,
    "cdi": 12,
    "igpm": 189,
    "selic_target": 432,
    "ipca": 433,
    "coop_singular_count": 25510,
    "coop_central_count": 25509,
    "coop_deposits_pf": 25517,
    "coop_credit_pf": 25518,
    "coop_credit_pj": 25519,
}
SGS_NAMES = {code: name for name, code in SGS_SERIES.items()}


def resolve_series(symbol: str) -> list[int]:
    """Resolve comma-separated SGS codes or known names to codes."""
    codes = []
    for item in (s.strip().lower() for s in symbol.split(",") if s.strip()):
        if item.isdigit():
            codes.append(int(item))
        elif item in SGS_SERIES:
            codes.append(SGS_SERIES[item])
        else:
            raise OpenBBError(
                f"Unknown SGS series '{item}'. Use a numeric SGS code or one of:"
                f" {', '.join(SGS_SERIES)}."
            )
    return codes


def build_sgs_url(code: int, start_date: dateType, end_date: dateType) -> str:
    """Build the SGS JSON URL (dates as dd/mm/yyyy)."""
    return (
        f"{SGS_BASE_URL}{code}/dados?formato=json"
        f"&dataInicial={start_date:%d/%m/%Y}&dataFinal={end_date:%d/%m/%Y}"
    )


def date_windows(start: dateType, end: dateType) -> list[tuple[dateType, dateType]]:
    """Split a range into windows of at most 10 calendar years (SGS limit)."""
    windows = []
    while start <= end:
        window_end = min(
            dateType(start.year + MAX_WINDOW_YEARS, start.month, start.day)
            - timedelta(days=1),
            end,
        )
        windows.append((start, window_end))
        start = window_end + timedelta(days=1)
    return windows


def parse_sgs_rows(code: int, raw: list[dict]) -> list[dict]:
    """Parse SGS rows (``data`` dd/mm/yyyy, ``valor`` decimal string)."""
    return [
        {
            "date": datetime.strptime(row["data"], "%d/%m/%Y").date(),
            "symbol": str(code),
            "value": float(row["valor"]),
        }
        for row in raw
        if row.get("valor") not in (None, "")
    ]


class BcbSgsQueryParams(QueryParams):
    """BCB SGS Time Series Query."""

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True, "choices": list(SGS_SERIES)}
    }

    symbol: str = Field(
        description="SGS series codes or names, comma-separated (e.g. '432,12' or"
        " 'selic_target,cdi'). Known names: " + ", ".join(SGS_SERIES) + "."
    )
    start_date: dateType | None = Field(
        default=None, description="Start date. Defaults to one year ago."
    )
    end_date: dateType | None = Field(
        default=None, description="End date. Defaults to today."
    )


class BcbSgsData(Data):
    """BCB SGS Time Series Data."""

    date: dateType = Field(description="Observation date.")
    symbol: str = Field(description="SGS series code.")
    name: str | None = Field(default=None, description="Known series name, if any.")
    value: float = Field(description="Observation value.")


class BcbSgsFetcher(Fetcher[BcbSgsQueryParams, list[BcbSgsData]]):
    """Fetch time series from the BCB SGS API."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> BcbSgsQueryParams:
        """Transform query, defaulting to the last year."""
        query = BcbSgsQueryParams(**params)
        query.end_date = query.end_date or dateType.today()
        query.start_date = query.start_date or query.end_date - timedelta(
            days=DEFAULT_LOOKBACK_DAYS
        )
        return query

    @staticmethod
    async def aextract_data(
        query: BcbSgsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch every series in 10-year windows."""
        # pylint: disable=import-outside-toplevel
        import asyncio

        from openbb_core.provider.utils.helpers import amake_request

        async def response_callback(response, _):
            if "json" not in response.headers.get("Content-Type", ""):
                raise OpenBBError(
                    "BCB SGS answered with an HTML page instead of data (HTTP"
                    f" {response.status}). The BCB firewall rejects requests from"
                    " some networks; try another network or the IPEA mirror."
                )
            return await response.json()

        async def get(code: int, start: dateType, end: dateType) -> list[dict]:
            raw = await amake_request(
                build_sgs_url(code, start, end),
                timeout=45,
                response_callback=response_callback,
                **kwargs,
            )
            return parse_sgs_rows(code, raw)  # type: ignore[arg-type]

        tasks = [
            get(code, start, end)
            for code in resolve_series(query.symbol)
            for start, end in date_windows(query.start_date, query.end_date)  # type: ignore[arg-type]
        ]
        return [row for batch in await asyncio.gather(*tasks) for row in batch]

    @staticmethod
    def transform_data(
        query: BcbSgsQueryParams, data: list[dict], **kwargs: Any
    ) -> list[BcbSgsData]:
        """Name known series and sort by series then date."""
        if not data:
            raise OpenBBError(EmptyDataError("No SGS observations found."))
        rows = sorted(data, key=lambda r: (int(r["symbol"]), r["date"]))
        return [
            BcbSgsData(**row, name=SGS_NAMES.get(int(row["symbol"]))) for row in rows
        ]
