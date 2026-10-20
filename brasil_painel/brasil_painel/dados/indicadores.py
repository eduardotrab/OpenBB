"""Pure functions behind the indicator cards (no I/O)."""

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class Ponto:
    """One observation of a series."""

    data: dt.date
    valor: float


@dataclass(frozen=True)
class Resumo:
    """What a card shows."""

    nome: str
    unidade: str
    fonte: str
    valor: float | None = None
    data_ref: dt.date | None = None
    anterior: float | None = None
    variacao: float | None = None
    tendencia: str | None = None
    defasado: bool = False
    erro: str | None = None
    comparacao: str = ""
    mensal: bool = False
    casas: int = 2
    percentual: bool = False
    anual: bool = False


def tendencia(atual: float, anterior: float, tolerancia: float = 1e-9) -> str:
    """'sobe', 'desce' or 'estavel' (relative tolerance)."""
    if abs(atual - anterior) <= tolerancia * max(abs(anterior), 1.0):
        return "estavel"
    return "sobe" if atual > anterior else "desce"


def data_de_periodo(periodo: str) -> dt.date:
    """'AAAAMM' (IBGE) → first day of the month; ISO dates are parsed as is."""
    if len(periodo) == 6 and periodo.isdigit():
        return dt.date(int(periodo[:4]), int(periodo[4:]), 1)
    return dt.date.fromisoformat(periodo[:10])


def _anterior_por_dias(pontos: list[Ponto], dias: int) -> Ponto | None:
    limite = pontos[-1].data - dt.timedelta(days=dias)
    candidatos = [p for p in pontos[:-1] if p.data <= limite]
    return candidatos[-1] if candidatos else None


def resumir(
    nome: str,
    pontos: list[Ponto],
    *,
    unidade: str,
    fonte: str,
    max_dias: int,
    hoje: dt.date,
    passos: int | None = None,
    dias: int | None = None,
    tolerancia: float = 1e-4,
    comparacao: str = "",
    mensal: bool = False,
    casas: int = 2,
    percentual: bool = False,
    anual: bool = False,
) -> Resumo:
    """Summarise a series: last value vs `passos` observations or `dias` days back.

    `defasado` is set when the last observation is older than `max_dias`;
    `percentual` reports the change in % of the previous value.
    """
    extra = dict(
        comparacao=comparacao,
        mensal=mensal,
        casas=casas,
        percentual=percentual,
        anual=anual,
    )
    if not pontos:
        return Resumo(nome, unidade, fonte, erro="Sem dados da fonte.", **extra)
    pontos = sorted(pontos, key=lambda p: p.data)
    ultimo = pontos[-1]
    if dias is not None:
        anterior = _anterior_por_dias(pontos, dias)
    else:
        n = passos or 1
        anterior = pontos[-1 - n] if len(pontos) > n else None
    base = dict(
        valor=ultimo.valor,
        data_ref=ultimo.data,
        defasado=(hoje - ultimo.data).days > max_dias,
        **extra,
    )
    if anterior is None:
        return Resumo(nome, unidade, fonte, **base)
    return Resumo(
        nome,
        unidade,
        fonte,
        anterior=anterior.valor,
        variacao=(
            (ultimo.valor / anterior.valor - 1) * 100
            if percentual
            else ultimo.valor - anterior.valor
        ),
        tendencia=tendencia(ultimo.valor, anterior.valor, tolerancia),
        **base,
    )
