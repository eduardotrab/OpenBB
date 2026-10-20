"""The dashboard must open without any external resource."""

import re

from brasil_painel.app import create_app, pagina
from brasil_painel.config import Settings

URL_ATTR = re.compile(r'(?:src|href)="([^"]+)"')


def _client():
    """Client with authentication disabled (`users_file=None`) to test the page itself."""
    return create_app(Settings(users_file=None)).server.test_client()


def test_index_responds():
    response = _client().get("/")
    assert response.status_code == 200
    assert "Painel Brasil" in response.get_data(as_text=True)


def test_index_references_only_local_resources():
    html = _client().get("/").get_data(as_text=True)
    refs = URL_ATTR.findall(html)
    assert refs, "expected script/link references in the page"
    external = [r for r in refs if re.match(r"^(https?:)?//", r)]
    assert external == []


def test_every_referenced_asset_is_served():
    client = _client()
    html = client.get("/").get_data(as_text=True)
    for ref in URL_ATTR.findall(html):
        assert client.get(ref).status_code == 200, ref


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("PAINEL_PORT", "7000")
    monkeypatch.setenv("OPENBB_API_URL", "http://x:1/api/v1/")
    settings = Settings.from_env()
    assert (settings.port, settings.api_url) == (7000, "http://x:1/api/v1")


def _ids(componente) -> set[str]:
    """Every component id inside a layout tree."""
    ids = {getattr(componente, "id", None)}
    filhos = getattr(componente, "children", None)
    if not isinstance(filhos, list | tuple):
        filhos = [filhos]
    for filho in filhos:
        if filho is not None and not isinstance(filho, str):
            ids |= _ids(filho)
    return ids - {None}


def test_routing_picks_the_page_and_highlights_the_menu():
    corpo, links = pagina("/mundo/")
    assert "mundo-eua" in _ids(corpo)
    assert [link.className for link in links] == ["", "ativo"]
    corpo, links = pagina(None)
    assert "abertura-cartoes" in _ids(corpo)
    assert links[0].className == "ativo"


def test_unknown_path_shows_not_found():
    corpo, links = pagina("/nada")
    assert "não encontrada" in corpo.children
    assert all(link.className == "" for link in links)


def test_world_page_is_served():
    assert _client().get("/mundo").status_code == 200
