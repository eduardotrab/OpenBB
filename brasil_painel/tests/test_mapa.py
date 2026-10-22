"""State mesh orientation and the choropleth figure."""

import json

from brasil_painel.componentes import mapa
from brasil_painel.regional import malha


def _quadrado(sentido_horario: bool) -> list:
    anel = [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]  # clockwise (x right, y up)
    return anel if sentido_horario else anel[::-1]


def test_rewind_makes_exterior_rings_clockwise():
    geo = {
        "features": [
            {"geometry": {"type": "Polygon", "coordinates": [_quadrado(False)]}},
            {"geometry": {"type": "MultiPolygon", "coordinates": [[_quadrado(False)]]}},
        ]
    }
    malha.rebobinar(geo)
    assert malha._area(geo["features"][0]["geometry"]["coordinates"][0]) < 0
    assert malha._area(geo["features"][1]["geometry"]["coordinates"][0][0]) < 0


def test_stored_mesh_has_27_clockwise_states():
    geo = json.loads(malha.ARQUIVO.read_text())
    assert len(geo["features"]) == 27
    for feicao in geo["features"]:
        g = feicao["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        assert all(malha._area(p[0]) < 0 for p in poligonos), feicao["properties"]


def test_map_figure_colors_states_and_centres_on_brazil():
    fig = mapa.figura_mapa(
        {"MG": 3.8, "SP": 5.9}, brasil=5.4, unidade="%", divergente=True
    )
    trace = fig.data[0]
    assert list(trace.locations) == ["31", "35"]
    assert trace.zmid == 5.4
    assert "Minas Gerais" in trace.customdata[0][0]
    assert "-1,60" in trace.customdata[0][2]
    texto = fig.to_json()
    assert "http://" not in texto and "https://" not in texto


def test_map_figure_sequential_has_no_midpoint():
    fig = mapa.figura_mapa({"MG": 10.0}, brasil=None, unidade="R$")
    assert fig.data[0].zmid is None


def test_map_graph_loads_topojson_locally():
    assert mapa.CONFIG_MAPA["topojsonURL"] == "/assets/topojson/"


def test_municipal_meshes_cover_the_ibge_list_and_are_clockwise():
    nomes = json.loads(malha.LISTA.read_text())
    codigos = set()
    for arquivo in malha.PASTA_MUNICIPIOS.glob("*.json"):
        for feicao in json.loads(arquivo.read_text())["features"]:
            codigos.add(feicao["properties"]["codarea"])
            g = feicao["geometry"]
            poligonos = (
                [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            )
            assert all(malha._area(p[0]) < 0 for p in poligonos), feicao["properties"]
    # recently installed municipalities reach the list before the mesh
    # (5101837, Boa Esperança do Norte, MT, in 2026)
    assert (
        len(nomes) > 5500 and codigos <= set(nomes) and len(set(nomes) - codigos) <= 3
    )
    assert nomes["3106200"] == ["Belo Horizonte", "MG"]


def test_municipal_map_grays_missing_and_centres_growth_on_the_median():
    fig = mapa.figura_mapa_municipios(
        "AC",
        {"1200401": 10.0, "1200013": -4.0},
        {"1200401": "Rio Branco"},
        2.0,
        "%",
        crescimento=True,
        destaque="1200401",
    )
    fundo, dados, contorno = fig.data
    assert len(fundo.locations) == 22 and list(dados.locations) == [
        "1200013",
        "1200401",
    ]
    assert dados.zmin + dados.zmax == 4.0  # symmetric around the median
    assert list(contorno.locations) == ["1200401"]
