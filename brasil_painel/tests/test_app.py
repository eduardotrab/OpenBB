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
    assert "FinScope" in response.get_data(as_text=True)


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


def _links(grupos):
    return [item for g in grupos for item in g.children[1:]]


def test_routing_picks_the_page_and_highlights_the_menu():
    corpo, grupos, titulo = pagina("/mundo/")
    assert "mundo-eua" in _ids(corpo)
    assert titulo == "Mundo"
    mercado = grupos[0].children[1:]
    assert [link.className for link in mercado] == [
        "fs-item",
        "fs-item ativo",
        "fs-item",
    ]
    corpo, grupos, titulo = pagina(None)
    assert "abertura-cartoes" in _ids(corpo)
    assert _links(grupos)[0].className == "fs-item ativo"
    assert grupos[0].children[0].children == "Mercado"


def test_unknown_path_shows_not_found():
    corpo, grupos, titulo = pagina("/nada")
    assert "não existe" in corpo.children
    assert all(link.className == "fs-item" for link in _links(grupos))


def test_world_page_is_served():
    assert _client().get("/mundo").status_code == 200


def test_routing_callback_runs_through_dash():
    payload = {
        "output": "..pagina.children...menu.children...titulo-pagina.children..",
        "outputs": [
            {"id": "pagina", "property": "children"},
            {"id": "menu", "property": "children"},
            {"id": "titulo-pagina", "property": "children"},
        ],
        "inputs": [{"id": "url", "property": "pathname", "value": "/mundo"}],
        "changedPropIds": ["url.pathname"],
    }
    response = _client().post("/_dash-update-component", json=payload)
    assert response.status_code == 200
    assert "mundo-eua" in response.get_data(as_text=True)


def test_warm_up_touches_slow_sources_and_survives_failures():
    from brasil_painel.app import aquecer
    from brasil_painel.dados.api import FonteIndisponivel

    class Falha:
        def __init__(self):
            self.rotas = set()

        def get(self, path, **params):
            self.rotas.add(path)
            raise FonteIndisponivel(path)

    client = Falha()
    aquecer(client).join(timeout=5)
    assert {
        "tesouro/direto",
        "economy/cpi",
        "economy/indicators",
    } <= client.rotas


def test_map_page_is_served_and_routed():
    assert _client().get("/mapa").status_code == 200
    corpo, _, _ = pagina("/mapa")
    assert {"mapa-grafico", "mapa-ranking", "mapa-painel", "mapa-classe"} <= _ids(corpo)


def test_gallery_is_routed_but_hidden_from_the_menu():
    corpo, grupos, _ = pagina("/estilo")
    assert "fs-galeria" in corpo.className
    assert all(link.href != "/estilo" for link in _links(grupos))


def test_every_menu_icon_exists():
    from pathlib import Path

    import brasil_painel
    from brasil_painel.app import PAGINAS

    pasta = Path(brasil_painel.__file__).parent / "assets" / "icones"
    assert all((pasta / f"{p.icone}.svg").exists() for p in PAGINAS)


def test_motion_script_is_local_and_respects_reduced_motion():
    from pathlib import Path

    import brasil_painel

    js = (Path(brasil_painel.__file__).parent / "assets" / "finscope.js").read_text()
    assert "prefers-reduced-motion" in js
    assert "http" not in js


def test_global_filters_reach_the_store(monkeypatch, tmp_path):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    payload = {
        "output": "..filtros.data...selo-topo.children..",
        "outputs": [
            {"id": "filtros", "property": "data"},
            {"id": "selo-topo", "property": "children"},
        ],
        "inputs": [
            {"id": "filtro-uf", "property": "value", "value": "MG"},
            {"id": "filtro-data", "property": "value", "value": "2026-08-31"},
        ],
        "changedPropIds": ["filtro-uf.value"],
    }
    resposta = _client().post("/_dash-update-component", json=payload)
    assert resposta.get_json()["response"]["filtros"]["data"] == {
        "uf": "MG",
        "data": "2026-08-31",
    }
    assert "ago/2026" in str(resposta.get_json()["response"]["selo-topo"])


def test_uf_options_start_with_brazil():
    from brasil_painel.componentes import filtros

    opcoes = filtros.opcoes_uf()
    assert opcoes[0] == {"label": "Brasil", "value": "BR"}
    assert len(opcoes) == 28


def test_every_screen_of_the_roadmap_so_far_is_routed():
    from brasil_painel.app import POR_CAMINHO

    for caminho in (
        "/",
        "/mundo",
        "/mapa",
        "/pessoas",
        "/empresas",
        "/rural",
        "/comparativo",
        "/produtos",
    ):
        assert caminho in POR_CAMINHO, caminho
