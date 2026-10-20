"""Development server: `painel` or `python -m brasil_painel`."""

import dataclasses
import secrets

from brasil_painel.app import create_app
from brasil_painel.config import Settings


def main() -> None:
    """Run the Dash development server (production uses gunicorn)."""
    settings = Settings.from_env()
    if not settings.secret_key:
        # Development only: sessions are lost when the process restarts.
        settings = dataclasses.replace(settings, secret_key=secrets.token_hex(32))
    create_app(settings).run(host=settings.host, port=settings.port, debug=False)


if __name__ == "__main__":
    main()
