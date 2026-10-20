"""Settings read from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_USERS_FILE = "~/.config/openbb-painel/usuarios.json"


@dataclass(frozen=True)
class Settings:
    """Runtime settings of the dashboard.

    `users_file=None` disables login; only tests do that.
    """

    host: str = "127.0.0.1"
    port: int = 6902
    api_url: str = "http://127.0.0.1:6900/api/v1"
    secret_key: str | None = None
    users_file: str | None = DEFAULT_USERS_FILE
    https: bool = False
    aquecer: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from `PAINEL_*` / `OPENBB_API_URL` variables."""
        return cls(
            host=os.environ.get("PAINEL_HOST", cls.host),
            port=int(os.environ.get("PAINEL_PORT", cls.port)),
            api_url=os.environ.get("OPENBB_API_URL", cls.api_url).rstrip("/"),
            secret_key=os.environ.get("PAINEL_SECRET_KEY") or None,
            users_file=os.environ.get("PAINEL_USERS_FILE", DEFAULT_USERS_FILE),
            https=bool(os.environ.get("PAINEL_CERTFILE")),
            aquecer=os.environ.get("PAINEL_AQUECER", "1") == "1",
        )
