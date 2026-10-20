"""gunicorn settings from the environment: `gunicorn -c python:brasil_painel.gunicorn_conf`.

HTTPS is enabled when PAINEL_CERTFILE and PAINEL_KEYFILE are set.
"""

import os

wsgi_app = "brasil_painel.wsgi:server"
bind = f"{os.environ.get('PAINEL_HOST', '127.0.0.1')}:{os.environ.get('PAINEL_PORT', '6902')}"
workers = int(os.environ.get("PAINEL_WORKERS", "2"))
threads = int(os.environ.get("PAINEL_THREADS", "4"))
timeout = 120
accesslog = "-"

certfile = os.environ.get("PAINEL_CERTFILE") or None
keyfile = os.environ.get("PAINEL_KEYFILE") or None
