"""Page registry: title, menu group and icon of every FinScope screen."""

from dataclasses import dataclass
from typing import Any

from dash import dcc, html

# Menu groups in display order
GRUPOS = [
    "Mercado",
    "Segmentos",
    "Produtos",
    "Boletim",
    "Bolsa",
    "Explorador",
    "Decisão",
]


@dataclass(frozen=True)
class Pagina:
    """One screen of the dashboard."""

    caminho: str
    titulo: str
    grupo: str | None  # None: reachable by URL but not in the menu
    icone: str
    modulo: Any  # module or object with layout() and register(app, client)


def icone(nome: str) -> html.Span:
    """Local SVG icon painted with the current text color (CSS mask)."""
    return html.Span(
        className="fs-icone",
        style={"--fs-icone": f"url(/assets/icones/{nome}.svg)"},
        **{"aria-hidden": "true"},
    )


def menu(paginas: list[Pagina], caminho: str) -> list[html.Div]:
    """Sidebar groups with links; the current page is marked."""
    blocos = []
    for grupo in GRUPOS:
        itens = [p for p in paginas if p.grupo == grupo]
        if not itens:
            continue
        blocos.append(
            html.Div(
                [
                    html.P(grupo, className="fs-grupo-titulo"),
                    *[
                        dcc.Link(
                            [
                                icone(p.icone),
                                html.Span(p.titulo, className="fs-item-texto"),
                            ],
                            href=p.caminho,
                            className="fs-item ativo"
                            if p.caminho == caminho
                            else "fs-item",
                            title=p.titulo,
                        )
                        for p in itens
                    ],
                ],
                className="fs-grupo",
            )
        )
    return blocos
