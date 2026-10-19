"""Receita Federal provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_receita.models.revenue import ReceitaRevenueFetcher

receita_provider = Provider(
    name="receita",
    website="https://www.gov.br/receitafederal",
    description="""Receita Federal do Brasil open data: monthly federal tax revenue
by state (arrecadação federal).""",
    fetcher_dict={"ReceitaRevenue": ReceitaRevenueFetcher},
    repr_name="Receita Federal",
)
