"""Helpers for the BCB Olinda OData API."""

from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError

OLINDA_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/"


async def olinda_get(url: str, timeout: int = 30, **kwargs: Any) -> list[dict]:
    """GET an Olinda OData URL and return its ``value`` rows.

    Raises OpenBBError when the response is not JSON (BCB gateways answer
    blocked or invalid requests with HTML pages).
    """
    # pylint: disable=import-outside-toplevel
    from openbb_core.provider.utils.helpers import amake_request

    async def response_callback(response, _):
        if "json" not in response.headers.get("Content-Type", ""):
            raise OpenBBError(
                f"BCB Olinda returned {response.status} with non-JSON content."
            )
        return (await response.json())["value"]

    return await amake_request(  # type: ignore[return-value]
        url, timeout=timeout, response_callback=response_callback, **kwargs
    )
