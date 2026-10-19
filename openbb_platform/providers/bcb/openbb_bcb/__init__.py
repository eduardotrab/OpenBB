"""BCB provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_bcb.models.currency_historical import BcbCurrencyHistoricalFetcher

bcb_provider = Provider(
    name="bcb",
    website="https://www.bcb.gov.br",
    description="""Banco Central do Brasil (BCB) open data: PTAX exchange rates
from the Olinda OData API.""",
    fetcher_dict={
        "CurrencyHistorical": BcbCurrencyHistoricalFetcher,
    },
    repr_name="Banco Central do Brasil (BCB)",
)
