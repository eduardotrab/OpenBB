"""IBGE Aggregates Model (SIDRA tables via servicodados API v3)."""

# pylint: disable=unused-argument

from typing import Any
from urllib.parse import quote

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_ibge.utils.http import IBGE_API_URL

ABSOLUTE_ZERO = "-"  # SIDRA convention; "...", "..", "X", "Z" mean unavailable


def parse_sidra_value(value: str | None) -> float | None:
    """Parse a SIDRA value: '-' is an absolute zero, other markers are None."""
    if value == ABSOLUTE_ZERO:
        return 0.0
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class IbgeAggregatesQueryParams(QueryParams):
    """IBGE Aggregates Query."""

    __json_schema_extra__ = {
        "variables": {"multiple_items_allowed": True},
        "periods": {"multiple_items_allowed": True},
        "locations": {"multiple_items_allowed": True},
        "classification": {"multiple_items_allowed": True},
    }

    table: int = Field(
        description="SIDRA table (agregado) number, e.g. 1737 (IPCA), 5932 (GDP"
        " quarterly change), 6381 (unemployment rate)."
    )
    variables: str = Field(
        default="allxp",
        description="Variable ids, comma-separated (e.g. '63,2265'), or 'allxp'"
        " (IBGE keyword: every variable).",
    )
    periods: str = Field(
        default="-12",
        description="'-N' for the last N periods, a range 'YYYYMM-YYYYMM', or a"
        " comma-separated list, in the table's period format.",
    )
    level: str = Field(
        default="N1",
        description="Territorial level: N1 Brazil, N2 region, N3 state (UF),"
        " N6 municipality, N7 metropolitan region...",
    )
    locations: str = Field(
        default="all", description="Location ids, comma-separated, or 'all'."
    )
    classification: str | None = Field(
        default=None,
        description="Optional classification filter in IBGE syntax, e.g."
        " '315[7169]' (IPCA general index).",
    )


class IbgeAggregatesData(Data):
    """IBGE Aggregates Data (long format)."""

    period: str = Field(description="Period code as published (YYYY, YYYYMM, YYYYQQ).")
    variable_id: str = Field(description="Variable id.")
    variable: str = Field(description="Variable name.")
    unit: str | None = Field(default=None, description="Unit of measure.")
    level: str = Field(description="Territorial level id.")
    location_id: str = Field(description="Location id.")
    location: str = Field(description="Location name.")
    classification: str | None = Field(
        default=None, description="Classification and category, when present."
    )
    value: float | None = Field(
        default=None, description="Value (SIDRA '-' = 0; None when unavailable)."
    )


def build_aggregates_url(query: IbgeAggregatesQueryParams) -> str:
    """Build the servicodados aggregates URL."""
    variables = "%7C".join(v.strip() for v in query.variables.split(","))
    url = (
        f"{IBGE_API_URL}agregados/{query.table}/periodos/{query.periods}"
        f"/variaveis/{variables}"
        f"?localidades={quote(f'{query.level}[{query.locations}]', safe=',')}"
    )
    if query.classification:
        url += f"&classificacao={quote(query.classification, safe=',')}"
    return url


def _classification(result: dict) -> str | None:
    parts = [
        f"{c['nome']}: {', '.join(c['categoria'].values())}"
        for c in result.get("classificacoes") or []
    ]
    return "; ".join(parts) or None


class IbgeAggregatesFetcher(
    Fetcher[IbgeAggregatesQueryParams, list[IbgeAggregatesData]]
):
    """Fetch SIDRA aggregate tables from the IBGE API."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> IbgeAggregatesQueryParams:
        """Transform query."""
        return IbgeAggregatesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: IbgeAggregatesQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the raw aggregate response."""
        from openbb_ibge.utils.http import ibge_get

        return await ibge_get(build_aggregates_url(query), **kwargs)

    @staticmethod
    def transform_data(
        query: IbgeAggregatesQueryParams, data: list[dict], **kwargs: Any
    ) -> list[IbgeAggregatesData]:
        """Flatten variables x results x series into one row per period."""
        rows = [
            IbgeAggregatesData(
                period=period,
                variable_id=variable["id"],
                variable=variable["variavel"],
                unit=variable.get("unidade"),
                level=series["localidade"]["nivel"]["id"],
                location_id=series["localidade"]["id"],
                location=series["localidade"]["nome"],
                classification=_classification(result),
                value=parse_sidra_value(value),
            )
            for variable in data
            for result in variable["resultados"]
            for series in result["series"]
            for period, value in series["serie"].items()
        ]
        if not rows:
            raise OpenBBError(EmptyDataError("No IBGE data found for the query."))
        return rows
