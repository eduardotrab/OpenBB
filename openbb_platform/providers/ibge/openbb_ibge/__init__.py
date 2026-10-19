"""IBGE provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_ibge.models.aggregates import IbgeAggregatesFetcher
from openbb_ibge.models.world_news import IbgeWorldNewsFetcher

ibge_provider = Provider(
    name="ibge",
    website="https://www.ibge.gov.br",
    description="""IBGE (Instituto Brasileiro de Geografia e Estatística) open data:
SIDRA aggregate tables (IPCA, GDP, unemployment...) and Agência IBGE news.""",
    fetcher_dict={
        "IbgeAggregates": IbgeAggregatesFetcher,
        "WorldNews": IbgeWorldNewsFetcher,
    },
    repr_name="IBGE",
)
