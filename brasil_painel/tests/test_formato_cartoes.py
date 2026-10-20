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


def test_agenda_marks_today():
    from brasil_painel.componentes.agenda import agenda
    from brasil_painel.dados.agenda import Evento

    hoje = dt.date(2026, 10, 20)
    texto = _texto(
        agenda(
            [
                Evento(hoje, "8h", "Copom — ata", "BCB"),
                Evento(dt.date(2026, 10, 23), "12h", "IPCA-15", "IBGE"),
            ],
            [],
            hoje,
        )
    )
    assert "hoje" in texto and "sex 23/10" in texto and "Copom — ata" in texto


def test_cartao_with_decimals_and_percent_change():
    r = Resumo(
        "EUR/USD",
        "US$",
        "ECB",
        valor=1.1225,
        data_ref=dt.date(2026, 10, 19),
        anterior=1.10,
        variacao=2.0455,
        tendencia="sobe",
        comparacao="em 30 dias",
        casas=4,
        percentual=True,
    )
    texto = _texto(cartao(r))
    assert "1,1225" in texto and "▲ +2,0% em 30 dias" in texto


def test_cartao_annual_reference_shows_the_year():
    r = Resumo(
        "PIB 2026 (projeção)",
        "%",
        "FMI (WEO)",
        valor=4.47,
        data_ref=dt.date(2026, 12, 31),
        anual=True,
    )
    assert "FMI (WEO) · ref. 2026" in _texto(cartao(r))
