"""BCB Focus Market Expectations Model."""

# pylint: disable=unused-argument

from datetime import (
    date as dateType,
    timedelta,
)
from typing import Any, Literal
from urllib.parse import quote

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_bcb.utils.olinda import OLINDA_BASE_URL

FOCUS_BASE_URL = f"{OLINDA_BASE_URL}Expectativas/versao/v1/odata/"
FOCUS_ENDPOINTS = {
    "annual": "ExpectativasMercadoAnuais",
    "monthly": "ExpectativaMercadoMensais",
    "selic": "ExpectativasMercadoSelic",
}
CALCULATION_BASES = {"30d": 0, "5d": 1}
FOCUS_INDICATORS = [
    "Balança comercial",
    "Conta corrente",
    "Câmbio",
    "Dívida bruta do governo geral",
    "Dívida líquida do setor público",
    "IGP-M",
    "IPCA",
    "IPCA Administrados",
    "IPCA Alimentação no domicílio",
    "IPCA Bens industrializados",
    "IPCA Livres",
    "IPCA Serviços",
    "Investimento direto no país",
    "PIB Agropecuária",
    "PIB Indústria",
    "PIB Serviços",
    "PIB Total",
    "Resultado nominal",
    "Resultado primário",
    "Selic",
    "Taxa de desocupação",
]
DEFAULT_LOOKBACK_DAYS = 30


class BcbFocusQueryParams(QueryParams):
    """BCB Focus Market Expectations Query."""

    __json_schema_extra__ = {"indicator": {"choices": FOCUS_INDICATORS}}

    indicator: str = Field(
        default="IPCA",
        description="Focus indicator, as named by the BCB (e.g. 'IPCA', 'PIB Total',"
        " 'Câmbio'). Ignored when frequency is 'selic'.",
    )
    frequency: Literal["annual", "monthly", "selic"] = Field(
        default="annual",
        description="'annual' (calendar-year expectations), 'monthly', or 'selic'"
        " (expected Selic per Copom meeting).",
    )
    calculation_base: Literal["30d", "5d"] = Field(
        default="30d",
        description="'30d' uses every forecast of the last 30 days; '5d' only the"
        " forecasts updated in the last 5 business days.",
    )
    start_date: dateType | None = Field(
        default=None, description="First survey date. Defaults to 30 days ago."
    )
    end_date: dateType | None = Field(
        default=None, description="Last survey date. Defaults to today."
    )


class BcbFocusData(Data):
    """BCB Focus Market Expectations Data."""

    __alias_dict__ = {
        "date": "Data",
        "indicator": "Indicador",
        "indicator_detail": "IndicadorDetalhe",
        "mean": "Media",
        "median": "Mediana",
        "std_dev": "DesvioPadrao",
        "min": "Minimo",
        "max": "Maximo",
        "respondents": "numeroRespondentes",
    }

    date: dateType = Field(description="Survey date.")
    indicator: str = Field(description="Indicator name.")
    indicator_detail: str | None = Field(
        default=None, description="Indicator detail (sub-indicator)."
    )
    reference: str = Field(
        description="Reference period: year (annual), MM/YYYY (monthly) or Copom"
        " meeting (selic, e.g. 'R6/2028')."
    )
    mean: float | None = Field(default=None, description="Mean forecast.")
    median: float | None = Field(default=None, description="Median forecast.")
    std_dev: float | None = Field(default=None, description="Standard deviation.")
    min: float | None = Field(default=None, description="Minimum forecast.")
    max: float | None = Field(default=None, description="Maximum forecast.")
    respondents: int | None = Field(default=None, description="Number of respondents.")


def build_focus_url(query: BcbFocusQueryParams) -> str:
    """Build the Olinda Focus URL with an OData filter for the query."""
    conditions = []
    if query.frequency != "selic":
        conditions.append(f"Indicador eq '{query.indicator}'")
    conditions += [
        f"Data ge '{query.start_date}'",
        f"Data le '{query.end_date}'",
        f"baseCalculo eq {CALCULATION_BASES[query.calculation_base]}",
    ]
    odata_filter = quote(" and ".join(conditions), safe="")
    return (
        f"{FOCUS_BASE_URL}{FOCUS_ENDPOINTS[query.frequency]}?$filter={odata_filter}"
        "&$orderby=Data%20desc&$format=json"
    )


class BcbFocusFetcher(Fetcher[BcbFocusQueryParams, list[BcbFocusData]]):
    """Fetch Focus market expectations from the BCB Olinda API."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> BcbFocusQueryParams:
        """Transform query, defaulting to the last 30 days."""
        query = BcbFocusQueryParams(**params)
        query.end_date = query.end_date or dateType.today()
        query.start_date = query.start_date or query.end_date - timedelta(
            days=DEFAULT_LOOKBACK_DAYS
        )
        return query

    @staticmethod
    async def aextract_data(
        query: BcbFocusQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the raw Focus rows."""
        from openbb_bcb.utils.olinda import olinda_get

        return await olinda_get(build_focus_url(query), timeout=60, **kwargs)

    @staticmethod
    def transform_data(
        query: BcbFocusQueryParams, data: list[dict], **kwargs: Any
    ) -> list[BcbFocusData]:
        """Map Olinda rows to the data model."""
        if not data:
            raise OpenBBError(
                EmptyDataError("No Focus expectations found for the query.")
            )
        mapped = ("DataReferencia", "Reuniao", "baseCalculo")
        return [
            BcbFocusData.model_validate(
                {
                    **{k: v for k, v in row.items() if k not in mapped},
                    "reference": row.get("DataReferencia") or row.get("Reuniao"),
                }
            )
            for row in data
        ]
