"""Thermometer screen: weights reach the calculation and the state panel."""

import datetime as dt
import json

import pandas as pd

from brasil_painel.dados import termometro as term
from brasil_painel.paginas import termometro as tela


def test_callback_passes_weights_and_explains_the_state(monkeypatch):
    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    chaves = list(term.configuracao())
    recebidos = {}

    def calcular(data, pesos):
        recebidos.update(pesos)
        c = pd.DataFrame(1.0, index=["MG", "SP", "BR"], columns=chaves)
        nota = pd.Series({"MG": 61.0, "SP": 39.0})
        pontos = pd.DataFrame(0.0, index=["MG", "SP"], columns=chaves)
        pontos.loc["MG", chaves[0]] = 11.0
        datas = dict.fromkeys(("scr", "pix", "desemprego"), dt.date(2026, 8, 1))
        return c, nota, pontos, datas

    monkeypatch.setattr(tela.term, "calcular", calcular)
    http = create_app(Settings(users_file=None)).server.test_client()
    ids = [{"type": "term-peso", "chave": k} for k in chaves]
    saidas = [
        "term-mapa.figure",
        "term-contexto.children",
        "term-estado.children",
        "term-ranking.children",
    ]
    payload = {
        "output": ".." + "...".join(saidas) + "..",
        "outputs": [
            {"id": s.split(".")[0], "property": s.split(".")[1]} for s in saidas
        ],
        "inputs": [
            [
                {"id": i, "property": "value", "value": 40 if n == 0 else 10}
                for n, i in enumerate(ids)
            ],
            {"id": "filtros", "property": "data", "value": {"uf": "MG", "data": ""}},
        ],
        "state": [[{"id": i, "property": "id", "value": i} for i in ids]],
        "changedPropIds": [],
    }
    resposta = http.post("/_dash-update-component", json=payload).get_json()["response"]
    texto = json.dumps(resposta, ensure_ascii=False)
    assert recebidos[chaves[0]] == 40 and recebidos[chaves[1]] == 10
    assert "Minas Gerais" in texto and "1º de 2" in texto and "+11,0" in texto
