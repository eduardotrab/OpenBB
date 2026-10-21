"""Highlights: largest movers in 12 months."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import classes, comparativo, destaques, regional
from brasil_painel.regional import armazem, scr

AGO, AGO_ANTES = dt.date(2026, 8, 31), dt.date(2025, 8, 31)


def _resumo(classe, tendencia):
    return classes.ResumoClasse(
        classe, AGO, carteira=1.0, inadimplencia=tendencia[-1][1], tendencia=tendencia
    )


def test_classes_ranked_by_rise_in_default_rate():
    linhas = [
        comparativo.Linha(
            "Brasil", _resumo("Brasil", [(AGO_ANTES, 4.0, None), (AGO, 5.0, None)])
        ),
        comparativo.Linha(
            "Pessoas", _resumo("Varejo", [(AGO_ANTES, 6.0, None), (AGO, 7.6, None)])
        ),
        comparativo.Linha(
            "Empresas", _resumo("Micro", [(AGO_ANTES, 6.0, None), (AGO, 8.0, None)])
        ),
        comparativo.Linha(
            "Pessoas", _resumo("Alta renda", [(AGO_ANTES, 6.5, None), (AGO, 6.1, None)])
        ),
    ]
    itens = destaques.classes_que_pioraram(linhas)
    assert [i.rotulo for i in itens] == ["Empresas: Micro", "Pessoas: Varejo"]
    assert itens[0].variacao == pytest.approx(2.0) and itens[0].href == "/empresas"


def test_states_ranked_by_rise_and_brazil_excluded():
    foto = regional.Retrato(
        AGO,
        {"MA": 9.6, "MG": 4.9, "SP": 4.0},
        5.0,
        {"MA": 3.1, "MG": 0.9, "SP": -0.2, "BR": 0.9},
    )
    assert [i.rotulo for i in destaques.ufs_que_pioraram(foto)] == [
        "Maranhão",
        "Minas Gerais",
    ]


def test_products_by_growth(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = [
        dict(data=d, uf="MG", cooperativa=False, cliente="PF", porte="Até 1 salário mínimo", mei=False, produto=p,
             carteira_ativa=v, carteira_inadimplencia=0.0, vencido_15_90=0.0)
        for d, p, v in [(AGO_ANTES, "Consignado", 100.0), (AGO, "Consignado", 130.0),
                        (AGO_ANTES, "Veículos", 100.0), (AGO, "Veículos", 90.0),
                        (AGO_ANTES, "Imobiliário", 100.0), (AGO, "Imobiliário", 105.0)]
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(linhas), "scr_classe", scr.CLASSE.schema)
    alta, baixa = destaques.produtos_por_crescimento(n=2)
    assert [i.rotulo for i in alta] == ["Consignado", "Imobiliário"]
    assert [i.rotulo for i in baixa] == ["Veículos", "Imobiliário"]
    assert alta[0].variacao == pytest.approx(30.0)


def test_opening_credit_strip_and_highlights_callback(tmp_path, monkeypatch):
    import json

    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = [
        dict(data=d, uf=uf, cooperativa=False, cliente="PF", porte="Até 1 salário mínimo", mei=False,
             produto="Consignado", carteira_ativa=v, carteira_inadimplencia=v * i, vencido_15_90=0.0)
        for d, i in ((AGO_ANTES, 0.04), (AGO, 0.06)) for uf, v in (("MG", 100.0), ("SP", 300.0))
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(linhas), "scr_classe", scr.CLASSE.schema)
    uf_linhas = (
        pd.DataFrame(linhas)
        .groupby(["data", "uf", "cooperativa", "cliente"], as_index=False)[
            ["carteira_ativa", "carteira_inadimplencia", "vencido_15_90"]
        ]
        .sum()
    )
    armazem.gravar(uf_linhas, "scr_uf", scr.SCHEMA)
    pix = pd.DataFrame(
        [dict(data=dt.date(2026, 9, 1), uf="BR", indicador="pix_pago_pf", valor=1.2e12)]
    )
    armazem.gravar(pix, "pix_uf", armazem.SCHEMA_LONGO)
    http = create_app(Settings(users_file=None)).server.test_client()
    payload = {
        "output": "..abertura-credito.children...abertura-destaques.children..",
        "outputs": [
            {"id": "abertura-credito", "property": "children"},
            {"id": "abertura-destaques", "property": "children"},
        ],
        "inputs": [
            {"id": "filtros", "property": "data", "value": {"uf": "BR", "data": ""}}
        ],
        "changedPropIds": [],
    }
    texto = json.dumps(
        http.post("/_dash-update-component", json=payload).get_json(),
        ensure_ascii=False,
    )
    assert "Pix pago no mês" in texto and "set/2026" in texto
    assert "Pessoas: Varejo" in texto and "São Paulo" in texto
