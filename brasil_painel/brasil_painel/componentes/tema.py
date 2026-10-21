"""Plotly template `finscope`, registered as the default for every figure."""

import plotly.graph_objects as go
import plotly.io as pio

from brasil_painel import marca

TRANSICAO = {"duration": 400, "easing": "cubic-in-out"}

_eixo = dict(
    gridcolor=marca.BORDA,
    linecolor=marca.BORDA,
    zeroline=False,
    tickfont=dict(color=marca.TEXTO_SUAVE),
    title=dict(font=dict(color=marca.TEXTO_SUAVE)),
)

pio.templates["finscope"] = go.layout.Template(
    layout=dict(
        font=dict(family=marca.FONTE, size=12, color=marca.TEXTO),
        colorway=marca.CATEGORICA,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=marca.SUPERFICIE,
        separators=",.",
        hoverlabel=dict(
            font=dict(family=marca.FONTE, color=marca.TEXTO),
            bgcolor=marca.SUPERFICIE,
            bordercolor=marca.BORDA,
        ),
        legend=dict(orientation="h", font=dict(color=marca.TEXTO_SUAVE)),
        xaxis=_eixo,
        yaxis=_eixo,
        transition=TRANSICAO,
        colorscale=dict(sequential=marca.SEQUENCIAL, diverging=marca.DIVERGENTE),
    )
)
pio.templates.default = "finscope"
