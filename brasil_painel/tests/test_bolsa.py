"""Stock monitor: quote parsing, close fallback and movers."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import bolsa
from brasil_painel.regional import armazem, b3

CORPO = {
    "BizSts": {"cd": "OK"},
    "Msg": {"dtTm": "2026-10-20 17:30:00"},
    "Trad": [{"scty": {"SctyQtn": {"opngPric": 58.82, "minPric": 56.91, "maxPric": 59.1, "curPrc": 58.07,
                                   "prcFlcn": 0.12}, "symb": "PETR4", "desc": "PETROBRAS   PN      N2"},
              "ttlQty": 67631}],
}  # fmt: skip


def test_quote_body_is_parsed():
    c = bolsa.ler_cotacao(CORPO, "PETR4")
    assert (c.ticker, c.nome, c.ultimo, c.variacao, c.negocios) == (
        "PETR4",
        "PETROBRAS PN N2",
        58.07,
        0.12,
        67631,
    )
    assert bolsa.ler_cotacao({"BizSts": {"cd": "NOK"}}, "PETR4") is None


def test_close_fallback_when_quotation_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = [
        dict(data=dt.date(2026, 10, 19), ticker="PETR4", nome="PETROBRAS", abertura=1.0, maxima=1.0, minima=1.0,
             fechamento=50.0, negocios=10, volume=1.0),
        dict(data=dt.date(2026, 10, 20), ticker="PETR4", nome="PETROBRAS", abertura=1.0, maxima=1.0, minima=1.0,
             fechamento=55.0, negocios=10, volume=1.0),
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(linhas), "b3_diario", b3.SCHEMA_DIARIO)

    class Sessao:
        def get(self, url, timeout):
            class R:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"BizSts": {"cd": "NOK"}}

            return R()

    bolsa._CACHE.clear()
    c = bolsa.cotacao("PETR4", Sessao())
    assert (c.ultimo, c.atrasada) == (55.0, False)
    assert c.variacao == pytest.approx(10.0)
    bolsa._CACHE.clear()


def test_movers_ignore_unknown_changes():
    quotes = [
        bolsa.Cotacao(t, t, 1.0, v)
        for t, v in [("A", 3.0), ("B", -2.0), ("C", None), ("D", 1.0)]
    ]
    altas, baixas = bolsa.altas_baixas(quotes, n=2)
    assert [c.ticker for c in altas] == ["A", "D"]
    assert [c.ticker for c in baixas] == ["B", "D"]


def test_quote_time_is_written_in_portuguese():
    assert (
        bolsa.ler_cotacao(CORPO, "PETR4").momento == "consultado em 20/10/2026 às 17:30"
    )
