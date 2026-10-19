"""HTTP helper for the IBGE servicodados API."""

from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError

IBGE_API_URL = "https://servicodados.ibge.gov.br/api/v3/"


async def ibge_get(url: str, timeout: int = 60, **kwargs: Any) -> Any:
    """GET an IBGE API URL and return the decoded JSON (responses are gzipped)."""
    # pylint: disable=import-outside-toplevel
    from openbb_core.provider.utils.helpers import amake_request

    async def response_callback(response, _):
        if "json" not in response.headers.get("Content-Type", ""):
            raise OpenBBError(
                f"IBGE API returned {response.status} with non-JSON content."
            )
        return await response.json()

    return await amake_request(
        url, timeout=timeout, response_callback=response_callback, **kwargs
    )
