"""The IBGE provider registers its fetchers."""

from openbb_ibge import ibge_provider
from openbb_ibge.models.aggregates import IbgeAggregatesFetcher
from openbb_ibge.models.world_news import IbgeWorldNewsFetcher


def test_fetcher_dict():
    assert ibge_provider.fetcher_dict == {
        "IbgeAggregates": IbgeAggregatesFetcher,
        "WorldNews": IbgeWorldNewsFetcher,
    }
