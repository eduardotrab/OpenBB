"""Pure transformations for the Focus and Tesouro Direto charts."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

Serie = list[tuple[dt.date, float]]

TIPOS_CURVA = {"Prefixado": "Tesouro Prefixado", "IPCA+": "Tesouro IPCA+"}


def series_focus(rows: list[dict], anos: list[int]) -> dict[int, Serie]:
    """Median expectation per reference year, over survey dates."""
    series: dict[int, Serie] = {ano: [] for ano in anos}
    for row in rows:
        ref = str(row.get("reference", ""))
        if not ref.isdigit() or int(ref) not in series or row.get("median") is None:
            continue
        series[int(ref)].append(
            (dt.date.fromisoformat(row["date"][:10]), row["median"])
        )
    return {ano: sorted(pontos) for ano, pontos in series.items() if pontos}


@dataclass(frozen=True)
class Curvas:
    """Yield curves (maturity → rate) on the last date and `dias` before."""

    data: dt.date
    hoje: dict[str, Serie]
    data_anterior: dt.date | None
    anterior: dict[str, Serie]


def _tipo(bond: str) -> str | None:
    for tipo, prefixo in TIPOS_CURVA.items():
        if bond.startswith(prefixo):
            return tipo
    return None


def _curva(rows: list[dict], data: dt.date) -> dict[str, Serie]:
    """One rate per maturity; the zero-coupon bond wins over the semiannual one."""
    curva: dict[str, dict[dt.date, tuple[bool, float]]] = defaultdict(dict)
    for row in rows:
        tipo = _tipo(row["bond"])
        taxa = (
            row.get("buy_rate")
            if row.get("buy_rate") is not None
            else row.get("sell_rate")
        )
        if not tipo or taxa is None:
            continue
        if dt.date.fromisoformat(row["date"][:10]) != data:
            continue
        vencimento = dt.date.fromisoformat(row["maturity"][:10])
        zero_cupom = row["bond"] == TIPOS_CURVA[tipo]
        atual = curva[tipo].get(vencimento)
        if atual is None or (zero_cupom and not atual[0]):
            curva[tipo][vencimento] = (zero_cupom, taxa)
    return {
        tipo: sorted((venc, taxa) for venc, (_, taxa) in pontos.items())
        for tipo, pontos in curva.items()
    }


def curvas_tesouro(rows: list[dict], dias: int = 30) -> Curvas:
    """Prefixado and IPCA+ curves on the last date and the last date ≤ `dias` before."""
    datas = sorted({dt.date.fromisoformat(r["date"][:10]) for r in rows})
    ultima = datas[-1]
    limite = ultima - dt.timedelta(days=dias)
    anteriores = [d for d in datas if d <= limite]
    data_anterior = anteriores[-1] if anteriores else None
    return Curvas(
        data=ultima,
        hoje=_curva(rows, ultima),
        data_anterior=data_anterior,
        anterior=_curva(rows, data_anterior) if data_anterior else {},
    )
