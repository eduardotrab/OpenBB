"""BCB provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher
from openbb_bcb.models.focus import BcbFocusFetcher
from openbb_bcb.models.ifdata import BcbIfDataFetcher
from openbb_bcb.models.sgs import BcbSgsFetcher

bcb_provider = Provider(
    name="bcb",
    website="https://www.bcb.gov.br",
    description="""Banco Central do Brasil (BCB) open data: PTAX exchange rates
Focus market expectations and IF.data (quarterly data of financial
institutions, credit cooperatives first) from the Olinda OData API, and SGS time series.""",
    fetcher_dict={
        "CurrencyHistorical": BcbCurrencyHistoricalFetcher,
        "BcbFocus": BcbFocusFetcher,
        "BcbIfData": BcbIfDataFetcher,
        "BcbSgs": BcbSgsFetcher,
    },
    repr_name="Banco Central do Brasil (BCB)",
)
