"""BCB News Model: press releases, news and Copom statements."""

# pylint: disable=unused-argument

import html
import re
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

SITE_API_URL = "https://www.bcb.gov.br/api/servico/sitebcb/"
DETAIL_URL = "https://www.bcb.gov.br/detalhenoticia/{id}/{kind}"
COPOM_URL = "https://www.bcb.gov.br/publicacoes/comunicadoscopom"
DEFAULT_COPOM_LIMIT = 10
EXCERPT_CHARS = 300


def html_to_text(content: str) -> str:
    """Strip HTML tags and entities, collapsing whitespace."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", content))
    return " ".join(text.replace("\xa0", " ").split())


def build_news_url(query: "BcbWorldNewsQueryParams") -> str:
    """Build the BCB site API URL for the category."""
    if query.category == "copom":
        return f"{SITE_API_URL}copom/comunicados?quantidade={query.limit or DEFAULT_COPOM_LIMIT}"
    return SITE_API_URL + ("noticias" if query.category == "news" else "notasimprensa")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class BcbWorldNewsQueryParams(WorldNewsQueryParams):
    """BCB News Query."""

    category: Literal["press_releases", "news", "copom"] = Field(
        default="press_releases",
        description="'press_releases' (notas à imprensa), 'news' (notícias) or"
        " 'copom' (Copom statements: the latest `limit` meetings, default 10,"
        " ignoring the date range).",
    )


class BcbWorldNewsData(WorldNewsData):
    """BCB News Data."""

    category: str = Field(description="BCB news category.")
    meeting: int | None = Field(default=None, description="Copom meeting number.")


class BcbWorldNewsFetcher(Fetcher[BcbWorldNewsQueryParams, list[BcbWorldNewsData]]):
    """Fetch press releases, news and Copom statements from the BCB site API."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> BcbWorldNewsQueryParams:
        """Transform query."""
        return BcbWorldNewsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: BcbWorldNewsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the raw items (the site API returns the latest 100)."""
        # pylint: disable=import-outside-toplevel
        from openbb_core.provider.utils.helpers import amake_request

        async def response_callback(response, _):
            if "json" not in response.headers.get("Content-Type", ""):
                raise OpenBBError(
                    f"BCB site API returned {response.status} with non-JSON content."
                )
            return (await response.json())["conteudo"]

        return await amake_request(  # type: ignore[return-value]
            build_news_url(query),
            timeout=30,
            response_callback=response_callback,
            **kwargs,
        )

    @staticmethod
    def transform_data(
        query: BcbWorldNewsQueryParams, data: list[dict], **kwargs: Any
    ) -> list[BcbWorldNewsData]:
        """Map items to the standard model, filtering dates (except Copom)."""
        results = []
        for item in data:
            title = " ".join(item["titulo"].split())
            if query.category == "copom":
                results.append(
                    BcbWorldNewsData(
                        date=datetime.fromisoformat(item["dataReferencia"]),
                        title=title,
                        url=COPOM_URL,
                        category="copom",
                        meeting=item.get("nro_reuniao"),
                    )
                )
                continue
            date = _parse_timestamp(item["dataPublicacao"])
            if not query.start_date <= date.date() <= query.end_date:  # type: ignore[operator]
                continue
            body = html_to_text(item["corpo"]) if item.get("corpo") else None
            results.append(
                BcbWorldNewsData(
                    date=date,
                    title=title,
                    body=body,
                    excerpt=body[:EXCERPT_CHARS] if body else None,
                    images=(item.get("urlImg") or {}).get("Url"),
                    url=DETAIL_URL.format(
                        id=item["Id"],
                        kind="noticia" if query.category == "news" else "nota",
                    ),
                    category=query.category,
                )
            )
        if not results:
            raise OpenBBError(EmptyDataError("No BCB news found for the query."))
        results.sort(key=lambda r: r.date, reverse=True)
        return results[: query.limit] if query.limit else results
