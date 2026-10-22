"""Cooperatives screen: systems table, unidentified note and ranking."""

import json

import pandas as pd

from brasil_painel.paginas import cooperativas as tela
from brasil_painel.regional import armazem, ifdata
from tests.test_cooperativas import JUN25, JUN26, _linhas


def test_short_name_uses_the_trade_name():
    assert (
        tela.nome_curto("COOPERATIVA DE CRÉDITO X LTDA. - SICOOB CREDICOM")
        == "Sicoob Credicom"
    )
    assert tela.nome_curto("SICREDI Y") == "Sicredi Y"
    assert (
        tela.nome_curto(
            "SICOOB CREDICOM - COOPERATIVA DE ECONOMIA E CREDITO MUTUO DOS MEDICOS LTDA."
        )
        == "Sicoob Credicom"
    )
    assert (
        tela.nome_curto("COOPERATIVA DE CRÉDITO OURO VERDE - SICREDI OURO VERDE MT/PA")
        == "Sicredi Ouro Verde MT/PA"
    )
    assert (
        tela.nome_curto("COOPERATIVA DE CREDITO VALE DO ITAJAI - VIACREDI")
        == "Viacredi"
    )
    assert tela.nome_curto(
        "COOPERATIVA DE CRÉDITO DE LIVRE ADMISSÃO CENTRO BRASILEIRA LTDA."
    ) == ("Cooperativa de Crédito de Livre Admissão Centro Brasileira")


def test_callback_follows_the_state(tmp_path, monkeypatch):
    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = []
    for data in (JUN25, JUN26):
        linhas += _linhas(
            data, "1", "COOPERATIVA X - SICOOB X", "MG", 600, 300, 100, 10
        )
        linhas += _linhas(
            data, "3", "COOPERATIVA DE LIVRE ADMISSAO Z", "MG", 100, 50, 20, 1
        )
        linhas += _linhas(data, "2", "SICREDI Y", "RS", 300, 200, 50, 5)
    armazem.gravar(
        pd.DataFrame(linhas)[ifdata.SCHEMA.names], ifdata.NOME, ifdata.SCHEMA
    )
    http = create_app(Settings(users_file=None)).server.test_client()
    saidas = [
        "coop-contexto.children",
        "coop-sistemas.children",
        "coop-ranking-titulo.children",
        "coop-ranking.children",
    ]
    payload = {
        "output": ".." + "...".join(saidas) + "..",
        "outputs": [
            {"id": s.split(".")[0], "property": s.split(".")[1]} for s in saidas
        ],
        "inputs": [
            {"id": "filtros", "property": "data", "value": {"uf": "MG", "data": ""}}
        ],
        "changedPropIds": [],
    }
    resposta = http.post("/_dash-update-component", json=payload).get_json()["response"]
    texto = json.dumps(resposta, ensure_ascii=False)
    assert (
        resposta["coop-ranking-titulo"]["children"]
        == "Maiores singulares em Minas Gerais"
    )
    assert "Sicoob X" in texto and "Sicredi" not in texto  # RS is filtered out
    assert "1 singular em Minas Gerais" in texto and "1 singular (" in texto
