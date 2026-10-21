"""Segment screens: filters, the 12-month change and the callback."""

import datetime as dt
import json

import pandas as pd
import pytest

from brasil_painel.app import create_app
from brasil_painel.config import Settings
from brasil_painel.paginas import segmento
from brasil_painel.regional import armazem, scr


def test_global_filters_become_data_filters():
    assert segmento.filtros_da_tela({"uf": "BR", "data": ""}) == {
        "uf": None,
        "data": None,
    }
    assert segmento.filtros_da_tela({"uf": "MG", "data": "2026-08-31"}) == {
        "uf": "MG",
        "data": dt.date(2026, 8, 31),
    }


def test_twelve_month_change_of_a_trend():
    tendencia = [
        (dt.date(2025, 8, 31), 4.0, 3.0),
        (dt.date(2026, 2, 28), 4.5, 3.5),
        (dt.date(2026, 8, 31), 5.0, 4.0),
    ]
    assert segmento._variacao_12m(tendencia) == pytest.approx(1.0)
    assert segmento._variacao_12m(tendencia[1:]) is None


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = [
        dict(data=dt.date(2026, 8, 31), uf="MG", cooperativa=coop, cliente="PF", porte=porte, mei=False,
             produto="Cartão de crédito", carteira_ativa=v, carteira_inadimplencia=v * 0.05, vencido_15_90=v * 0.01)
        for porte, coop, v in [("Até 1 salário mínimo", True, 100.0), ("Até 1 salário mínimo", False, 900.0),
                               ("Acima de 20 salários mínimos", False, 2000.0), ("Indisponível", False, 50.0)]
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(linhas), "scr_classe", scr.CLASSE.schema)


def test_people_callback_returns_one_column_per_income_class(loja):
    http = create_app(Settings(users_file=None)).server.test_client()
    payload = {
        "output": "..pessoas-colunas.children...pessoas-contexto.children...pessoas-resto.children..",
        "outputs": [
            {"id": "pessoas-colunas", "property": "children"},
            {"id": "pessoas-contexto", "property": "children"},
            {"id": "pessoas-resto", "property": "children"},
        ],
        "inputs": [
            {"id": "pessoas-produto", "property": "value", "value": ""},
            {"id": "filtros", "property": "data", "value": {"uf": "BR", "data": ""}},
        ],
        "changedPropIds": [],
    }
    resposta = http.post("/_dash-update-component", json=payload).get_json()["response"]
    colunas = resposta["pessoas-colunas"]["children"]
    assert len(colunas) == 4
    texto = json.dumps(resposta, ensure_ascii=False)
    assert "Varejo" in texto and "Alta renda" in texto
    assert "Sem carteira com estes filtros." in texto  # Renda média has no rows
    assert "sem faixa/porte informado" in texto
    assert "ago/2026" in json.dumps(resposta["pessoas-contexto"], ensure_ascii=False)


def test_rural_callback_has_three_producer_columns(tmp_path, monkeypatch):
    from brasil_painel.regional import sicor

    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = [
        dict(data=dt.date(2026, 8, 1), uf="MG", porte=porte, atividade="Agrícola", cooperativa=True, sicoob=True,
             valor_custeio=100.0, valor_investimento=50.0, valor_comercializacao=0.0, valor_industrializacao=0.0,
             contratos=3.0)
        for porte in ("Pequeno produtor", "Grande produtor")
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(linhas), "sicor_uf", sicor.SCHEMA)
    http = create_app(Settings(users_file=None)).server.test_client()
    payload = {
        "output": "..rural-colunas.children...rural-contexto.children..",
        "outputs": [
            {"id": "rural-colunas", "property": "children"},
            {"id": "rural-contexto", "property": "children"},
        ],
        "inputs": [
            {
                "id": "filtros",
                "property": "data",
                "value": {"uf": "BR", "data": "2026-08-31"},
            }
        ],
        "changedPropIds": [],
    }
    resposta = http.post("/_dash-update-component", json=payload).get_json()["response"]
    assert len(resposta["rural-colunas"]["children"]) == 3
    texto = json.dumps(resposta, ensure_ascii=False)
    assert "Sem contratos com estes filtros." in texto  # medium producer has no rows
    assert "Contratado em ago/2026" in texto
