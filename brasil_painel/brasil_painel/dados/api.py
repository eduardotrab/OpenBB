"""Client of the local OpenBB API with a small in-memory TTL cache."""

import json
import threading
import time
from typing import Any

import requests


class FonteIndisponivel(Exception):
    """The API (or the source behind it) did not return usable data."""


class OpenBBClient:
    """GET `<base_url>/<path>` and return the `results` list."""

    def __init__(self, base_url: str, ttl_segundos: float = 600, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.ttl = ttl_segundos
        self.timeout = timeout
        self._session = requests.Session()
        self._cache: dict[tuple, tuple[float, list]] = {}
        self._lock = threading.Lock()

    def get(self, path: str, **params: Any) -> list[dict]:
        """Return the results of a route; raises FonteIndisponivel on failure."""
        key = (path, tuple(sorted(params.items())))
        with self._lock:
            hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            # Some feeds carry control characters inside strings.
            body = json.loads(response.text, strict=False)
        except (requests.RequestException, ValueError) as error:
            raise FonteIndisponivel(f"{path}: {error}") from error
        results = body.get("results") if isinstance(body, dict) else None
        if not results:
            raise FonteIndisponivel(f"{path}: sem dados")
        with self._lock:
            self._cache[key] = (time.monotonic(), results)
        return results
