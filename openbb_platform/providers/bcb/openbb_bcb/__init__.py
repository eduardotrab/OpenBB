"""BCB provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher
from openbb_bcb.models.focus import BcbFocusFetcher

bcb_provider = Provider(
    name="bcb",
    website="https://www.bcb.gov.br",
    description="""Banco Central do Brasil (BCB) open data: PTAX exchange rates
and Focus market expectations from the Olinda OData API.""",
    fetcher_dict={
        "CurrencyHistorical": BcbCurrencyHistoricalFetcher,
        "BcbFocus": BcbFocusFetcher,
    },
    repr_name="Banco Central do Brasil (BCB)",
)
