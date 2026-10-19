"""Small text disk cache for large Tesouro Transparente files."""

import hashlib
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path


def cache_dir() -> Path:
    """Return the cache directory (``$OPENBB_TESOURO_CACHE_DIR`` or ``~/.cache/openbb_tesouro``)."""
    return Path(
        os.environ.get(
            "OPENBB_TESOURO_CACHE_DIR", Path.home() / ".cache" / "openbb_tesouro"
        )
    )


async def cached_text(
    key: str,
    loader: Callable[[], Awaitable[str]],
    ttl_hours: float = 12,
    use_cache: bool = True,
) -> str:
    """Return text cached under ``key``, calling ``loader`` when missing or expired."""
    if not use_cache:
        return await loader()
    path = cache_dir() / f"{hashlib.sha256(key.encode()).hexdigest()}.txt"
    if path.exists() and time.time() - path.stat().st_mtime < ttl_hours * 3600:
        return path.read_text(encoding="utf-8")
    text = await loader()
    if text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text
