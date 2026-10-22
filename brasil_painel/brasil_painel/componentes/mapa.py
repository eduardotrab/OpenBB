"""Choropleth of the states, always read against the Brazil figure.

Sequential (one blue ramp) for magnitudes; diverging blue ↔ gray ↔ red,
centred on Brazil, for indicators where "above Brazil" is worse.
The world topojson Plotly insists on loading is served from our assets.
"""

import functools
import json

import plotly.graph_objects as go

from brasil_painel import marca
from brasil_painel.dados import formato
from brasil_painel.regional import malha
from brasil_painel.regional.ufs import NOMES, SIGLAS

CODIGOS = {sigla: str(codigo) for codigo, sigla in SIGLAS.items()}
CONFIG_MAPA = {
    "displaylogo": False,
    "responsive": True,
    "topojsonURL": "/assets/topojson/",
}
SEQUENCIAL = marca.SEQUENCIAL
DIVERGENTE = marca.DIVERGENTE


@functools.cache
def geojson() -> dict:
    """State mesh shipped with the package."""
    return json.loads(malha.ARQUIVO.read_text())


def figura_mapa(
    valores: dict[str, float],
    brasil: float | None,
    unidade: str,
    *,
    casas: int = 2,
    divergente: bool = False,
    destaque: str | None = None,
    altura: int = 520,
) -> go.Figure:
    """Color each state by its value; hover shows Brazil and the difference."""
    siglas = list(valores)
    customdata = [
        [
            NOMES[s],
            f"{formato.numero(valores[s], casas)} {unidade}",
            (
                f"Brasil: {formato.numero(brasil, casas)} {unidade}"
                f"<br>Diferença: {formato.numero(valores[s] - brasil, casas, sinal=True)}"
                if brasil is not None
                else ""
            ),
        ]
        for s in siglas
    ]
    fig = go.Figure(
        go.Choropleth(
            geojson=geojson(),
            featureidkey="properties.codarea",
            locations=[CODIGOS[s] for s in siglas],
            z=[valores[s] for s in siglas],
            zmid=brasil if divergente else None,
            colorscale=DIVERGENTE if divergente else SEQUENCIAL,
            marker=dict(line=dict(color="#ffffff", width=0.6)),
            customdata=customdata,
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}"
            "<br>%{customdata[2]}<extra></extra>",
            colorbar=dict(title=dict(text=unidade), thickness=12, len=0.7),
        )
    )
    if destaque in valores:
        # outline of the selected state, drawn on top without changing its color
        fig.add_trace(
            go.Choropleth(
                geojson=geojson(),
                featureidkey="properties.codarea",
                locations=[CODIGOS[destaque]],
                z=[0],
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                marker=dict(line=dict(color=marca.VERDE_ESCURO, width=3)),
                hoverinfo="skip",
            )
        )
    fig.update_geos(
        visible=False,
        fitbounds="locations",
        projection_type="mercator",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


@functools.cache
def geojson_municipios(uf: str) -> dict:
    """Municipal mesh of one state, shipped with the package."""
    return json.loads((malha.PASTA_MUNICIPIOS / f"{uf}.json").read_text())


def figura_mapa_municipios(
    uf: str,
    valores: dict[str, float],
    nomes: dict[str, str],
    referencia: float | None,
    unidade: str,
    *,
    casas: int = 1,
    crescimento: bool = False,
    destaque: str | None = None,
    altura: int = 560,
) -> go.Figure:
    """Municipalities of one state colored by value; those without data in light gray.

    Magnitudes use the sequential ramp clipped at the 5th and 95th percentiles
    (a capital would wash out the rest); growth uses the diverging ramp
    centred on the state median, green above it.
    """
    geo = geojson_municipios(uf)
    todos = [f["properties"]["codarea"] for f in geo["features"]]
    com_dado = [c for c in todos if c in valores]
    numeros = sorted(valores[c] for c in com_dado)
    fig = go.Figure(
        go.Choropleth(
            geojson=geo, featureidkey="properties.codarea", locations=todos, z=[0] * len(todos),
            colorscale=[[0, "#E3E9EA"], [1, "#E3E9EA"]], showscale=False,
            marker=dict(line=dict(color="#ffffff", width=0.3)),
            customdata=[[nomes.get(c, c)] for c in todos],
            hovertemplate="<b>%{customdata[0]}</b><br>sem dado<extra></extra>",
        )
    )  # fmt: skip
    if com_dado:
        baixo = numeros[int(len(numeros) * 0.05)]
        alto = numeros[min(len(numeros) - 1, int(len(numeros) * 0.95))]
        if crescimento and referencia is not None:
            folga = max(abs(alto - referencia), abs(referencia - baixo)) or 1
            baixo, alto = referencia - folga, referencia + folga
        customdata = [
            [
                nomes.get(c, c),
                f"{formato.numero(valores[c], casas)} {unidade}",
                f"Mediana do estado: {formato.numero(referencia, casas)} {unidade}"
                if referencia is not None
                else "",
            ]
            for c in com_dado
        ]
        fig.add_trace(
            go.Choropleth(
                geojson=geo, featureidkey="properties.codarea", locations=com_dado,
                z=[valores[c] for c in com_dado], zmin=baixo, zmax=alto,
                colorscale=DIVERGENTE[::-1] if crescimento else SEQUENCIAL,
                marker=dict(line=dict(color="#ffffff", width=0.3)), customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
                colorbar=dict(title=dict(text=unidade), thickness=12, len=0.7, tickformat=f",.{casas}f"),
            )
        )  # fmt: skip
    if destaque in todos:
        fig.add_trace(
            go.Choropleth(
                geojson=geo, featureidkey="properties.codarea", locations=[destaque], z=[0],
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                marker=dict(line=dict(color=marca.VERDE_ESCURO, width=2.5)), hoverinfo="skip",
            )
        )  # fmt: skip
    fig.update_geos(
        visible=False,
        fitbounds="locations",
        projection_type="mercator",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        separators=",.",
    )
    return fig
