"""Small helper for BCB Olinda OData queries (spaces must be %20, not '+')."""

import urllib.parse

import requests

BASE = "https://olinda.bcb.gov.br/olinda/servico"


def consultar(
    caminho: str, params: dict, sessao: requests.Session, timeout: int = 300
) -> list[dict]:
    """GET `<BASE>/<caminho>` with OData params; returns the `value` list."""
    query = urllib.parse.urlencode(
        {"$format": "json", **params}, quote_via=urllib.parse.quote, safe="$,'@()"
    )
    resposta = sessao.get(f"{BASE}/{caminho}?{query}", timeout=timeout)
    resposta.raise_for_status()
    return resposta.json()["value"]
