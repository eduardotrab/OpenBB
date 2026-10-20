"""Login for the Flask server behind Dash (flask-login)."""

from html import escape
from urllib.parse import urlparse

from flask import Flask, Response, redirect, request
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user

from brasil_painel.usuarios import UserStore

PUBLIC_PATHS = {"/login", "/assets/estilo.css", "/_favicon.ico"}

LOGIN_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrar — Painel Brasil</title>
<link rel="stylesheet" href="/assets/estilo.css"></head>
<body><header class="topo"><h1>Painel Brasil</h1></header>
<main class="conteudo login">
<form method="post" action="/login">
<h2>Entrar</h2>{erro}
<label>Usuário <input name="usuario" autocomplete="username" required autofocus></label>
<label>Senha <input name="senha" type="password" autocomplete="current-password" required></label>
<input type="hidden" name="next" value="{next}">
<button type="submit">Entrar</button>
</form></main></body></html>"""


class User(UserMixin):
    """Logged-in user (only the username is kept in the session)."""

    def __init__(self, username: str):
        self.id = username


def _safe_next(target: str | None) -> str:
    """Accept only local paths, to avoid open redirects."""
    if not target:
        return "/"
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def _login_page(next_url: str, erro: str = "", status: int = 200) -> Response:
    erro_html = f'<p class="erro">{escape(erro)}</p>' if erro else ""
    body = LOGIN_PAGE.format(erro=erro_html, next=escape(next_url))
    return Response(body, status=status, mimetype="text/html")


def setup_auth(
    server: Flask, store: UserStore, secret_key: str, https: bool = False
) -> None:
    """Protect every route except the login page and its stylesheet."""
    server.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=https,
        REMEMBER_COOKIE_SECURE=https,
    )
    manager = LoginManager(server)

    @manager.user_loader
    def load_user(username: str) -> User | None:
        return User(username) if store.exists(username) else None

    @server.before_request
    def require_login():
        if current_user.is_authenticated or request.path in PUBLIC_PATHS:
            return None
        if request.path.startswith("/_dash") or request.method != "GET":
            return Response("Não autenticado.", status=401)
        return redirect(f"/login?next={request.full_path.rstrip('?')}")

    @server.route("/login", methods=["GET", "POST"])
    def login():
        next_url = _safe_next(request.values.get("next"))
        if request.method == "GET":
            return _login_page(next_url)
        username = request.form.get("usuario", "").strip()
        if store.verify(username, request.form.get("senha", "")):
            login_user(User(username))
            return redirect(next_url)
        return _login_page(next_url, "Usuário ou senha inválidos.", status=401)

    @server.route("/logout")
    def logout():
        logout_user()
        return redirect("/login")
