"""Unit tests for the IBGE news model (no network)."""

import datetime

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_ibge.models.world_news import (
    IbgeWorldNewsFetcher,
    IbgeWorldNewsQueryParams,
    build_news_url,
)


def test_build_news_url_uses_mm_dd_yyyy_range_and_limit():
    query = IbgeWorldNewsQueryParams(
        start_date="2026-10-01", end_date="2026-10-16", limit=5
    )
    assert build_news_url(query) == (
        "https://servicodados.ibge.gov.br/api/v3/noticias/"
        "?qtd=5&de=10-01-2026&ate=10-16-2026"
    )


def test_build_news_url_default_limit_and_release_type():
    query = IbgeWorldNewsQueryParams(
        start_date="2026-10-01", end_date="2026-10-16", category="release"
    )
    assert build_news_url(query) == (
        "https://servicodados.ibge.gov.br/api/v3/noticias/"
        "?qtd=50&de=10-01-2026&ate=10-16-2026&tipo=release"
    )


def test_transform_data_maps_items():
    query = IbgeWorldNewsQueryParams()
    raw = [
        {
            "id": 48310,
            "tipo": "Notícia",
            "titulo": "IBGE debate uso de dados",
            "introducao": "Como garantir...",
            "data_publicacao": "16/10/2026 01:28:30",
            "editorias": "ibge",
            "imagens": '{"image_intro":"images\\/agenciadenoticias\\/x.jpg"}',
            "link": "http://agenciadenoticias.ibge.gov.br/agencia-noticias/n.html",
        }
    ]
    row = IbgeWorldNewsFetcher.transform_data(query, raw)[0]
    assert (row.date, row.title, row.excerpt, row.url, row.images, row.category) == (
        datetime.datetime(2026, 10, 16, 1, 28, 30),
        "IBGE debate uso de dados",
        "Como garantir...",
        "https://agenciadenoticias.ibge.gov.br/agencia-noticias/n.html",
        "https://agenciadenoticias.ibge.gov.br/images/agenciadenoticias/x.jpg",
        "Notícia",
    )


def test_transform_data_without_rows_raises_empty_data():
    with pytest.raises(OpenBBError):
        IbgeWorldNewsFetcher.transform_data(IbgeWorldNewsQueryParams(), [])
