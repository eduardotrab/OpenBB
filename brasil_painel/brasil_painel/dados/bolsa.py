"""Stock market monitor data: delayed B3 quotes, intraday and daily candles (plan 18).

Quotes come from the public B3 quotation service (delayed, no key), one asset
per request, fetched in parallel with a 2-minute cache. Outside trading hours
the last COTAHIST close stands in.
"""

import datetime as dt
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pandas as pd
import requests

from brasil_painel.dados.classes import DadosAusentes
from brasil_painel.regional import armazem

URL = "https://cotacao.b3.com.br/mds/api/v1"
CACHE_SEGUNDOS = 120
_CACHE: dict[tuple[str, str], tuple[float, object]] = {}
_TRAVA = threading.Lock()


@dataclass(frozen=True)
class Cotacao:
    """Delayed quote of one asset."""

    ticker: str
    nome: str
    ultimo: float | None
    variacao: float | None  # % against the previous close
    abertura: float | None = None
    maxima: float | None = None
    minima: float | None = None
    negocios: float | None = None
    momento: str = ""
    atrasada: bool = True  # False when it is the last daily close


def _guardado(chave: tuple[str, str]):
    with _TRAVA:
        salvo = _CACHE.get(chave)
    return salvo[1] if salvo and time.monotonic() - salvo[0] < CACHE_SEGUNDOS else None


def _guardar(chave: tuple[str, str], valor) -> None:
    with _TRAVA:
        _CACHE[chave] = (time.monotonic(), valor)


def _consultado(momento: str) -> str:
    """'2026-10-21 01:52:22' → 'consultado em 21/10/2026 às 01:52'."""
    try:
        quando = dt.datetime.fromisoformat(momento)
    except ValueError:
        return ""
    return f"consultado em {quando:%d/%m/%Y} às {quando:%H:%M}"


def ler_cotacao(corpo: dict, ticker: str) -> Cotacao | None:
    """B3 `instrumentQuotation` body → Cotacao (None when there is no price)."""
    negocios = corpo.get("Trad") or []
    if not negocios:
        return None
    titulo = negocios[0].get("scty", {})
    preco = titulo.get("SctyQtn", {})
    if preco.get("curPrc") is None:
        return None
    return Cotacao(
        ticker=titulo.get("symb", ticker),
        nome=" ".join(str(titulo.get("desc", "")).split()),
        ultimo=preco.get("curPrc"),
        variacao=preco.get("prcFlcn"),
        abertura=preco.get("opngPric"),
        maxima=preco.get("maxPric"),
        minima=preco.get("minPric"),
        negocios=negocios[0].get("ttlQty"),
        momento=_consultado(corpo.get("Msg", {}).get("dtTm", "")),
    )


def fechamento(ticker: str) -> Cotacao | None:
    """Last daily close from COTAHIST, with the change against the previous one."""
    df = armazem.ler("b3_diario")
    if df is None:
        return None
    linhas = df[df.ticker == ticker].sort_values("data").tail(2)
    if linhas.empty:
        return None
    ultima = linhas.iloc[-1]
    variacao = (
        (ultima.fechamento / linhas.iloc[0].fechamento - 1) * 100
        if len(linhas) == 2
        else None
    )
    return Cotacao(ticker, ultima.nome, ultima.fechamento, variacao, ultima.abertura, ultima.maxima,
                   ultima.minima, float(ultima.negocios), f"fechamento de {ultima.data:%d/%m/%Y}", False)  # fmt: skip


def cotacao(ticker: str, sessao: requests.Session | None = None) -> Cotacao | None:
    """Delayed quote, or the last close when the quotation service has no price."""
    chave = ("cotacao", ticker)
    if (salvo := _guardado(chave)) is not None:
        return salvo
    resultado = None
    try:
        r = (sessao or requests).get(f"{URL}/instrumentQuotation/{ticker}", timeout=15)
        r.raise_for_status()
        resultado = ler_cotacao(r.json(), ticker)
    except (requests.RequestException, ValueError):
        resultado = None
    resultado = resultado or fechamento(ticker)
    if resultado is not None:
        _guardar(chave, resultado)
    return resultado


def cotacoes(tickers: list[str]) -> list[Cotacao]:
    """Quotes of several assets in parallel (8 at a time)."""
    with ThreadPoolExecutor(max_workers=8) as grupo:
        resultados = list(grupo.map(cotacao, tickers))
    return [c for c in resultados if c is not None]


def intradia(
    ticker: str, sessao: requests.Session | None = None
) -> list[tuple[str, float]]:
    """Minute closes of the current session (empty outside trading days)."""
    chave = ("intradia", ticker)
    if (salvo := _guardado(chave)) is not None:
        return salvo
    try:
        r = (sessao or requests).get(
            f"{URL}/DailyFluctuationHistory/{ticker}", timeout=15
        )
        r.raise_for_status()
        pontos = r.json().get("TradgFlr", {}).get("scty", {}).get("lstQtn", [])
        dia = r.json().get("TradgFlr", {}).get("date", "")
        serie = [
            (f"{dia} {p['dtTm']}", p["closPric"])
            for p in pontos
            if p.get("closPric") is not None
        ]
    except (requests.RequestException, ValueError, KeyError):
        serie = []
    _guardar(chave, serie)
    return serie


def candles(ticker: str, dias: int = 180) -> pd.DataFrame:
    """Daily candles of the last `dias` days from COTAHIST."""
    df = armazem.ler("b3_diario")
    if df is None:
        raise DadosAusentes(
            "Dados de 'b3_diario' ainda não foram baixados: rode `painel-dados atualizar b3`."
        )
    df = df[df.ticker == ticker]
    if df.empty:
        return df
    corte = df.data.max() - dt.timedelta(days=dias)
    return df[df.data >= corte].sort_values("data")


def carteira() -> pd.DataFrame:
    """Ibovespa portfolio (ticker, name, weight %), largest first."""
    df = armazem.ler("b3_ibov")
    if df is None:
        raise DadosAusentes(
            "Dados de 'b3_ibov' ainda não foram baixados: rode `painel-dados atualizar b3`."
        )
    return df.sort_values("peso", ascending=False, ignore_index=True)


def altas_baixas(
    quotes: list[Cotacao], n: int = 5
) -> tuple[list[Cotacao], list[Cotacao]]:
    """Largest gains and losses among the quotes with a known change."""
    com_var = sorted(
        (c for c in quotes if c.variacao is not None),
        key=lambda c: c.variacao,
        reverse=True,
    )
    return com_var[:n], list(reversed(com_var[-n:]))
