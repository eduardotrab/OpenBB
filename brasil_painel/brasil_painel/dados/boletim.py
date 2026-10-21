"""Economic bulletin data: Focus expectations, quotes and agribusiness (plan 17).

Quotes come from public APIs without keys: ECB reference rates (through the
local OpenBB API), IMF commodity prices (monthly), Mercado Bitcoin and Binance
(crypto). Crypto is fetched by the server with a short cache, never by the browser.
"""

import datetime as dt
import threading
import time
from dataclasses import dataclass

import requests

from brasil_painel.dados import abertura
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient

GRAMAS_POR_ONCA = 31.1035
FOCUS = [
    ("IPCA", "IPCA", "%"),
    ("PIB Total", "PIB", "%"),
    ("Câmbio", "Câmbio", "R$/US$"),
    ("Selic", "Selic", "% a.a."),
]
MOEDAS = [
    ("USD", "USDBRL"),
    ("EUR", "EURBRL"),
    ("JPY", "JPYBRL"),
    ("GBP", "GBPBRL"),
    ("CNY", "CNYBRL"),
]
METAIS_PETROLEO = [
    ("Ouro (grama)", "PCPS::PGOLD"),
    ("Petróleo Brent", "PCPS::POILBRE"),
    ("Petróleo WTI", "PCPS::POILWTI"),
]
AGRO = [("Soja", "PCPS::PSOYB", "US$/t"), ("Milho", "PCPS::PMAIZMT", "US$/t"), ("Boi", "PCPS::PBEEF", "US¢/lb"),
        ("Café arábica", "PCPS::PCOFFOTM", "US¢/lb")]  # fmt: skip

Pontos = list[tuple[dt.date, float]]


def semanal(pontos: Pontos) -> Pontos:
    """Last value of each ISO week, oldest first."""
    por_semana: dict[tuple[int, int], tuple[dt.date, float]] = {}
    for data, valor in sorted(pontos):
        por_semana[data.isocalendar()[:2]] = (data, valor)
    return [por_semana[k] for k in sorted(por_semana)]


def sequencia(semanas: Pontos, tolerancia: float = 1e-9) -> tuple[str, int]:
    """Direction of the last weekly move and for how many weeks in a row it holds."""
    if len(semanas) < 2:
        return "estavel", 0

    def direcao(a: float, b: float) -> str:
        if abs(b - a) <= tolerancia:
            return "estavel"
        return "sobe" if b > a else "desce"

    passos = [direcao(a, b) for (_, a), (_, b) in zip(semanas, semanas[1:])]
    atual, n = passos[-1], 0
    for passo in reversed(passos):
        if passo != atual:
            break
        n += 1
    return atual, n


def variacao_pct(pontos: Pontos, dias: int) -> float | None:
    """% change of the last value against the last one at least `dias` before."""
    if not pontos:
        return None
    pontos = sorted(pontos)
    data, ultimo = pontos[-1]
    antes = [v for d, v in pontos if d <= data - dt.timedelta(days=dias)]
    return (ultimo / antes[-1] - 1) * 100 if antes and antes[-1] else None


@dataclass(frozen=True)
class Expectativa:
    """One Focus indicator for one reference year."""

    rotulo: str
    unidade: str
    ano: int
    valor: float | None
    tendencia: str
    semanas: int


@dataclass(frozen=True)
class Cotacao:
    """A quote with its reference date and change."""

    rotulo: str
    valor: float | None
    unidade: str
    data: dt.date | None
    variacao: float | None
    periodo: str  # "semanal" or "mensal"
    fonte: str


def expectativas(
    client: OpenBBClient, hoje: dt.date | None = None
) -> list[Expectativa]:
    """Focus medians of this year and the next, with the weekly direction."""
    hoje = hoje or dt.date.today()
    dados = abertura.focus(client, hoje)
    saida = []
    for nome, rotulo, unidade in FOCUS:
        for ano in (hoje.year, hoje.year + 1):
            pontos = dados.get(nome, {}).get(ano, [])
            semanas = semanal(pontos)
            tendencia, n = sequencia(semanas)
            saida.append(
                Expectativa(
                    rotulo,
                    unidade,
                    ano,
                    pontos[-1][1] if pontos else None,
                    tendencia,
                    n,
                )
            )
    return saida


def moedas(client: OpenBBClient, hoje: dt.date | None = None) -> list[Cotacao]:
    """Real against the main currencies, and EUR/USD (ECB reference rates)."""
    hoje = hoje or dt.date.today()
    desde = (hoje - dt.timedelta(days=21)).isoformat()
    saida = []
    for codigo, simbolo in [*MOEDAS, ("EUR/USD", "EURUSD")]:
        try:
            rows = client.get(
                "currency/price/historical",
                provider="ecb",
                symbol=simbolo,
                start_date=desde,
            )
        except FonteIndisponivel:
            saida.append(
                Cotacao(_rotulo_moeda(codigo), None, "", None, None, "semanal", "BCE")
            )
            continue
        pontos = [(dt.date.fromisoformat(r["date"][:10]), r["close"]) for r in rows]
        unidade = "US$" if codigo == "EUR/USD" else "R$"
        saida.append(Cotacao(_rotulo_moeda(codigo), pontos[-1][1], unidade, pontos[-1][0],
                             variacao_pct(pontos, 7), "semanal", "BCE"))  # fmt: skip
    return saida


def _rotulo_moeda(codigo: str) -> str:
    return codigo if "/" in codigo else f"BRL-{codigo}"


def _imf(client: OpenBBClient, simbolos: list[str], hoje: dt.date) -> dict[str, Pontos]:
    rows = client.get(
        "economy/indicators",
        provider="imf",
        symbol=",".join(simbolos),
        country="G001",
        frequency="month",
        start_date=(hoje - dt.timedelta(days=120)).isoformat(),
    )
    series: dict[str, Pontos] = {}
    for r in rows:
        if r.get("unit") == "Unit prices - US dollars" and r.get("value") is not None:
            series.setdefault(r["symbol"], []).append(
                (dt.date.fromisoformat(r["date"][:10]), r["value"])
            )
    return series


def metais_petroleo(client: OpenBBClient, hoje: dt.date | None = None) -> list[Cotacao]:
    """Gold per gram, Brent and WTI (IMF, monthly)."""
    hoje = hoje or dt.date.today()
    series = _imf(client, [s for _, s in METAIS_PETROLEO], hoje)
    saida = []
    for rotulo, simbolo in METAIS_PETROLEO:
        pontos = sorted(series.get(simbolo, []))
        if simbolo.endswith("PGOLD"):
            pontos = [(d, v / GRAMAS_POR_ONCA) for d, v in pontos]
        unidade = "US$/g" if simbolo.endswith("PGOLD") else "US$/barril"
        saida.append(Cotacao(rotulo, pontos[-1][1] if pontos else None, unidade, pontos[-1][0] if pontos else None,
                             variacao_pct(pontos, 25), "mensal", "IMF"))  # fmt: skip
    return saida


def agro(client: OpenBBClient, hoje: dt.date | None = None) -> list[Cotacao]:
    """Soy, corn, cattle and coffee international prices (IMF, monthly)."""
    hoje = hoje or dt.date.today()
    series = _imf(client, [s for _, s, _ in AGRO], hoje)
    saida = []
    for rotulo, simbolo, unidade in AGRO:
        pontos = sorted(series.get(simbolo, []))
        saida.append(Cotacao(rotulo, pontos[-1][1] if pontos else None, unidade, pontos[-1][0] if pontos else None,
                             variacao_pct(pontos, 25), "mensal", "IMF"))  # fmt: skip
    return saida


_CACHE: dict[str, tuple[float, list[Cotacao]]] = {}
_TRAVA = threading.Lock()
CACHE_CRIPTO = 600  # seconds


def _candles_mercado_bitcoin(par: str, sessao: requests.Session) -> Pontos:
    agora = int(time.time())
    r = sessao.get(
        "https://api.mercadobitcoin.net/api/v4/candles",
        params={
            "symbol": par,
            "resolution": "1d",
            "from": agora - 10 * 86400,
            "to": agora,
        },
        timeout=20,
    )
    r.raise_for_status()
    corpo = r.json()
    return [
        (dt.datetime.fromtimestamp(t, dt.UTC).date(), float(c))
        for t, c in zip(corpo["t"], corpo["c"])
    ]


def _candles_binance(simbolo: str, sessao: requests.Session) -> Pontos:
    r = sessao.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": simbolo, "interval": "1d", "limit": 9},
        timeout=20,
    )
    r.raise_for_status()
    return [
        (dt.datetime.fromtimestamp(k[0] / 1000, dt.UTC).date(), float(k[4]))
        for k in r.json()
    ]


def cripto(sessao: requests.Session | None = None) -> list[Cotacao]:
    """Bitcoin and Ether in R$ (Mercado Bitcoin) and BNB in US$ (Binance), 7-day change."""
    with _TRAVA:
        salvo = _CACHE.get("cripto")
    if salvo and time.monotonic() - salvo[0] < CACHE_CRIPTO:
        return salvo[1]
    sessao = sessao or requests.Session()
    fontes = [
        (
            "Bitcoin",
            "R$",
            "Mercado Bitcoin",
            lambda: _candles_mercado_bitcoin("BTC-BRL", sessao),
        ),
        (
            "Ether",
            "R$",
            "Mercado Bitcoin",
            lambda: _candles_mercado_bitcoin("ETH-BRL", sessao),
        ),
        ("BNB", "US$", "Binance", lambda: _candles_binance("BNBUSDT", sessao)),
    ]
    saida = []
    for rotulo, unidade, fonte, buscar in fontes:
        try:
            pontos = buscar()
        except (requests.RequestException, KeyError, ValueError):
            saida.append(Cotacao(rotulo, None, unidade, None, None, "semanal", fonte))
            continue
        saida.append(
            Cotacao(
                rotulo,
                pontos[-1][1],
                unidade,
                pontos[-1][0],
                variacao_pct(pontos, 7),
                "semanal",
                fonte,
            )
        )
    with _TRAVA:
        _CACHE["cripto"] = (time.monotonic(), saida)
    return saida
