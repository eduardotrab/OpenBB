"""Formatting and card rendering."""

import datetime as dt

from brasil_painel.componentes.cartoes import cartao
from brasil_painel.dados import formato
from brasil_painel.dados.indicadores import Resumo


def test_numero_ptbr():
    assert formato.numero(1234.5) == "1.234,50"
    assert formato.numero(-0.25, sinal=True) == "-0,25"
    assert formato.numero(0.3, 4, sinal=True) == "+0,3000"


def test_data():
    assert formato.data(dt.date(2026, 10, 20)) == "20/10/2026"
    assert formato.data(dt.date(2026, 9, 1), mensal=True) == "set/2026"


def _texto(componente) -> str:
    filhos = getattr(componente, "children", componente)
    if isinstance(filhos, list):
        return " ".join(_texto(f) for f in filhos)
    if isinstance(filhos, str):
        return filhos
    return _texto(filhos) if filhos is not None else ""


def test_cartao_shows_value_reference_and_trend():
    r = Resumo(
        "Selic meta",
        "% a.a.",
        "BCB",
        valor=13.75,
        data_ref=dt.date(2026, 10, 20),
        anterior=15.0,
        variacao=-1.25,
        tendencia="desce",
        comparacao="em 12 meses",
    )
    texto = _texto(cartao(r))
    assert (
        "13,75" in texto
        and "▼ -1,25 em 12 meses" in texto
        and "ref. 20/10/2026" in texto
    )


def test_cartao_flags_stale_and_error():
    velho = Resumo(
        "X", "%", "F", valor=1.0, data_ref=dt.date(2026, 1, 1), defasado=True
    )
    assert "desatualizado" in _texto(cartao(velho))
    erro = Resumo("X", "%", "F", erro="timeout")
    assert "Fonte indisponível" in _texto(cartao(erro))
