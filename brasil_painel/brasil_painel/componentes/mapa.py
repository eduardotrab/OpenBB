"""Choropleth of the states, always read against the Brazil figure.

Sequential (one blue ramp) for magnitudes; diverging blue ↔ gray ↔ red,
centred on Brazil, for indicators where "above Brazil" is worse.
The world topojson Plotly insists on loading is served from our assets.
"""

import functools
import json

import plotly.graph_objects as go

from brasil_painel.componentes.graficos import TEXTO
from brasil_painel.dados import formato
from brasil_painel.regional import malha
from brasil_painel.regional.ufs import NOMES, SIGLAS

CODIGOS = {sigla: str(codigo) for codigo, sigla in SIGLAS.items()}
CONFIG_MAPA = {
    "displaylogo": False,
    "responsive": True,
    "topojsonURL": "/assets/topojson/",
}
SEQUENCIAL = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
DIVERGENTE = ["#184f95", "#6da7ec", "#f0efec", "#ef8a85", "#b3261e"]


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
) -> go.Figure:
    """Color each state by its value; hover shows Brazil and the difference."""
    siglas = list(valores)
    customdata = [
        [
            NOMES[s],
            f"{formato.numero(valores[s], casas)} {unidade}",
            (
                f"Brasil: {formato.numero(brasil, casas)} {unidade}"
                f" · diferença: {formato.numero(valores[s] - brasil, casas, sinal=True)}"
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
    fig.update_geos(
        visible=False,
        fitbounds="locations",
        projection_type="mercator",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, sans-serif", size=12, color=TEXTO),
        separators=",.",
    )
    return fig
