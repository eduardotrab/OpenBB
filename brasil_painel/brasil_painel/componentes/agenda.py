"""Release calendar for the next days."""

import datetime as dt

from dash import html

from brasil_painel.dados.agenda import Evento

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def agenda(
    eventos: list[Evento], falhas: list[str], hoje: dt.date | None = None
) -> html.Div:
    """Events grouped by day; today is highlighted."""
    hoje = hoje or dt.date.today()
    itens = []
    for evento in eventos:
        dia = (
            "hoje"
            if evento.data == hoje
            else f"{DIAS[evento.data.weekday()]} {evento.data:%d/%m}"
        )
        itens.append(
            html.Li(
                [
                    html.Span(
                        dia, className="dia" + (" hoje" if evento.data == hoje else "")
                    ),
                    html.Span(evento.titulo, className="evento"),
                    html.Span(
                        " · ".join(x for x in (evento.hora, evento.fonte) if x),
                        className="detalhe",
                    ),
                ]
            )
        )
    filhos = [html.Ul(itens, className="agenda") if itens else html.P("Nada previsto.")]
    if falhas:
        filhos.insert(
            0, html.P(f"Sem resposta agora: {', '.join(falhas)}.", className="aviso")
        )
    return html.Div(filhos)
