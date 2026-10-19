"""BCB fetcher tests against recorded HTTP cassettes (record with --record=all)."""

import datetime

import pytest
from openbb_core.app.service.user_service import UserService

from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher
from openbb_bcb.models.focus import BcbFocusFetcher

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


@pytest.fixture(scope="module")
def vcr_config():
    return {"filter_headers": [("User-Agent", None)]}


@pytest.mark.record_http
def test_bcb_currency_historical_fetcher(credentials=test_credentials):
    params = {
        "symbol": "USDBRL,EURBRL",
        "start_date": datetime.date(2026, 10, 13),
        "end_date": datetime.date(2026, 10, 16),
    }

    fetcher = BcbCurrencyHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_bcb_focus_fetcher(credentials=test_credentials):
    params = {
        "indicator": "IPCA",
        "start_date": datetime.date(2026, 10, 1),
        "end_date": datetime.date(2026, 10, 9),
    }

    fetcher = BcbFocusFetcher()
    result = fetcher.test(params, credentials)
    assert result is None
