"""Unit tests for the BCB news model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_bcb.models.world_news import (
    BcbWorldNewsFetcher,
    BcbWorldNewsQueryParams,
    build_news_url,
    html_to_text,
)

PRESS = [
    {
        "titulo": "BC divulga o IBC-Br",
        "Id": 21285,
        "dataPublicacao": "2026-10-16T12:00:49Z",
    },
    {
        "titulo": "Liquidação de cooperativa",
        "Id": 21284,
        "dataPublicacao": "2026-10-15T18:00:00Z",
    },
    {"titulo": "Antiga", "Id": 21000, "dataPublicacao": "2026-06-01T10:00:00Z"},
]


def test_build_news_url_per_category():
    base = "https://www.bcb.gov.br/api/servico/sitebcb/"
    assert build_news_url(BcbWorldNewsQueryParams()) == base + "notasimprensa"
    assert build_news_url(BcbWorldNewsQueryParams(category="news")) == base + "noticias"
    assert (
        build_news_url(BcbWorldNewsQueryParams(category="copom", limit=3))
        == base + "copom/comunicados?quantidade=3"
    )
    assert (
        build_news_url(BcbWorldNewsQueryParams(category="copom"))
        == base + "copom/comunicados?quantidade=10"
    )


def test_html_to_text_strips_tags_and_entities():
    assert html_to_text(
        "<div><p>Os reajustes&nbsp;salariais</p><p>subiram</p></div>"
    ) == ("Os reajustes salariais subiram")


def test_press_releases_filtered_by_dates_newest_first():
    query = BcbWorldNewsQueryParams(start_date="2026-10-10", end_date="2026-10-16")
    rows = BcbWorldNewsFetcher.transform_data(query, PRESS)
    assert [(r.title, r.url, r.category) for r in rows] == [
        (
            "BC divulga o IBC-Br",
            "https://www.bcb.gov.br/detalhenoticia/21285/nota",
            "press_releases",
        ),
        (
            "Liquidação de cooperativa",
            "https://www.bcb.gov.br/detalhenoticia/21284/nota",
            "press_releases",
        ),
    ]
    assert rows[0].date == datetime.datetime(
        2026, 10, 16, 12, 0, 49, tzinfo=datetime.timezone.utc
    )


def test_limit_applies_after_date_filter():
    query = BcbWorldNewsQueryParams(
        start_date="2026-01-01", end_date="2026-10-16", limit=1
    )
    rows = BcbWorldNewsFetcher.transform_data(query, PRESS)
    assert [r.title for r in rows] == ["BC divulga o IBC-Br"]


def test_news_maps_body_image_and_excerpt():
    query = BcbWorldNewsQueryParams(
        category="news", start_date="2026-10-01", end_date="2026-10-16"
    )
    raw = [
        {
            "titulo": "BC divulga reajustes",
            "Id": 21280,
            "urlImg": {"Description": "x", "Url": "https://www.bcb.gov.br/img.png"},
            "dataPublicacao": "2026-10-06T10:34:47Z",
            "corpo": "<div>Os reajustes salariais</div>",
        }
    ]
    row = BcbWorldNewsFetcher.transform_data(query, raw)[0]
    assert (row.body, row.excerpt, row.images, row.url) == (
        "Os reajustes salariais",
        "Os reajustes salariais",
        "https://www.bcb.gov.br/img.png",
        "https://www.bcb.gov.br/detalhenoticia/21280/noticia",
    )


def test_copom_ignores_date_filter_and_keeps_meeting():
    query = BcbWorldNewsQueryParams(
        category="copom", start_date="2026-10-10", end_date="2026-10-16"
    )
    raw = [
        {
            "nro_reuniao": 281,
            "dataReferencia": "2026-09-16",
            "titulo": "281ª reunião - Copom reduz a taxa Selic para  13,75% a.a.",
        }
    ]
    row = BcbWorldNewsFetcher.transform_data(query, raw)[0]
    assert (row.date, row.title, row.meeting) == (
        datetime.datetime(2026, 9, 16),
        "281ª reunião - Copom reduz a taxa Selic para 13,75% a.a.",
        281,
    )


def test_no_articles_in_range_raises_empty_data():
    query = BcbWorldNewsQueryParams(start_date="2027-01-01", end_date="2027-01-31")
    with pytest.raises(OpenBBError):
        BcbWorldNewsFetcher.transform_data(query, PRESS)
