"""The BCB provider registers its fetchers."""

from openbb_bcb import bcb_provider
from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher
from openbb_bcb.models.focus import BcbFocusFetcher
from openbb_bcb.models.ifdata import BcbIfDataFetcher
from openbb_bcb.models.sgs import BcbSgsFetcher


def test_fetcher_dict():
    assert bcb_provider.fetcher_dict == {
        "CurrencyHistorical": BcbCurrencyHistoricalFetcher,
        "BcbFocus": BcbFocusFetcher,
        "BcbIfData": BcbIfDataFetcher,
        "BcbSgs": BcbSgsFetcher,
    }
