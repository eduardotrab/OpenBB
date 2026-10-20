"""IBGE state mesh for the map, stored in the package (the map must open offline).

Regenerate with `python -m brasil_painel.regional.malha` (needs internet once).
"""

import json
import sys
from pathlib import Path

import requests

URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?intrarregiao=UF&formato=application/vnd.geo%2Bjson&qualidade=minima"
)
ARQUIVO = Path(__file__).resolve().parent.parent / "dados" / "malha_uf.json"


def _area(anel: list) -> float:
    """Twice the signed planar area (positive = counterclockwise)."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(anel, anel[1:]))


def _orientar(anel: list, horario: bool) -> list:
    anel = [[round(x, 4), round(y, 4)] for x, y in anel]
    return anel if (_area(anel) < 0) == horario else anel[::-1]


def rebobinar(geojson: dict) -> dict:
    """Exterior rings clockwise, holes counterclockwise (d3-geo / Plotly).

    The IBGE follows RFC 7946 (the opposite); unchanged, every state would
    fill the whole globe.
    """
    for feicao in geojson["features"]:
        geometria = feicao["geometry"]
        poligonos = (
            [geometria["coordinates"]]
            if geometria["type"] == "Polygon"
            else geometria["coordinates"]
        )
        orientados = [
            [_orientar(anel, i == 0) for i, anel in enumerate(p)] for p in poligonos
        ]
        geometria["coordinates"] = (
            orientados[0] if geometria["type"] == "Polygon" else orientados
        )
    return geojson


def gerar(destino: Path = ARQUIVO) -> Path:
    """Download the IBGE mesh, rewind it and save it compactly."""
    resposta = requests.get(URL, timeout=120)
    resposta.raise_for_status()
    destino.write_text(json.dumps(rebobinar(resposta.json()), separators=(",", ":")))
    return destino


if __name__ == "__main__":
    print(gerar())  # noqa: T201
    sys.exit(0)
