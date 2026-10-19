"""Small JSON disk cache for slow BCB endpoints."""

import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path


def cache_dir() -> Path:
    """Return the cache directory (``$OPENBB_BCB_CACHE_DIR`` or ``~/.cache/openbb_bcb``)."""
    return Path(
        os.environ.get("OPENBB_BCB_CACHE_DIR", Path.home() / ".cache" / "openbb_bcb")
    )


async def cached_rows(
    key: str,
    loader: Callable[[], Awaitable[list[dict]]],
    ttl_days: float = 7,
    use_cache: bool = True,
) -> list[dict]:
    """Return rows cached under ``key``, calling ``loader`` when missing or expired.

    Empty results are never cached.
    """
    if not use_cache:
        return await loader()
    path = cache_dir() / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
    if path.exists() and time.time() - path.stat().st_mtime < ttl_days * 86400:
        return json.loads(path.read_text(encoding="utf-8"))
    rows = await loader()
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows
