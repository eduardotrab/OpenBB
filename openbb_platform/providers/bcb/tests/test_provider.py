"""The BCB provider registers its fetchers."""

from openbb_bcb import bcb_provider
from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher


def test_fetcher_dict():
    assert bcb_provider.fetcher_dict == {
        "CurrencyHistorical": BcbCurrencyHistoricalFetcher,
    }
