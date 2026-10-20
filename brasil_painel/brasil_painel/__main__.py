"""Development server: `painel` or `python -m brasil_painel`."""

from brasil_painel.app import create_app
from brasil_painel.config import Settings


def main() -> None:
    """Run the Dash development server."""
    settings = Settings.from_env()
    create_app(settings).run(host=settings.host, port=settings.port, debug=False)


if __name__ == "__main__":
    main()
