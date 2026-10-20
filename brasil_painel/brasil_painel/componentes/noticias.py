"""News list with a filter by origin."""

import datetime as dt

from dash import dcc, html

from brasil_painel.dados.noticias import BRASILIA, FONTES, Noticia

ORIGENS = [origem for origem, _, _ in FONTES]


def para_store(noticias: list[Noticia]) -> list[dict]:
    """Serialise for dcc.Store."""
    return [
        {
            "titulo": x.titulo,
            "data": x.data.isoformat(),
            "url": x.url,
            "origem": x.origem,
        }
        for x in noticias
    ]


def filtro() -> dcc.Checklist:
    """Origin checkboxes (all selected)."""
    return dcc.Checklist(
        id="noticias-filtro",
        options=ORIGENS,
        value=ORIGENS,
        inline=True,
        className="filtro",
    )


def lista(dados: list[dict], origens: list[str], falhas: list[str]) -> html.Div:
    """Render the news of the selected origins, newest first."""
    itens = []
    for item in dados:
        if item["origem"] not in origens:
            continue
        quando = dt.datetime.fromisoformat(item["data"]).astimezone(BRASILIA)
        itens.append(
            html.Li(
                [
                    html.Span(quando.strftime("%d/%m %H:%M"), className="quando"),
                    html.Span(item["origem"], className="origem"),
                    html.A(
                        item["titulo"],
                        href=item["url"],
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                ]
            )
        )
    filhos = [
        html.Ul(itens, className="noticias") if itens else html.P("Nenhuma notícia.")
    ]
    if falhas:
        filhos.insert(
            0, html.P(f"Sem resposta agora: {', '.join(falhas)}.", className="aviso")
        )
    return html.Div(filhos)
