"""IBGE fetcher tests against recorded HTTP cassettes (record with --record=all)."""

import datetime

import pytest
from openbb_core.app.service.user_service import UserService

from openbb_ibge.models.aggregates import IbgeAggregatesFetcher
from openbb_ibge.models.world_news import IbgeWorldNewsFetcher

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


@pytest.fixture(scope="module")
def vcr_config():
    return {"filter_headers": [("User-Agent", None)]}


@pytest.mark.record_http
def test_ibge_aggregates_fetcher(credentials=test_credentials):
    params = {"table": 1737, "variables": "63,2265", "periods": "202608-202609"}

    fetcher = IbgeAggregatesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_ibge_world_news_fetcher(credentials=test_credentials):
    params = {
        "start_date": datetime.date(2026, 10, 1),
        "end_date": datetime.date(2026, 10, 16),
        "limit": 3,
    }

    fetcher = IbgeWorldNewsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None
