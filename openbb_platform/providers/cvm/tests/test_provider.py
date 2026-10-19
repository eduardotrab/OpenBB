"""The CVM provider registers its fetchers."""

from openbb_cvm import cvm_provider
from openbb_cvm.models.fund_daily import CvmFundDailyFetcher
from openbb_cvm.models.funds import CvmFundsFetcher


def test_fetcher_dict():
    assert cvm_provider.fetcher_dict == {
        "CvmFunds": CvmFundsFetcher,
        "CvmFundDaily": CvmFundDailyFetcher,
    }
