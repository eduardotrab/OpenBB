"""The BCB provider registers its fetchers."""

from openbb_bcb import bcb_provider
from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher
from openbb_bcb.models.focus import BcbFocusFetcher


def test_fetcher_dict():
    assert bcb_provider.fetcher_dict == {
        "CurrencyHistorical": BcbCurrencyHistoricalFetcher,
        "BcbFocus": BcbFocusFetcher,
    }
