"""The Receita provider registers its fetchers."""

from openbb_receita import receita_provider
from openbb_receita.models.revenue import ReceitaRevenueFetcher


def test_fetcher_dict():
    assert receita_provider.fetcher_dict == {"ReceitaRevenue": ReceitaRevenueFetcher}
