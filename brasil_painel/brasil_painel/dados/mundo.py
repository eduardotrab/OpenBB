"""World page data from sources without API keys (Fed, OECD, IMF, ECB).

OECD/IMF/Fed rates come as fractions (0.0388) and are shown in % (3.88).
"""

import datetime as dt
from collections import defaultdict

from brasil_painel.dados.abertura import Spec, montar_cartoes, serie_ibge, serie_sgs
from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient
from brasil_painel.dados.indicadores import Ponto, Resumo

Series = dict[str, list[Ponto]]

ECB_DEPOSITO = "FM::B.U2.EUR.4F.KR.DFR.LEV"  # only the dates of change
EUA, OECD_CHINA, OECD_ZONA_EURO = (
    "United States",
    "China (People’s Republic of)",
    "Euro area",
)
IMF_CHINA = "China, People's Republic of"

# IMF primary commodity prices: symbol → (label, unit)
COMMODITIES = {
    "PCPS::PSOYB": ("Soja", "US$/t"),
    "PCPS::PMAIZMT": ("Milho", "US$/t"),
    "PCPS::PBEEF": ("Boi", "US¢/lb"),
    "PCPS::PCOFFOTM": ("Café arábica", "US¢/lb"),
}
UNIDADE_DOLAR = "Unit prices - US dollars"


def _data(texto: str) -> dt.date:
    return dt.date.fromisoformat(texto[:10])


def _ordenar(pontos) -> list[Ponto]:
    return sorted(pontos, key=lambda p: p.data)


def serie(rows: list[dict], campo: str, escala: float = 1.0) -> list[Ponto]:
    """Sorted points of one field, skipping empty values."""
    return _ordenar(
        Ponto(_data(r["date"]), r[campo] * escala)
        for r in rows
        if r.get(campo) is not None
    )


def por_pais(rows: list[dict], escala: float = 1.0) -> Series:
    """Split a multi-country response into one sorted series per country."""
    series: Series = defaultdict(list)
    for r in rows:
        if r.get("value") is not None:
            series[r["country"]].append(Ponto(_data(r["date"]), r["value"] * escala))
    return {pais: _ordenar(pontos) for pais, pontos in series.items()}


def precos_commodities(rows: list[dict]) -> Series:
    """Dollar prices per symbol (the IMF also returns index and % rows)."""
    series: Series = defaultdict(list)
    for r in rows:
        if r.get("unit") == UNIDADE_DOLAR and r.get("value") is not None:
            series[r["symbol"]].append(Ponto(_data(r["date"]), r["value"]))
    return {simbolo: _ordenar(pontos) for simbolo, pontos in series.items()}


def degraus(mudancas: list[Ponto], hoje: dt.date) -> list[Ponto]:
    """Extend a rate known only at its change dates up to today."""
    if not mudancas or mudancas[-1].data >= hoje:
        return mudancas
    return [*mudancas, Ponto(hoje, mudancas[-1].valor)]


def inicio_do_mes(pontos: list[Ponto]) -> list[Ponto]:
    """Date monthly points on day 1 (the IMF uses the last day, the IBGE the first)."""
    return [Ponto(p.data.replace(day=1), p.valor) for p in pontos]


def recortar(pontos: list[Ponto], desde: dt.date) -> list[Ponto]:
    """Keep points from `desde`, starting with the value in force on that date."""
    vigente = [p for p in pontos if p.data <= desde]
    depois = [p for p in pontos if p.data > desde]
    return ([Ponto(desde, vigente[-1].valor)] if vigente else []) + depois


def indice_base_100(pontos: list[Ponto], dias: int = 365) -> list[Ponto]:
    """Rebase to 100 at the last point at least `dias` before the latest one."""
    if not pontos:
        return []
    limite = pontos[-1].data - dt.timedelta(days=dias)
    inicio = max(
        (i for i, p in enumerate(pontos) if p.data <= limite + dt.timedelta(days=5)),
        default=0,
    )
    base = pontos[inicio].valor
    return [Ponto(p.data, p.valor / base * 100) for p in pontos[inicio:]]


# --- fetchers (the client caches identical calls, so cards and charts share them)


def _effr(client: OpenBBClient, desde: dt.date) -> list[Ponto]:
    rows = client.get(
        "fixedincome/rate/effr",
        provider="federal_reserve",
        start_date=desde.isoformat(),
    )
    return serie(rows, "rate", 100)


def _treasury_10a(client: OpenBBClient, desde: dt.date) -> list[Ponto]:
    rows = client.get(
        "fixedincome/government/treasury_rates",
        provider="federal_reserve",
        start_date=desde.isoformat(),
    )
    return serie(rows, "year_10", 100)


def _oecd(
    client: OpenBBClient, rota: str, pais: str, desde: dt.date, **extra
) -> Series:
    """US + China (or + euro area) in one call, since the OECD is slow (~8–20 s)."""
    rows = client.get(
        rota, provider="oecd", country=pais, start_date=desde.isoformat(), **extra
    )
    return por_pais(rows, 1 if rota.endswith("leading_indicator") else 100)


def _cpi(client: OpenBBClient, desde: dt.date) -> Series:
    """US and China CPI from the IMF (the OECD drops older US months)."""
    rows = client.get(
        "economy/cpi",
        provider="imf",
        country="united_states,china",
        start_date=desde.isoformat(),
    )
    return por_pais(rows, 100)


def _desemprego(client: OpenBBClient, desde: dt.date) -> Series:
    return _oecd(client, "economy/unemployment", "united_states,EA", desde)


def _cli_china(client: OpenBBClient, desde: dt.date) -> list[Ponto]:
    serie_ = _oecd(client, "economy/composite_leading_indicator", "china", desde)
    return serie_.get(OECD_CHINA, [])


def _do_pais(series: Series, pais: str) -> list[Ponto]:
    if pais not in series:
        raise FonteIndisponivel(f"sem dados de {pais}")
    return series[pais]


def _hicp(client: OpenBBClient, desde: dt.date) -> list[Ponto]:
    rows = client.get(
        "economy/cpi",
        provider="imf",
        country="euro_area",
        harmonized="true",
        start_date=desde.isoformat(),
    )
    return serie(rows, "value", 100)


def _deposito_bce(client: OpenBBClient, hoje: dt.date) -> list[Ponto]:
    rows = client.get("economy/indicators", provider="ecb", symbol=ECB_DEPOSITO)
    return degraus(serie(rows, "value"), hoje)


def _cambio(client: OpenBBClient, par: str, desde: dt.date) -> list[Ponto]:
    rows = client.get(
        "currency/price/historical",
        provider="ecb",
        symbol=par,
        start_date=desde.isoformat(),
    )
    return serie(rows, "close")


def _commodities(client: OpenBBClient, desde: dt.date) -> Series:
    rows = client.get(
        "economy/indicators",
        provider="imf",
        symbol=",".join(COMMODITIES),
        country="G001",
        frequency="month",
        start_date=desde.isoformat(),
    )
    return precos_commodities(rows)


def _de(series: Series, chave: str) -> list[Ponto]:
    if chave not in series:
        raise FonteIndisponivel(f"sem dados de {chave}")
    return series[chave]


# --- page data


def cartoes(
    client: OpenBBClient, hoje: dt.date | None = None
) -> dict[str, list[Resumo]]:
    """Cards per block id of the world page."""
    hoje = hoje or dt.date.today()
    ano = hoje - dt.timedelta(days=400)
    mensal = hoje - dt.timedelta(days=500)  # reaches the month 12 months back
    dois_anos = hoje - dt.timedelta(days=760)
    diario_12m = dict(unidade="% a.a.", dias=365, max_dias=5, comparacao="em 12 meses")
    mensal_cpi = dict(
        unidade="%", passos=1, max_dias=80, comparacao="vs. mês anterior", mensal=True
    )
    mensal_12m = dict(
        unidade="%", dias=365, max_dias=80, comparacao="vs. 12 meses antes", mensal=True
    )
    cambio = dict(
        dias=30, max_dias=5, comparacao="em 30 dias", casas=4, percentual=True
    )
    commodity = dict(
        passos=12,
        max_dias=80,
        comparacao="em 12 meses",
        mensal=True,
        percentual=True,
        fonte="IMF",
    )
    specs: dict[str, list[Spec]] = {
        "mundo-eua": [
            (
                "Fed funds (efetiva)",
                lambda: _effr(client, ano),
                dict(fonte="Fed", **diario_12m),
            ),
            (
                "Treasury 10 anos",
                lambda: _treasury_10a(client, hoje - dt.timedelta(days=45)),
                dict(
                    fonte="Fed",
                    unidade="% a.a.",
                    dias=30,
                    max_dias=5,
                    comparacao="em 30 dias",
                ),
            ),
            (
                "Inflação 12 meses",
                lambda: _do_pais(_cpi(client, mensal), EUA),
                dict(fonte="IMF", **mensal_cpi),
            ),
            (
                "Desemprego",
                lambda: _do_pais(_desemprego(client, mensal), EUA),
                dict(fonte="OCDE", **mensal_12m),
            ),
        ],
        "mundo-europa": [
            (
                "Taxa de depósito do BCE",
                lambda: _deposito_bce(client, hoje),
                dict(fonte="BCE", **diario_12m),
            ),
            (
                "Inflação 12 meses (HICP)",
                lambda: _hicp(client, mensal),
                dict(fonte="IMF", **mensal_cpi),
            ),
            (
                "Desemprego",
                lambda: _do_pais(_desemprego(client, mensal), OECD_ZONA_EURO),
                dict(fonte="OCDE", **mensal_cpi),
            ),
        ],
        "mundo-china": [
            (
                "Inflação 12 meses",
                lambda: _do_pais(_cpi(client, mensal), IMF_CHINA),
                dict(fonte="IMF", **mensal_cpi),
            ),
            (
                "Indicador antecedente",
                lambda: _cli_china(client, mensal),
                dict(
                    fonte="OCDE (CLI, 100 = tendência)",
                    unidade="pts",
                    passos=1,
                    max_dias=80,
                    comparacao="vs. mês anterior",
                    mensal=True,
                ),
            ),
        ],
        "mundo-cambio": [
            (
                "EUR/USD",
                lambda: _cambio(client, "EURUSD", hoje - dt.timedelta(days=45)),
                dict(unidade="US$", fonte="BCE", **cambio),
            ),
            (
                "USD/CNY",
                lambda: _cambio(client, "USDCNY", hoje - dt.timedelta(days=45)),
                dict(unidade="¥", fonte="BCE", **cambio),
            ),
            (
                "EUR/BRL",
                lambda: _cambio(client, "EURBRL", hoje - dt.timedelta(days=45)),
                dict(unidade="R$", fonte="BCE", **cambio),
            ),
        ],
        "mundo-commodities": [
            (
                nome,
                lambda simbolo=simbolo: _de(_commodities(client, dois_anos), simbolo),
                dict(unidade=unidade, **commodity),
            )
            for simbolo, (nome, unidade) in COMMODITIES.items()
        ],
    }
    return {bloco: montar_cartoes(lista, hoje) for bloco, lista in specs.items()}


def _juntar(cargas: dict[str, callable]) -> tuple[Series, list[str]]:
    """Run each loader; returns the series that loaded and the names that failed."""
    series, falhas = {}, []
    for nome, carregar in cargas.items():
        try:
            pontos = carregar()
        except FonteIndisponivel:
            falhas.append(nome)
            continue
        if pontos:
            series[nome] = pontos
        else:
            falhas.append(nome)
    return series, falhas


def juros(
    client: OpenBBClient, hoje: dt.date | None = None
) -> tuple[Series, list[str]]:
    """Policy rates over two years: Fed funds, ECB deposit facility and Selic."""
    hoje = hoje or dt.date.today()
    desde = hoje - dt.timedelta(days=730)
    return _juntar(
        {
            "Fed funds": lambda: _effr(client, desde),
            "BCE (depósito)": lambda: recortar(_deposito_bce(client, hoje), desde),
            "Selic meta": lambda: serie_sgs(client, 432, desde),
        }
    )


def inflacao(
    client: OpenBBClient, hoje: dt.date | None = None
) -> tuple[Series, list[str]]:
    """12-month inflation over two years: US, China, euro area (IMF) and Brazil."""
    hoje = hoje or dt.date.today()
    desde = hoje - dt.timedelta(days=760)
    series, falhas = _juntar(
        {
            "EUA": lambda: _do_pais(_cpi(client, desde), EUA),
            "China": lambda: _do_pais(_cpi(client, desde), IMF_CHINA),
            "Zona do euro": lambda: _hicp(client, desde),
            "Brasil": lambda: serie_ibge(client, 1737, 2265, 25),
        }
    )
    return {nome: inicio_do_mes(p) for nome, p in series.items()}, falhas


def agro(client: OpenBBClient, hoje: dt.date | None = None) -> tuple[Series, list[str]]:
    """Commodity dollar prices rebased to 100 twelve months before the last month."""
    hoje = hoje or dt.date.today()
    desde = hoje - dt.timedelta(days=760)
    return _juntar(
        {
            nome: lambda simbolo=simbolo: indice_base_100(
                _de(_commodities(client, desde), simbolo)
            )
            for simbolo, (nome, _) in COMMODITIES.items()
        }
    )
