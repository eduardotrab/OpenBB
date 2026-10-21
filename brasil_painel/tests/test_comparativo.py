"""Comparison of every class against the Brazil total."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import comparativo
from brasil_painel.regional import armazem, scr, sicor

AGO = dt.date(2026, 8, 31)


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))

    def linha(cliente, porte, valor, mei=False):
        return dict(data=AGO, uf="MG", cooperativa=False, cliente=cliente, porte=porte, mei=mei,
                    produto="Outros", carteira_ativa=valor, carteira_inadimplencia=valor / 10, vencido_15_90=0.0)  # fmt: skip

    linhas = [
        linha("PF", "Até 1 salário mínimo", 100.0),
        linha("PF", "Mais de 3 a 5 salários mínimos", 50.0, mei=True),
        linha("PJ", "Grande", 1000.0),
    ]
    armazem.gravar(pd.DataFrame(linhas), "scr_classe", scr.CLASSE.schema)
    rural = [
        dict(data=dt.date(2026, 8, 1), uf="MG", porte=p, atividade="Agrícola", cooperativa=c, sicoob=False,
             valor_custeio=v, valor_investimento=0.0, valor_comercializacao=0.0, valor_industrializacao=0.0,
             contratos=1.0)
        for p, c, v in [("Pequeno produtor", True, 10.0), ("Grande produtor", False, 30.0)]
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(rural), "sicor_uf", sicor.SCHEMA)


def test_brazil_row_counts_mei_only_once(loja):
    linhas = comparativo.tabela()
    brasil = linhas[0]
    assert brasil.grupo == "Brasil"
    assert brasil.resumo.carteira == pytest.approx(1150.0)
    pf = sum(linha.resumo.carteira for linha in linhas if linha.grupo == "Pessoas")
    pj_sem_mei = sum(
        linha.resumo.carteira
        for linha in linhas
        if linha.grupo == "Empresas" and linha.resumo.classe != "MEI"
    )
    assert pf + pj_sem_mei == pytest.approx(brasil.resumo.carteira)
    assert [linha.resumo.classe for linha in linhas if linha.grupo == "Empresas"][
        0
    ] == "MEI"


def test_rural_block_starts_with_the_total(loja):
    rurais = comparativo.rurais()
    assert rurais[0].classe == "Brasil" and rurais[0].valor == pytest.approx(40.0)
    assert rurais[0].share_coop == pytest.approx(25.0)
    assert [r.classe for r in rurais[1:]] == [
        "Pequeno produtor",
        "Médio produtor",
        "Grande produtor",
    ]
