"""CVM Funds Model: registry of investment fund classes (RCVM 175)."""

# pylint: disable=unused-argument

import csv
import io
import zipfile
from datetime import date as dateType
from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_cvm.utils.helpers import CVM_DATA_URL, digits, fold

REGISTRY_URL = f"{CVM_DATA_URL}FI/CAD/DADOS/registro_fundo_classe.zip"
CLASSES_FILE = "registro_classe.csv"
ACTIVE_STATUS = "Em Funcionamento Normal"
CACHE_TTL_HOURS = 24


def _date(value: str) -> dateType | None:
    return dateType.fromisoformat(value) if value else None


def parse_classes(content: bytes) -> list[dict]:
    """Parse ``registro_classe.csv`` from the registry zip."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        text = archive.read(CLASSES_FILE).decode("latin-1")
    return [
        {
            "cnpj": row["CNPJ_Classe"],
            "name": row["Denominacao_Social"],
            "cvm_code": row["Codigo_CVM"] or None,
            "class_type": row["Tipo_Classe"] or None,
            "status": row["Situacao"] or None,
            "classification": row["Classificacao"] or None,
            "anbima_classification": row["Classificacao_Anbima"] or None,
            "benchmark": row["Indicador_Desempenho"] or None,
            "target_public": row["Publico_Alvo"] or None,
            "exclusive": row["Exclusivo"] == "S",
            "net_assets": float(row["Patrimonio_Liquido"])
            if row["Patrimonio_Liquido"]
            else None,
            "net_assets_date": _date(row["Data_Patrimonio_Liquido"]),
            "start_date": _date(row["Data_Inicio"]),
        }
        for row in csv.DictReader(io.StringIO(text), delimiter=";")
    ]


class CvmFundsQueryParams(QueryParams):
    """CVM Funds Query."""

    search: str | None = Field(
        default=None,
        description="Text to search in the fund class name (case and accent"
        " insensitive), e.g. 'sicoob'.",
    )
    cnpj: str | None = Field(default=None, description="Fund class CNPJ.")
    active_only: bool = Field(
        default=True, description="Keep only classes 'Em Funcionamento Normal'."
    )
    use_cache: bool = Field(
        default=True, description="Cache the registry file on disk for 24 hours."
    )


class CvmFundsData(Data):
    """CVM Funds Data."""

    cnpj: str = Field(description="Fund class CNPJ.")
    name: str = Field(description="Fund class name.")
    cvm_code: str | None = Field(default=None, description="CVM code.")
    class_type: str | None = Field(default=None, description="Class type.")
    status: str | None = Field(default=None, description="Registration status.")
    classification: str | None = Field(default=None, description="CVM classification.")
    anbima_classification: str | None = Field(
        default=None, description="ANBIMA classification."
    )
    benchmark: str | None = Field(default=None, description="Performance benchmark.")
    target_public: str | None = Field(default=None, description="Target investors.")
    exclusive: bool | None = Field(default=None, description="Exclusive fund.")
    net_assets: float | None = Field(default=None, description="Net assets (BRL).")
    net_assets_date: dateType | None = Field(
        default=None, description="Net assets reference date."
    )
    start_date: dateType | None = Field(default=None, description="Start of activity.")


class CvmFundsFetcher(Fetcher[CvmFundsQueryParams, list[CvmFundsData]]):
    """Search the CVM investment fund class registry."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> CvmFundsQueryParams:
        """Transform query."""
        return CvmFundsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: CvmFundsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Download (or read from cache) the registry and parse the classes."""
        from openbb_cvm.utils.helpers import download

        content = await download(
            REGISTRY_URL, CACHE_TTL_HOURS, query.use_cache, **kwargs
        )
        return parse_classes(content)

    @staticmethod
    def transform_data(
        query: CvmFundsQueryParams, data: list[dict], **kwargs: Any
    ) -> list[CvmFundsData]:
        """Apply the name, CNPJ and status filters."""
        search = fold(query.search) if query.search else None
        cnpj = digits(query.cnpj) if query.cnpj else None
        rows = [
            r
            for r in data
            if (not query.active_only or r["status"] == ACTIVE_STATUS)
            and (search is None or search in fold(r["name"]))
            and (cnpj is None or digits(r["cnpj"]) == cnpj)
        ]
        if not rows:
            raise OpenBBError(EmptyDataError("No CVM fund classes match the query."))
        return [CvmFundsData(**r) for r in rows]
