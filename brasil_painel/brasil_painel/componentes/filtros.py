"""Global filters (UF, reference month) kept in a session Store for every screen."""

import datetime as dt

from dash import dcc, html

from brasil_painel.dados import formato
from brasil_painel.regional import armazem
from brasil_painel.regional.ufs import BRASIL, NOMES

PADRAO = {"uf": BRASIL, "data": ""}  # "" = most recent month


def opcoes_uf() -> list[dict]:
    """Brazil first, then the states by name."""
    estados = sorted(NOMES.items(), key=lambda x: x[1])
    return [{"label": "Brasil", "value": BRASIL}] + [
        {"label": f"{nome} ({sigla})", "value": sigla} for sigla, nome in estados
    ]


def meses_disponiveis() -> list[dt.date]:
    """List the reference months of the credit data, newest first (empty before ingestion)."""
    df = armazem.ler("scr_uf")
    return [] if df is None else sorted(set(df.data), reverse=True)


def opcoes_data() -> list[dict]:
    """'Mais recente' plus each available month."""
    return [{"label": "Mais recente", "value": ""}] + [
        {"label": formato.data(d, mensal=True), "value": d.isoformat()}
        for d in meses_disponiveis()
    ]


def atualizado_em() -> dt.date | None:
    """When the regional store was last refreshed."""
    caminho = armazem.diretorio() / "scr_uf.parquet"
    if not caminho.exists():
        return None
    return dt.date.fromtimestamp(caminho.stat().st_mtime)


def selo(filtros: dict | None) -> html.Div:
    """Update date and the reference month in use."""
    filtros = filtros or PADRAO
    meses = meses_disponiveis()
    base = (
        dt.date.fromisoformat(filtros["data"])
        if filtros.get("data")
        else (meses[0] if meses else None)
    )
    linhas = []
    if atualizado_em():
        linhas.append(html.Span(f"Atualizado em {formato.data(atualizado_em())}"))
    if base:
        linhas.append(html.Span(f"Data-base: {formato.data(base, mensal=True)}"))
    return html.Div(linhas, className="fs-selo-datas")


def controles() -> list:
    """Dropdowns of the top bar plus the Store they feed."""
    return [
        dcc.Dropdown(
            id="filtro-uf",
            options=opcoes_uf(),
            value=PADRAO["uf"],
            clearable=False,
            className="fs-filtro fs-filtro-uf",
            persistence=True,
            persistence_type="session",
        ),
        dcc.Dropdown(
            id="filtro-data",
            options=opcoes_data(),
            value=PADRAO["data"],
            clearable=False,
            searchable=False,
            className="fs-filtro fs-filtro-data",
            persistence=True,
            persistence_type="session",
        ),
        html.Div(id="selo-topo"),
        dcc.Store(id="filtros", storage_type="session", data=PADRAO),
    ]
