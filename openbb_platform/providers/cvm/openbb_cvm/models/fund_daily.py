"""CVM Fund Daily Report Model (Informe Diário de Fundos)."""

# pylint: disable=unused-argument

import csv
import io
import zipfile
from datetime import (
    date as dateType,
    timedelta,
)
from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_cvm.utils.helpers import CVM_DATA_URL, digits

DAILY_URL = f"{CVM_DATA_URL}FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{{month}}.zip"
CACHE_TTL_HOURS = 12
DEFAULT_LOOKBACK_DAYS = 30


def daily_report_urls(start: dateType, end: dateType) -> list[str]:
    """Return one monthly zip URL per month between ``start`` and ``end``."""
    urls, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        urls.append(DAILY_URL.format(month=f"{year}{month:02d}"))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return urls


def _float(value: str) -> float | None:
    return float(value) if value else None


def parse_daily_zip(content: bytes, cnpjs: set[str]) -> list[dict]:
    """Parse a monthly zip, keeping only rows of the requested CNPJs (digits)."""
    rows = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in archive.namelist():
            text = archive.read(name).decode("latin-1")
            for row in csv.DictReader(io.StringIO(text), delimiter=";"):
                if digits(row["CNPJ_FUNDO_CLASSE"]) not in cnpjs:
                    continue
                rows.append(
                    {
                        "date": dateType.fromisoformat(row["DT_COMPTC"]),
                        "cnpj": row["CNPJ_FUNDO_CLASSE"],
                        "fund_type": row["TP_FUNDO_CLASSE"],
                        "subclass": row.get("ID_SUBCLASSE") or None,
                        "total_value": _float(row["VL_TOTAL"]),
                        "quota": _float(row["VL_QUOTA"]),
                        "net_assets": _float(row["VL_PATRIM_LIQ"]),
                        "inflows": _float(row["CAPTC_DIA"]),
                        "outflows": _float(row["RESG_DIA"]),
                        "shareholders": int(row["NR_COTST"])
                        if row["NR_COTST"]
                        else None,
                    }
                )
    return rows


class CvmFundDailyQueryParams(QueryParams):
    """CVM Fund Daily Report Query."""

    __json_schema_extra__ = {"cnpj": {"multiple_items_allowed": True}}

    cnpj: str = Field(
        description="Fund (class) CNPJ, with or without punctuation; comma-separated"
        " for several funds."
    )
    start_date: dateType | None = Field(
        default=None, description="Start date. Defaults to 30 days ago."
    )
    end_date: dateType | None = Field(
        default=None, description="End date. Defaults to today."
    )
    use_cache: bool = Field(
        default=True, description="Cache monthly files on disk for 12 hours."
    )


class CvmFundDailyData(Data):
    """CVM Fund Daily Report Data (values in BRL)."""

    date: dateType = Field(description="Reference date (DT_COMPTC).")
    cnpj: str = Field(description="Fund (class) CNPJ.")
    fund_type: str | None = Field(default=None, description="Fund / class type.")
    subclass: str | None = Field(default=None, description="Subclass id, if any.")
    total_value: float | None = Field(
        default=None, description="Portfolio total value."
    )
    quota: float | None = Field(default=None, description="Quota value.")
    net_assets: float | None = Field(default=None, description="Net assets (PL).")
    inflows: float | None = Field(default=None, description="Daily subscriptions.")
    outflows: float | None = Field(default=None, description="Daily redemptions.")
    shareholders: int | None = Field(
        default=None, description="Number of shareholders."
    )


class CvmFundDailyFetcher(Fetcher[CvmFundDailyQueryParams, list[CvmFundDailyData]]):
    """Fetch daily fund reports (quota, net assets, flows) from the CVM."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> CvmFundDailyQueryParams:
        """Transform query, defaulting to the last 30 days."""
        query = CvmFundDailyQueryParams(**params)
        query.end_date = query.end_date or dateType.today()
        query.start_date = query.start_date or query.end_date - timedelta(
            days=DEFAULT_LOOKBACK_DAYS
        )
        return query

    @staticmethod
    async def aextract_data(
        query: CvmFundDailyQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Download the monthly zips in the range and keep the requested funds."""
        # pylint: disable=import-outside-toplevel
        import asyncio

        from openbb_cvm.utils.helpers import download

        cnpjs = {digits(c) for c in query.cnpj.split(",") if digits(c)}
        urls = daily_report_urls(query.start_date, query.end_date)  # type: ignore[arg-type]
        contents = await asyncio.gather(
            *[download(u, CACHE_TTL_HOURS, query.use_cache, **kwargs) for u in urls]
        )
        return [row for c in contents if c for row in parse_daily_zip(c, cnpjs)]

    @staticmethod
    def transform_data(
        query: CvmFundDailyQueryParams, data: list[dict], **kwargs: Any
    ) -> list[CvmFundDailyData]:
        """Filter by date range and sort by fund then date."""
        rows = [
            r
            for r in data
            if query.start_date <= r["date"] <= query.end_date  # type: ignore[operator]
        ]
        if not rows:
            raise OpenBBError(
                EmptyDataError("No CVM daily reports found for the fund(s) and dates.")
            )
        rows.sort(key=lambda r: (r["cnpj"], r["date"]))
        return [CvmFundDailyData(**r) for r in rows]
