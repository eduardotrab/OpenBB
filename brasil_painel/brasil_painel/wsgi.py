"""WSGI entry point for gunicorn: `gunicorn brasil_painel.wsgi:server`."""

from brasil_painel.app import create_app

app = create_app()
server = app.server
