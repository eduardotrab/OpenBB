"""Data of the opening screen, fetched from the local OpenBB API."""

import datetime as dt
from collections.abc import Callable

from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.dados.indicadores import Ponto, Resumo, data_de_periodo, resumir
from brasil_painel.dados.mercado import Curvas, curvas_tesouro, series_focus


def serie_sgs(client: OpenBBClient, codigo: int, desde: dt.date) -> list[Ponto]:
    """BCB SGS series from `desde`."""
    rows = client.get("bcb/sgs", symbol=str(codigo), start_date=desde.isoformat())
    return [
        Ponto(dt.date.fromisoformat(r["date"]), r["value"])
        for r in rows
        if r["value"] is not None
    ]


def serie_ibge(
    client: OpenBBClient, tabela: int, variavel: int, periodos: int
) -> list[Ponto]:
    """Last `periodos` of an IBGE SIDRA table variable."""
    rows = client.get(
        "ibge/aggregates",
        table=str(tabela),
        variables=str(variavel),
        periods=f"-{periodos}",
    )
    return [
        Ponto(data_de_periodo(r["period"]), r["value"])
        for r in rows
        if r["value"] is not None
    ]


def _ptax(client: OpenBBClient, desde: dt.date) -> list[Ponto]:
    rows = client.get(
        "currency/price/historical",
        symbol="USDBRL",
        provider="bcb",
        start_date=desde.isoformat(),
    )
    return [Ponto(dt.date.fromisoformat(r["date"][:10]), r["close"]) for r in rows]


Spec = tuple[str, Callable[[], list[Ponto]], dict]


def montar_cartoes(specs: list[Spec], hoje: dt.date) -> list[Resumo]:
    """Load and summarise each (name, loader, options); a failing source becomes an error card."""
    resumos = []
    for nome, carregar, opcoes in specs:
        try:
            pontos = carregar()
        except FonteIndisponivel as error:
            resumos.append(
                Resumo(nome, opcoes["unidade"], opcoes["fonte"], erro=str(error))
            )
            continue
        resumos.append(resumir(nome, pontos, hoje=hoje, **opcoes))
    return resumos


def indicadores(client: OpenBBClient, hoje: dt.date | None = None) -> list[Resumo]:
    """Cards of the opening screen; a failing source becomes an error card."""
    hoje = hoje or dt.date.today()
    ano_atras = hoje - dt.timedelta(days=400)
    specs: list[Spec] = [
        (
            "Dólar (PTAX venda)",
            lambda: _ptax(client, hoje - dt.timedelta(days=45)),
            dict(
                unidade="R$",
                fonte="BCB",
                dias=30,
                max_dias=4,
                comparacao="em 30 dias",
                casas=4,
            ),
        ),
        (
            "Selic meta",
            lambda: serie_sgs(client, 432, ano_atras),
            dict(
                unidade="% a.a.",
                fonte="BCB",
                dias=365,
                max_dias=4,
                comparacao="em 12 meses",
            ),
        ),
        (
            "CDI",
            lambda: serie_sgs(client, 4389, ano_atras),
            dict(
                unidade="% a.a.",
                fonte="BCB",
                dias=365,
                max_dias=6,
                comparacao="em 12 meses",
            ),
        ),
        (
            "IPCA 12 meses",
            lambda: serie_ibge(client, 1737, 2265, 13),
            dict(
                unidade="%",
                fonte="IBGE",
                passos=1,
                max_dias=75,
                comparacao="vs. mês anterior",
                mensal=True,
            ),
        ),
        (
            "Desemprego",
            lambda: serie_ibge(client, 6381, 4099, 13),
            dict(
                unidade="%",
                fonte="IBGE (PNAD)",
                passos=12,
                max_dias=130,
                comparacao="vs. 12 meses antes",
                mensal=True,
            ),
        ),
    ]
    return montar_cartoes(specs, hoje)


FOCUS_INDICADORES = ("IPCA", "Selic", "PIB Total", "Câmbio")


def focus(client: OpenBBClient, hoje: dt.date | None = None, dias: int = 180) -> dict:
    """Focus medians for the current and next year, per indicator."""
    hoje = hoje or dt.date.today()
    desde = (hoje - dt.timedelta(days=dias)).isoformat()
    anos = [hoje.year, hoje.year + 1]
    return {
        nome: series_focus(
            client.get("bcb/focus", indicator=nome, start_date=desde), anos
        )
        for nome in FOCUS_INDICADORES
    }


def tesouro(
    client: OpenBBClient, hoje: dt.date | None = None, dias: int = 45
) -> Curvas:
    """Tesouro Direto curves (the first call can take ~90 s; see warm-up)."""
    hoje = hoje or dt.date.today()
    rows = client.get(
        "tesouro/direto", start_date=(hoje - dt.timedelta(days=dias)).isoformat()
    )
    return curvas_tesouro(rows, dias=30)
