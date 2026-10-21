"""Opportunities screen: niche labels and the main callback."""

import json

import pandas as pd

from brasil_painel.paginas import oportunidades as tela
from tests.test_oportunidades import _df, _linhas


def _dados():
    return pd.concat([
        _df(_linhas("SP", False, 700, inad=35), _linhas("SP", True, 300, inad=15)),
        _df(_linhas("MG", False, lambda i: 950 + i * 10, inad=19), _linhas("MG", True, 50, inad=1)),
        _df(_linhas("RS", False, 1000, venc=lambda i: 10 if i < 10 else 40), _linhas("RS", True, 100, venc=lambda i: 1 if i < 10 else 9)),
    ], ignore_index=True)  # fmt: skip


def test_niche_label_uses_state_name_and_commas():
    assert tela.rotulo(
        {"uf": "SP", "classe": "Pequena", "produto": "Capital de giro"},
        ("uf", "classe", "produto"),
    ) == ("São Paulo, Pequena, Capital de giro")


def _post(http, saidas, entradas, estado=()):
    payload = {
        "output": ".." + "...".join(saidas) + "..",
        "outputs": [
            {"id": s.split(".")[0], "property": s.split(".")[1]} for s in saidas
        ],
        "inputs": entradas,
        "state": list(estado),
        "changedPropIds": [],
    }
    return http.post("/_dash-update-component", json=payload).get_json()["response"]


def test_lists_callback_renders_room_alerts_and_picks_a_niche(monkeypatch):
    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    monkeypatch.setattr(tela, "_base", lambda grupo: _dados())
    monkeypatch.setattr(tela.op, "MINIMO_MERCADO", 0)
    monkeypatch.setattr(tela.op, "MINIMO_COOP", 0)
    http = create_app(Settings(users_file=None)).server.test_client()
    resposta = _post(
        http,
        [
            "op-espaco.children",
            "op-alertas.children",
            "op-contexto.children",
            "op-nicho.data",
        ],
        [
            {"id": "op-detalhe", "property": "value", "value": "uf"},
            {"id": "op-grupo", "property": "value", "value": "todos"},
            {"id": "op-sinal", "property": "value", "value": "cooperativas"},
            {"id": "filtros", "property": "data", "value": {"uf": "BR", "data": ""}},
        ],
    )
    texto = json.dumps(resposta, ensure_ascii=False)
    assert (
        "Minas Gerais" in texto
        and "Rio Grande do Sul" in texto
        and "Espaço somado" in texto
    )
    assert resposta["op-nicho"]["data"] == {"detalhe": "uf", "chave": "RS"}

    graficos = _post(
        http,
        ["op-nicho-titulo.children", "op-nicho-graficos.children"],
        [
            {
                "id": "op-nicho",
                "property": "data",
                "value": {"detalhe": "uf", "chave": "RS"},
            }
        ],
        [{"id": "op-grupo", "property": "value", "value": "todos"}],
    )
    assert graficos["op-nicho-titulo"]["children"] == "Rio Grande do Sul no tempo"
    assert "Atraso de 15 a 90 dias" in json.dumps(graficos, ensure_ascii=False)
