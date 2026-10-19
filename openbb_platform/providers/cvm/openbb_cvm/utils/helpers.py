"""Helpers for the CVM open data portal: text normalization, download and cache."""

import hashlib
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError

CVM_DATA_URL = "https://dados.cvm.gov.br/dados/"


def digits(value: str) -> str:
    """Keep only the digits of a CNPJ (or any code)."""
    return re.sub(r"\D", "", value)


def fold(text: str) -> str:
    """Lowercase and strip accents, for accent-insensitive search."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def cache_dir() -> Path:
    """Return the cache directory (``$OPENBB_CVM_CACHE_DIR`` or ``~/.cache/openbb_cvm``)."""
    return Path(
        os.environ.get("OPENBB_CVM_CACHE_DIR", Path.home() / ".cache" / "openbb_cvm")
    )


async def download(
    url: str, ttl_hours: float, use_cache: bool = True, **kwargs: Any
) -> bytes:
    """Download a CVM file, caching it on disk for ``ttl_hours``.

    Returns empty bytes for 404 (e.g. a month not yet published).
    """
    # pylint: disable=import-outside-toplevel
    from openbb_core.provider.utils.helpers import amake_request

    path = cache_dir() / f"{hashlib.sha256(url.encode()).hexdigest()}.bin"
    if (
        use_cache
        and path.exists()
        and time.time() - path.stat().st_mtime < ttl_hours * 3600
    ):
        return path.read_bytes()

    async def response_callback(response, _):
        if response.status == 404:
            return b""
        if response.status != 200:
            raise OpenBBError(f"CVM returned {response.status} for {url}.")
        return await response.read()

    content: bytes = await amake_request(  # type: ignore[assignment]
        url, timeout=180, response_callback=response_callback, **kwargs
    )
    if use_cache and content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return content
