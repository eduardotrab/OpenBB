"""Page building blocks shared by every page."""

from dash import dcc, html

from brasil_painel import marca

CONFIG_GRAFICO = {"displaylogo": False, "responsive": True}


def secao(titulo: str, id_: str, nota: str = "") -> html.Section:
    """Build a titled block whose body is filled by a callback."""
    return html.Section(
        [
            html.H2(titulo),
            html.P(nota, className="nota") if nota else None,
            carregando(html.Div(id=id_)),
        ],
        className="secao",
    )


def aviso(texto: str) -> html.P:
    """Message shown when a source fails."""
    return html.P(f"Fonte indisponível no momento: {texto}", className="aviso")


def grafico(figura) -> dcc.Graph:
    """Wrap a Plotly figure with the shared toolbar config."""
    return dcc.Graph(figure=figura, config=CONFIG_GRAFICO)


def carregando(filho) -> dcc.Loading:
    """Wrap a callback target with a loading indicator in the brand color."""
    return dcc.Loading(filho, type="dot", color=marca.TURQUESA)
