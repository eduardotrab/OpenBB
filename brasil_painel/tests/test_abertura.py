"""Opening-screen data assembly with a fake API client."""

import datetime as dt

from brasil_painel.dados.abertura import indicadores
from brasil_painel.dados.api import FonteIndisponivel


class FakeClient:
    def __init__(self, respostas):
        self.respostas = respostas

    def get(self, path, **params):
        chave = params.get("symbol") or params.get("table")
        resposta = self.respostas.get((path, chave))
        if resposta is None:
            raise FonteIndisponivel(path)
        return resposta


def test_indicadores_build_cards_and_isolate_failures():
    hoje = dt.date(2026, 10, 20)
    client = FakeClient(
        {
            ("bcb/sgs", "432"): [
                {"date": "2025-10-01", "value": 15.0},
                {"date": "2026-10-20", "value": 13.75},
            ],
            ("ibge/aggregates", "1737"): [
                {"period": "202608", "value": 4.7},
                {"period": "202609", "value": 4.58},
            ],
        }
    )
    cards = {c.nome: c for c in indicadores(client, hoje)}
    assert cards["Selic meta"].variacao == -1.25
    assert cards["IPCA 12 meses"].data_ref == dt.date(2026, 9, 1)
    assert cards["IPCA 12 meses"].tendencia == "desce"
    assert cards["Dólar (PTAX venda)"].erro
    assert len(cards) == 5
