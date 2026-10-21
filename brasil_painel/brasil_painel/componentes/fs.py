"""FinScope building blocks, after the class-column models (funnel, bars, KPIs).

Numbers carry `data-valor`/`data-casas` so `assets/finscope.js` can count them
up once when they appear (skipped under reduced motion).
"""

import datetime as dt

from dash import html

from brasil_painel.dados import formato

SETAS = {"sobe": "▲", "desce": "▼", "estavel": "■"}


def _tendencia(variacao: float) -> str:
    if abs(variacao) < 1e-9:
        return "estavel"
    return "sobe" if variacao > 0 else "desce"


def kpi(
    rotulo: str,
    valor: float | None,
    *,
    unidade: str = "",
    casas: int = 1,
    variacao: float | None = None,
    comparacao: str = "",
    nota: str = "",
) -> html.Div:
    """Big number with its label, change and an optional note."""
    if valor is None:
        corpo = html.P("sem dado", className="fs-kpi-vazio")
    else:
        corpo = html.P(
            [
                html.Span(
                    formato.numero(valor, casas),
                    className="fs-numero",
                    **{"data-valor": valor, "data-casas": casas},
                ),
                html.Span(unidade, className="fs-unidade") if unidade else None,
            ],
            className="fs-kpi-valor",
        )
    filhos = [html.P(rotulo, className="fs-kpi-rotulo"), corpo]
    if variacao is not None:
        sentido = _tendencia(variacao)
        filhos.append(
            html.P(
                f"{SETAS[sentido]} {formato.numero(variacao, casas, sinal=True)} {comparacao}".strip(),
                className=f"fs-kpi-variacao {sentido}",
            )
        )
    if nota:
        filhos.append(html.P(nota, className="fs-kpi-nota"))
    return html.Div(filhos, className="fs-kpi")


def funil(etapas: list[tuple[str, float]], prefixo: str = "") -> html.Div:
    """Centered bars, each as a share of the first stage (as in the models)."""
    base = etapas[0][1] if etapas and etapas[0][1] else 1.0
    linhas = []
    for i, (rotulo, valor) in enumerate(etapas):
        parte = valor / base * 100
        texto = f"{prefixo}{formato.compacto(valor)}"
        if i:
            texto += f" ({formato.numero(parte, 1)}%)"
        linhas.append(
            html.Div(
                [
                    html.Span(rotulo, className="fs-funil-rotulo"),
                    html.Div(
                        html.Div(
                            html.Span(texto, className="fs-funil-texto"),
                            className="fs-funil-barra",
                            style={"width": f"{max(parte, 0):.1f}%"},
                        ),
                        className="fs-funil-trilho",
                    ),
                ],
                className="fs-funil-linha",
            )
        )
    return html.Div(linhas, className="fs-funil")


def barras_comparativas(
    itens: list[tuple[str, float, str]], prefixo: str = ""
) -> html.Div:
    """Horizontal bars (label, value, role) scaled to the largest value.

    Role picks the color: `coop`, `sistema`, `medio`, `claro`, `roxo`.
    Every bar shows its value, since three brand colors are below 3:1.
    """
    maior = max((abs(v) for _, v, _ in itens), default=0) or 1.0
    return html.Div(
        [
            html.Div(
                [
                    html.Span(rotulo, className="fs-barra-rotulo"),
                    html.Div(
                        html.Div(
                            className=f"fs-barra fs-cor-{papel}",
                            style={"width": f"{abs(valor) / maior * 100:.1f}%"},
                        ),
                        className="fs-barra-trilho",
                    ),
                    html.Span(
                        f"{prefixo}{formato.compacto(valor)}",
                        className="fs-barra-valor",
                    ),
                ],
                className="fs-barra-linha",
            )
            for rotulo, valor, papel in itens
        ],
        className="fs-barras",
    )


def coluna_classe(titulo: str, filhos: list, subtitulo: str = "") -> html.Section:
    """Framed column for one class, side by side with the others."""
    cabecalho = [html.H3(titulo, className="fs-coluna-titulo")]
    if subtitulo:
        cabecalho.append(html.P(subtitulo, className="fs-coluna-subtitulo"))
    return html.Section([html.Header(cabecalho), *filhos], className="fs-coluna")


def selo_datas(atualizacao: dt.date, data_base: dt.date) -> html.Div:
    """Update date and reference date, always visible."""
    return html.Div(
        [
            html.Span(f"Atualizado em {formato.data(atualizacao)}"),
            html.Span(f"Data-base: {formato.data(data_base, mensal=True)}"),
        ],
        className="fs-selo-datas",
    )


def esqueleto(linhas: int = 3) -> html.Div:
    """Show a loading placeholder shaped like the content."""
    return html.Div(
        [html.Div(className="fs-esqueleto-linha") for _ in range(linhas)],
        className="fs-esqueleto",
        **{"aria-busy": "true", "aria-label": "Carregando"},
    )
