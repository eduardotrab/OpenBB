"""Plotly figures: Focus expectations and Tesouro Direto yield curves.

Colors follow the dataviz reference palette (categorical slots 1 and 2; a muted
gray for the comparison curve). One y-axis per panel; legend + hover always on.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from brasil_painel import marca
from brasil_painel.componentes import tema  # noqa: F401 - registers the template
from brasil_painel.dados import formato
from brasil_painel.dados.indicadores import Ponto
from brasil_painel.dados.mercado import Curvas, Serie

SERIE_1, SERIE_2, SERIE_3, SERIE_4 = marca.CATEGORICA[:4]
COMPARACAO = marca.BRASIL
TEXTO = marca.TEXTO
GRADE = marca.BORDA

UNIDADES_FOCUS = {"IPCA": "%", "Selic": "% a.a.", "PIB Total": "%", "Câmbio": "R$/US$"}


def _layout(fig: go.Figure, altura: int) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(l=48, r=16, t=72, b=32),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=0.99, yref="container", x=0.01),
        separators=",.",
    )
    fig.update_xaxes(showgrid=False, linecolor=GRADE, tickformat="%m/%Y")
    fig.update_yaxes(gridcolor=GRADE, zeroline=False)
    return fig


def figura_focus(series: dict[str, dict[int, Serie]]) -> go.Figure:
    """2×2 small multiples: median expectation for each reference year."""
    nomes = list(series)
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[f"{n} ({UNIDADES_FOCUS.get(n, '')})" for n in nomes],
        vertical_spacing=0.18,
        horizontal_spacing=0.08,
    )
    anos = sorted({ano for por_ano in series.values() for ano in por_ano})
    cores = dict(zip(anos, (SERIE_1, SERIE_2)))
    for i, nome in enumerate(nomes):
        linha, coluna = divmod(i, 2)
        for ano, pontos in series[nome].items():
            fig.add_trace(
                go.Scatter(
                    x=[d for d, _ in pontos],
                    y=[v for _, v in pontos],
                    name=str(ano),
                    legendgroup=str(ano),
                    showlegend=i == 0,
                    mode="lines",
                    line=dict(width=2, color=cores.get(ano, COMPARACAO)),
                    hovertemplate=f"{ano}: %{{y:.2f}}<extra></extra>",
                ),
                row=linha + 1,
                col=coluna + 1,
            )
    return _layout(fig, 520)


def figura_curva(curvas: Curvas) -> go.Figure:
    """Prefixado and IPCA+ curves side by side: today vs. ~30 days before."""
    tipos = [t for t in ("Prefixado", "IPCA+") if t in curvas.hoje]
    fig = make_subplots(
        rows=1,
        cols=len(tipos) or 1,
        horizontal_spacing=0.08,
        subplot_titles=[
            f"{t} (% a.a.{' + IPCA' if t == 'IPCA+' else ''})" for t in tipos
        ],
    )
    rotulos = [
        (curvas.anterior, curvas.data_anterior, COMPARACAO),
        (curvas.hoje, curvas.data, SERIE_1),
    ]
    for col, tipo in enumerate(tipos, start=1):
        for curva, data, cor in rotulos:
            if not data or tipo not in curva:
                continue
            nome = formato.data(data)
            fig.add_trace(
                go.Scatter(
                    x=[d for d, _ in curva[tipo]],
                    y=[v for _, v in curva[tipo]],
                    name=nome,
                    legendgroup=nome,
                    showlegend=col == 1,
                    mode="lines+markers",
                    line=dict(width=2, color=cor),
                    marker=dict(size=8, color=cor),
                    hovertemplate=f"{nome}: %{{y:.2f}}%<extra></extra>",
                ),
                row=1,
                col=col,
            )
    fig = _layout(fig, 360)
    fig.update_xaxes(tickformat="%Y")
    fig.update_layout(hovermode="closest")
    return fig


# Color follows the entity: Brazil is always slot 1, then US, euro area, China.
CORES_ENTIDADE = {
    "Selic meta": SERIE_1,
    "Brasil": SERIE_1,
    "Fed funds": SERIE_2,
    "EUA": SERIE_2,
    "BCE (depósito)": SERIE_3,
    "Zona do euro": SERIE_3,
    "China": SERIE_4,
    "Soja": SERIE_1,
    "Milho": SERIE_2,
    "Boi": SERIE_3,
    "Café arábica": SERIE_4,
}


ALTURA_LINHAS = 360
MARGEM_LINHAS = dict(l=48, r=130, t=48, b=32)
RECUO_ROTULO = 14  # px between end labels


def afastar(posicoes: list[float], minimo: float) -> list[float]:
    """Push sorted label positions apart so neighbours are at least `minimo` apart."""
    ordem = sorted(range(len(posicoes)), key=lambda i: posicoes[i])
    ajustadas = list(posicoes)
    for anterior, atual in zip(ordem, ordem[1:]):
        ajustadas[atual] = max(ajustadas[atual], ajustadas[anterior] + minimo)
    return ajustadas


def figura_linhas(
    series: dict[str, list[Ponto]],
    unidade: str,
    *,
    degrau: bool = False,
    base_100: bool = False,
    mensal: bool = False,
    cores: dict[str, str] | None = None,
    casas: int = 2,
    referencia: str | None = None,
) -> go.Figure:
    """Several series on one axis, each labelled at its last point."""
    fig = go.Figure()
    sufixo = unidade if unidade in ("%", "") else f" {unidade}"
    valores = [p.valor for pontos in series.values() for p in pontos]
    folga = (max(valores) - min(valores)) * 0.06 or 1
    y0, y1 = min(valores) - folga, max(valores) + folga
    altura_px = ALTURA_LINHAS - MARGEM_LINHAS["t"] - MARGEM_LINHAS["b"]
    finais = [pontos[-1] for pontos in series.values()]
    em_px = [(p.valor - y0) / (y1 - y0) * altura_px for p in finais]
    deslocamentos = [
        novo - velho for novo, velho in zip(afastar(em_px, RECUO_ROTULO), em_px)
    ]
    for (nome, pontos), deslocamento in zip(series.items(), deslocamentos):
        cor = (cores or {}).get(nome) or CORES_ENTIDADE.get(nome, COMPARACAO)
        fig.add_trace(
            go.Scatter(
                x=[p.data for p in pontos],
                y=[p.valor for p in pontos],
                name=nome,
                mode="lines",
                line=dict(
                    width=2,
                    color=marca.BRASIL if nome == referencia else cor,
                    dash="dash" if nome == referencia else "solid",
                    shape="hv" if degrau else "linear",
                ),
                hovertemplate=f"{nome}: %{{y:,.{casas}f}}{sufixo}<extra></extra>",
            )
        )
        ultimo = pontos[-1]
        fig.add_annotation(
            x=ultimo.data,
            y=ultimo.valor,
            text=f"{nome} {formato.numero(ultimo.valor, 1 if base_100 else casas)}",
            showarrow=False,
            xanchor="left",
            xshift=6,
            yshift=deslocamento,
            font=dict(size=11, color=TEXTO),
        )
    if base_100:
        fig.add_hline(y=100, line=dict(width=1, color=COMPARACAO, dash="dot"))
    datas = [p.data for pontos in series.values() for p in pontos]
    fig = _layout(fig, ALTURA_LINHAS)
    fig.update_layout(margin=MARGEM_LINHAS)
    fig.update_xaxes(
        range=[min(datas), max(datas)],
        hoverformat="%m/%Y" if mensal else "%d/%m/%Y",
    )
    fig.update_yaxes(range=[y0, y1], ticksuffix=sufixo)
    return fig


def figura_tendencia(
    pontos: list[tuple],
    rotulos: tuple[str, str] = ("Sistema", "Cooperativas"),
    unidade: str = "%",
) -> go.Figure:
    """Small two-line trend for a class column: system vs. cooperatives."""
    sufixo = unidade if unidade == "%" else f" {unidade}"
    fig = go.Figure()
    for i, (rotulo, cor) in enumerate(
        zip(rotulos, (marca.SISTEMA, marca.COOPERATIVAS)), start=1
    ):
        validos = [(p[0], p[i]) for p in pontos if p[i] is not None]
        fig.add_trace(
            go.Scatter(
                x=[d for d, _ in validos],
                y=[v for _, v in validos],
                name=rotulo,
                mode="lines",
                line=dict(width=2, color=cor),
                hovertemplate=f"{rotulo}: %{{y:,.2f}}{sufixo}<extra></extra>",
            )
        )
    fig.update_layout(
        height=170,
        margin=dict(l=36, r=8, t=30, b=24),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.0,
            yref="container",
            x=0,
            font=dict(size=11),
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, tickformat="%m/%y", nticks=4)
    fig.update_yaxes(ticksuffix=sufixo, nticks=4)
    return fig


CORES_GRUPO = {"Pessoas": marca.TURQUESA, "Empresas": marca.ROXO}


def figura_posicionamento(linhas) -> go.Figure:
    """Risk × growth of every class; bubble area = portfolio; Brazil as dashed lines."""
    brasil = next(item.resumo for item in linhas if item.grupo == "Brasil")
    classes_ = [
        item for item in linhas if item.grupo != "Brasil" and item.resumo.carteira
    ]
    maior = max((item.resumo.carteira for item in classes_), default=1)
    fig = go.Figure()
    for grupo, cor in CORES_GRUPO.items():
        itens = [item.resumo for item in classes_ if item.grupo == grupo]
        fig.add_trace(
            go.Scatter(
                x=[r.inadimplencia for r in itens],
                y=[r.crescimento_12m for r in itens],
                mode="markers+text",
                name=grupo,
                text=[r.classe for r in itens],
                textposition="top center",
                textfont=dict(size=11, color=marca.TEXTO),
                marker=dict(
                    size=[12 + 38 * (r.carteira / maior) ** 0.5 for r in itens],
                    color=cor,
                    opacity=0.85,
                    line=dict(color=marca.SUPERFICIE, width=2),
                ),
                customdata=[[formato.compacto(r.carteira)] for r in itens],
                hovertemplate="<b>%{text}</b><br>Inadimplência: %{x:.2f}%"
                "<br>Crescimento 12 meses: %{y:.1f}%<br>Carteira: R$ %{customdata[0]}<extra></extra>",
            )
        )
    if brasil.inadimplencia is not None:
        fig.add_vline(
            x=brasil.inadimplencia, line=dict(color=marca.BRASIL, dash="dash", width=1)
        )
    if brasil.crescimento_12m is not None:
        fig.add_hline(
            y=brasil.crescimento_12m,
            line=dict(color=marca.BRASIL, dash="dash", width=1),
        )
        fig.add_annotation(
            x=1, xref="paper", y=brasil.crescimento_12m, text="Brasil", showarrow=False,
            xanchor="right", yanchor="bottom", font=dict(size=11, color=marca.BRASIL),
        )  # fmt: skip
    for x, y, texto, ancora in (
        (0, 1, "cresce com risco menor", "left"),
        (1, 0, "cresce menos com risco maior", "right"),
    ):
        fig.add_annotation(
            x=x, y=y, xref="paper", yref="paper", text=texto, showarrow=False,
            xanchor=ancora, yanchor="top" if y else "bottom", font=dict(size=11, color=marca.TEXTO_SUAVE),
        )  # fmt: skip
    fig.update_layout(height=430, margin=dict(l=56, r=16, t=40, b=48), hovermode="closest",
                      legend=dict(orientation="h", yanchor="top", y=1.0, yref="container", x=0))  # fmt: skip
    fig.update_xaxes(title="Inadimplência (> 90 dias)", ticksuffix="%")
    fig.update_yaxes(title="Crescimento da carteira em 12 meses", ticksuffix="%")
    return fig
