"""IBGE News Model (Agência IBGE Notícias)."""

# pylint: disable=unused-argument

import json
from datetime import datetime
from typing import Any, Literal

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.world_news import (
    WorldNewsData,
    WorldNewsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_ibge.utils.http import IBGE_API_URL

AGENCY_URL = "https://agenciadenoticias.ibge.gov.br/"
DEFAULT_LIMIT = 50


class IbgeWorldNewsQueryParams(WorldNewsQueryParams):
    """IBGE News Query."""

    category: Literal["all", "noticia", "release"] = Field(
        default="all",
        description="'noticia' (news), 'release' (press releases) or 'all'.",
    )


class IbgeWorldNewsData(WorldNewsData):
    """IBGE News Data."""

    category: str | None = Field(default=None, description="Item type.")
    topics: str | None = Field(default=None, description="Editorial topics.")


def build_news_url(query: IbgeWorldNewsQueryParams) -> str:
    """Build the IBGE news URL (dates as MM-DD-YYYY)."""
    url = (
        f"{IBGE_API_URL}noticias/?qtd={query.limit or DEFAULT_LIMIT}"
        f"&de={query.start_date:%m-%d-%Y}&ate={query.end_date:%m-%d-%Y}"
    )
    return url if query.category == "all" else f"{url}&tipo={query.category}"


def _image_url(images: str | None) -> str | None:
    try:
        path = json.loads(images or "{}").get("image_intro")
    except json.JSONDecodeError:
        return None
    return f"{AGENCY_URL}{path}" if path else None


class IbgeWorldNewsFetcher(Fetcher[IbgeWorldNewsQueryParams, list[IbgeWorldNewsData]]):
    """Fetch Agência IBGE news."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> IbgeWorldNewsQueryParams:
        """Transform query."""
        return IbgeWorldNewsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: IbgeWorldNewsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the raw news items."""
        from openbb_ibge.utils.http import ibge_get

        return (await ibge_get(build_news_url(query), **kwargs))["items"]

    @staticmethod
    def transform_data(
        query: IbgeWorldNewsQueryParams, data: list[dict], **kwargs: Any
    ) -> list[IbgeWorldNewsData]:
        """Map items to the standard model."""
        if not data:
            raise OpenBBError(EmptyDataError("No IBGE news found for the query."))
        return [
            IbgeWorldNewsData(
                date=datetime.strptime(item["data_publicacao"], "%d/%m/%Y %H:%M:%S"),
                title=item["titulo"],
                excerpt=item.get("introducao"),
                url=(item.get("link") or "").replace("http://", "https://", 1) or None,
                images=_image_url(item.get("imagens")),
                category=item.get("tipo"),
                topics=item.get("editorias") or None,
            )
            for item in data
        ]
