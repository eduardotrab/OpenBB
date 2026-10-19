"""Live tests against the CVM open data portal (not in the default suite)."""

import datetime

import pytest
from openbb_core.app.service.user_service import UserService

from openbb_cvm.models.fund_daily import CvmFundDailyFetcher
from openbb_cvm.models.funds import CvmFundsFetcher

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


@pytest.mark.integration
def test_cvm_funds_fetcher_live(credentials=test_credentials):
    assert CvmFundsFetcher().test({"search": "sicoob"}, credentials) is None


@pytest.mark.integration
def test_cvm_fund_daily_fetcher_live(credentials=test_credentials):
    params = {
        "cnpj": "00.017.024/0001-53",
        "start_date": datetime.date(2026, 10, 1),
        "end_date": datetime.date(2026, 10, 15),
    }
    assert CvmFundDailyFetcher().test(params, credentials) is None
