"""The Tesouro provider registers its fetchers."""

from openbb_tesouro import tesouro_provider
from openbb_tesouro.models.direto import TesouroDiretoFetcher


def test_fetcher_dict():
    assert tesouro_provider.fetcher_dict == {"TesouroDireto": TesouroDiretoFetcher}
