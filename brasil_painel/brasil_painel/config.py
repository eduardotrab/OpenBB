"""Settings read from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings of the dashboard."""

    host: str = "127.0.0.1"
    port: int = 6902
    api_url: str = "http://127.0.0.1:6900/api/v1"

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from `PAINEL_*` / `OPENBB_API_URL` variables."""
        return cls(
            host=os.environ.get("PAINEL_HOST", cls.host),
            port=int(os.environ.get("PAINEL_PORT", cls.port)),
            api_url=os.environ.get("OPENBB_API_URL", cls.api_url).rstrip("/"),
        )
