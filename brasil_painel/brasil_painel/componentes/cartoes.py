"""Indicator cards."""

from dash import html

from brasil_painel.dados import formato
from brasil_painel.dados.indicadores import Resumo

SETAS = {"sobe": "▲", "desce": "▼", "estavel": "■"}


def variacao(resumo: Resumo) -> str:
    """Change as '+0,25' in the card's unit, or '+2,0%' when percentual."""
    if resumo.percentual:
        return formato.numero(resumo.variacao, 1, sinal=True) + "%"
    return formato.numero(resumo.variacao, resumo.casas, sinal=True)


def cartao(resumo: Resumo) -> html.Div:
    """One card: value, unit, reference date, change and trend arrow."""
    if resumo.erro or resumo.valor is None:
        return html.Div(
            [
                html.H3(resumo.nome),
                html.P("Fonte indisponível", className="valor"),
                html.P(resumo.fonte, className="rodape"),
            ],
            className="cartao cartao-erro",
            title=resumo.erro or "",
        )
    filhos = [
        html.H3(resumo.nome),
        html.P(
            [
                formato.numero(resumo.valor, resumo.casas),
                html.Span(f" {resumo.unidade}", className="unidade"),
            ],
            className="valor",
        ),
    ]
    if resumo.tendencia:
        filhos.append(
            html.P(
                f"{SETAS[resumo.tendencia]} {variacao(resumo)} {resumo.comparacao}",
                className=f"variacao {resumo.tendencia}",
            )
        )
    rodape = f"{resumo.fonte} · ref. {formato.data(resumo.data_ref, resumo.mensal)}"
    filhos.append(html.P(rodape, className="rodape"))
    if resumo.defasado:
        filhos.append(html.P("desatualizado", className="selo-defasado"))
    return html.Div(
        filhos, className="cartao" + (" cartao-defasado" if resumo.defasado else "")
    )


def cartoes(resumos: list[Resumo]) -> html.Div:
    """Row of cards."""
    return html.Div([cartao(r) for r in resumos], className="cartoes")
