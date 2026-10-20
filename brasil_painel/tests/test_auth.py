"""Login, user store and access control."""

import json
import stat

import pytest

from brasil_painel.app import create_app
from brasil_painel.config import Settings
from brasil_painel.usuarios import UserStore


@pytest.fixture
def store(tmp_path):
    return UserStore(tmp_path / "usuarios.json")


@pytest.fixture
def client(store):
    store.add("ana", "senha-forte-123")
    settings = Settings(secret_key="teste", users_file=str(store.path))
    return create_app(settings).server.test_client()


def test_store_keeps_only_password_hashes(store):
    store.add("ana", "senha-forte-123")
    raw = store.path.read_text()
    assert "senha-forte-123" not in raw
    assert set(json.loads(raw)) == {"ana"}
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600


def test_store_verifies_password(store):
    store.add("ana", "senha-forte-123")
    assert store.verify("ana", "senha-forte-123")
    assert not store.verify("ana", "errada")
    assert not store.verify("bruno", "senha-forte-123")


def test_store_rejects_short_password_and_duplicates(store):
    with pytest.raises(ValueError):
        store.add("ana", "curta")
    store.add("ana", "senha-forte-123")
    with pytest.raises(ValueError):
        store.add("ana", "outra-senha-123")


def test_store_remove_and_list(store):
    store.add("ana", "senha-forte-123")
    store.add("bruno", "senha-forte-456")
    store.remove("ana")
    assert store.list() == ["bruno"]
    with pytest.raises(KeyError):
        store.remove("ana")


def test_anonymous_page_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_anonymous_dash_api_is_unauthorized(client):
    assert client.get("/_dash-layout").status_code == 401


def test_login_page_is_public_and_local(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "http://" not in html and "https://" not in html


def test_wrong_password_is_refused(client):
    response = client.post("/login", data={"usuario": "ana", "senha": "errada"})
    assert response.status_code == 401
    assert client.get("/").status_code == 302


def test_login_then_logout(client):
    response = client.post(
        "/login", data={"usuario": "ana", "senha": "senha-forte-123", "next": "/"}
    )
    assert response.status_code == 302
    assert client.get("/").status_code == 200
    assert client.get("/_dash-layout").status_code == 200
    client.get("/logout")
    assert client.get("/").status_code == 302


def test_login_ignores_external_next(client):
    response = client.post(
        "/login",
        data={"usuario": "ana", "senha": "senha-forte-123", "next": "//evil.example"},
    )
    assert response.headers["Location"] == "/"


def test_session_cookie_is_hardened(client):
    response = client.post(
        "/login", data={"usuario": "ana", "senha": "senha-forte-123"}
    )
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_cookie_is_secure_under_https(store):
    store.add("ana", "senha-forte-123")
    settings = Settings(secret_key="teste", users_file=str(store.path), https=True)
    client = create_app(settings).server.test_client()
    response = client.post(
        "/login", data={"usuario": "ana", "senha": "senha-forte-123"}
    )
    assert "Secure" in response.headers["Set-Cookie"]


def test_missing_secret_key_refuses_to_start(store):
    with pytest.raises(RuntimeError):
        create_app(Settings(users_file=str(store.path)))
