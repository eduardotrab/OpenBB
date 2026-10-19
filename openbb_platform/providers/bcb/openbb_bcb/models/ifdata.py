"""BCB IF.data Model: quarterly financial data of institutions (cooperatives first)."""

# pylint: disable=unused-argument

import calendar
import re
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
from pydantic import Field, field_validator

from openbb_bcb.utils.olinda import OLINDA_BASE_URL

IFDATA_BASE_URL = f"{OLINDA_BASE_URL}IFDATA/versao/v1/odata/"
INSTITUTION_TYPES = {"prudential": 1, "financial": 2, "individual": 3, "fx": 4}
COOPERATIVE_SEGMENTS = ("B3S", "B3C")
REPORTS = {
    1: "Resumo",
    2: "Ativo",
    3: "Passivo",
    4: "Demonstração de Resultado",
    5: "Informações de Capital",
    6: "Segmentação",
    7: "Carteira de Crédito Ativa - Por indexador",
    8: "Carteira de crédito ativa - por nível de risco da operação",
    9: "Carteira de crédito ativa - por região geográfica",
    10: "Carteira de crédito ativa - quantidade de clientes e de operações",
    11: "Carteira de crédito ativa Pessoa Física - modalidade e prazo de vencimento",
    12: "Carteira de crédito ativa Pessoa Jurídica - por atividade econômica (CNAE)",
    13: "Carteira de crédito ativa Pessoa Jurídica - modalidade e prazo de vencimento",
    14: "Carteira de crédito ativa Pessoa Jurídica - por porte do tomador",
    15: "Movimentação de Câmbio no Trimestre",
    16: "Carteira de crédito ativa - por carteiras de instrumentos financeiros",
}
PUBLICATION_LAG_DAYS = 75
CACHE_TTL_DAYS = 7


def latest_available_period(today: dateType) -> str:
    """Return the last quarter end (YYYYMM) at least 75 days before ``today``."""
    cutoff = today - timedelta(days=PUBLICATION_LAG_DAYS)
    year, month = cutoff.year, cutoff.month - cutoff.month % 3
    if month == cutoff.month and cutoff.day < calendar.monthrange(year, month)[1]:
        month -= 3
    if month <= 0:
        year, month = year - 1, month + 12
    return f"{year}{month:02d}"


class BcbIfDataQueryParams(QueryParams):
    """BCB IF.data Query."""

    __json_schema_extra__ = {"report": {"choices": list(REPORTS)}}

    period: str | None = Field(
        default=None,
        description="Quarter end as YYYYMM or YYYY-MM (e.g. '202606')."
        " Defaults to the latest quarter expected to be published.",
    )
    report: int = Field(
        default=1,
        description="IF.data report number: "
        + "; ".join(f"{k} = {v}" for k, v in REPORTS.items()),
    )
    institution_type: Literal["prudential", "financial", "individual", "fx"] = Field(
        default="individual",
        description="'individual' institutions (cooperatives report here),"
        " 'prudential' or 'financial' conglomerates, or 'fx' operations.",
    )
    segment: Literal["cooperatives", "all"] = Field(
        default="cooperatives",
        description="'cooperatives' keeps credit cooperatives (singular and"
        " central); 'all' keeps every institution.",
    )
    institution: str | None = Field(
        default=None,
        description="One institution: CNPJ (base 8 digits or full) or IF.data code.",
    )
    uf: str | None = Field(default=None, description="State (UF) filter, e.g. 'SP'.")
    use_cache: bool = Field(
        default=True, description="Cache responses on disk for 7 days."
    )

    @field_validator("period", mode="before")
    @classmethod
    def validate_period(cls, v):
        """Normalize to YYYYMM and require a quarter-end month."""
        if v is None:
            return v
        digits = re.sub(r"\D", "", str(v))[:6]
        if len(digits) != 6 or digits[4:] not in ("03", "06", "09", "12"):
            raise ValueError(f"period must be a quarter end (YYYYMM), got '{v}'.")
        return digits

    @field_validator("institution", mode="before")
    @classmethod
    def validate_institution(cls, v):
        """Reduce a CNPJ to its 8-digit base; keep IF.data codes as given."""
        if v is None:
            return v
        cleaned = re.sub(r"[^0-9A-Za-z]", "", str(v)).upper()
        return cleaned[:8] if cleaned.isdigit() and len(cleaned) >= 8 else cleaned

    @field_validator("uf", mode="before")
    @classmethod
    def validate_uf(cls, v):
        """Uppercase the UF."""
        return v.upper() if isinstance(v, str) else v


class BcbIfDataData(Data):
    """BCB IF.data Data (long format: one row per institution and column)."""

    period: dateType = Field(description="Quarter end date.")
    institution: str = Field(description="IF.data institution code (CNPJ base).")
    name: str | None = Field(default=None, description="Institution name.")
    segment: str | None = Field(
        default=None,
        description="IF.data segment (Tcb): B3S = singular credit cooperative,"
        " B3C = central cooperative.",
    )
    uf: str | None = Field(default=None, description="State (UF).")
    city: str | None = Field(default=None, description="City.")
    report: str = Field(description="Report name.")
    group: str | None = Field(default=None, description="Column group.")
    account: str | None = Field(default=None, description="Accounting code.")
    column: str = Field(description="Column (indicator) name.")
    value: float | None = Field(default=None, description="Balance / value.")


def _odata_filter(condition: str | None) -> str:
    return f"&$filter={quote(condition, safe='')}" if condition else ""


def build_cadastro_url(query: BcbIfDataQueryParams) -> str:
    """Build the IF.data cadastro URL, filtering server-side when possible."""
    if query.institution:
        condition = f"CodInst eq '{query.institution}'"
    elif query.segment == "cooperatives":
        condition = " or ".join(f"Tcb eq '{s}'" for s in COOPERATIVE_SEGMENTS)
    else:
        condition = None
    return (
        f"{IFDATA_BASE_URL}IfDataCadastro(AnoMes=@AnoMes)?@AnoMes={query.period}"
        f"{_odata_filter(condition)}&$format=json"
    )


def build_values_url(query: BcbIfDataQueryParams) -> str:
    """Build the IF.data values URL for one report."""
    condition = f"CodInst eq '{query.institution}'" if query.institution else None
    return (
        f"{IFDATA_BASE_URL}IfDataValores(AnoMes=@AnoMes,TipoInstituicao="
        "@TipoInstituicao,Relatorio=@Relatorio)"
        f"?@AnoMes={query.period}"
        f"&@TipoInstituicao={INSTITUTION_TYPES[query.institution_type]}"
        f"&@Relatorio='{query.report}'{_odata_filter(condition)}&$format=json"
    )


class BcbIfDataFetcher(Fetcher[BcbIfDataQueryParams, list[BcbIfDataData]]):
    """Fetch IF.data reports from the BCB Olinda API, joined with the cadastro."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> BcbIfDataQueryParams:
        """Transform query, defaulting to the latest published quarter."""
        query = BcbIfDataQueryParams(**params)
        query.period = query.period or latest_available_period(dateType.today())
        return query

    @staticmethod
    async def aextract_data(
        query: BcbIfDataQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> dict[str, list[dict]]:
        """Fetch the cadastro and the report values (cached on disk)."""
        # pylint: disable=import-outside-toplevel
        import asyncio

        from openbb_bcb.utils.cache import cached_rows
        from openbb_bcb.utils.olinda import olinda_get

        async def get(url: str) -> list[dict]:
            return await cached_rows(
                url,
                lambda: olinda_get(url, timeout=120, **kwargs),
                ttl_days=CACHE_TTL_DAYS,
                use_cache=query.use_cache,
            )

        cadastro, values = await asyncio.gather(
            get(build_cadastro_url(query)), get(build_values_url(query))
        )
        return {"cadastro": cadastro, "values": values}

    @staticmethod
    def transform_data(
        query: BcbIfDataQueryParams, data: dict[str, list[dict]], **kwargs: Any
    ) -> list[BcbIfDataData]:
        """Join values with the cadastro and apply the UF filter."""
        cadastro = {row["CodInst"]: row for row in data["cadastro"]}
        year, month = int(str(query.period)[:4]), int(str(query.period)[4:])
        period = dateType(year, month, calendar.monthrange(year, month)[1])
        results = []
        for row in data["values"]:
            inst = cadastro.get(row["CodInst"])
            if inst is None or (query.uf and inst.get("Uf") != query.uf):
                continue
            results.append(
                BcbIfDataData(
                    period=period,
                    institution=row["CodInst"],
                    name=inst.get("NomeInstituicao"),
                    segment=inst.get("Tcb"),
                    uf=inst.get("Uf"),
                    city=inst.get("Municipio"),
                    report=row["NomeRelatorio"],
                    group=row.get("Grupo"),
                    account=row.get("Conta"),
                    column=row["NomeColuna"],
                    value=row.get("Saldo"),
                )
            )
        if not results:
            raise OpenBBError(EmptyDataError("No IF.data rows found for the query."))
        return results
