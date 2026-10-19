"""Tesouro provider module."""

from openbb_core.provider.abstract.provider import Provider

from openbb_tesouro.models.direto import TesouroDiretoFetcher

tesouro_provider = Provider(
    name="tesouro",
    website="https://www.tesourotransparente.gov.br",
    description="""Tesouro Nacional open data: Tesouro Direto bond rates and prices
(Tesouro Transparente).""",
    fetcher_dict={"TesouroDireto": TesouroDiretoFetcher},
    repr_name="Tesouro Nacional",
)
