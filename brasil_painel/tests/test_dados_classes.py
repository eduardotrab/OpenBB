"""Class summaries in the format of the segment models."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import classes as resumo
from brasil_painel.regional import armazem, scr, sicor

AGO, AGO_ANTES = dt.date(2026, 8, 31), dt.date(2025, 8, 31)


def _linha(
    data, uf, coop, cliente, porte, produto, ativa, *, inad=0.0, venc=0.0, mei=False
):
    return dict(data=data, uf=uf, cooperativa=coop, cliente=cliente, porte=porte, mei=mei, produto=produto,
                carteira_ativa=ativa, carteira_inadimplencia=inad, vencido_15_90=venc)  # fmt: skip


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    varejo, alta = "Até 1 salário mínimo", "Acima de 20 salários mínimos"
    linhas = []
    for data, f in ((AGO_ANTES, 1.0), (AGO, 1.1)):
        linhas += [
            _linha(
                data,
                "MG",
                True,
                "PF",
                varejo,
                "Cartão de crédito",
                100 * f,
                inad=10,
                venc=5,
            ),
            _linha(
                data, "MG", False, "PF", varejo, "Consignado", 900 * f, inad=30, venc=10
            ),
            _linha(data, "SP", False, "PF", alta, "Imobiliário", 2000 * f, inad=20),
            _linha(
                data,
                "SP",
                False,
                "PJ",
                "Pequeno",
                "Capital de giro",
                500 * f,
                inad=5,
                venc=5,
            ),
            _linha(data, "MG", True, "PF", varejo, "Outros", 50 * f, mei=True),
        ]
    armazem.gravar(pd.DataFrame(linhas), "scr_classe", scr.CLASSE.schema)
    rural = pd.DataFrame(
        [
            dict(data=dt.date(2026, 8, 1), uf="MG", porte="Pequeno produtor", atividade="Agrícola", cooperativa=True,
                 sicoob=True, valor_custeio=60.0, valor_investimento=40.0, valor_comercializacao=0.0,
                 valor_industrializacao=0.0, contratos=4.0),
            dict(data=dt.date(2026, 8, 1), uf="MG", porte="Pequeno produtor", atividade="Agrícola", cooperativa=False,
                 sicoob=False, valor_custeio=100.0, valor_investimento=0.0, valor_comercializacao=0.0,
                 valor_industrializacao=0.0, contratos=1.0),
        ]
    )  # fmt: skip
    armazem.gravar(rural, "sicor_uf", sicor.SCHEMA)
    return tmp_path


def test_income_class_summary(loja):
    r = resumo.resumir("pf", "Varejo")
    assert r.data == AGO
    assert r.carteira == pytest.approx(1050 * 1.1)
    assert r.carteira_coop == pytest.approx(150 * 1.1)
    assert r.share_coop == pytest.approx(150 / 1050 * 100)
    assert r.inadimplencia == pytest.approx(40 / (1050 * 1.1) * 100)
    assert r.crescimento_12m == pytest.approx(10.0)
    assert r.peso_cartao == pytest.approx(100 / 1050 * 100)
    rotulos = [e for e, _ in r.funil]
    assert rotulos == ["Carteira", "Em dia", "Atraso 15–90 dias", "Inadimplente"]
    assert dict(r.funil)["Em dia"] == pytest.approx(1050 * 1.1 - 40 - 15)


def test_filters_by_uf_and_product(loja):
    assert resumo.resumir("pf", "Varejo", uf="SP").carteira == 0
    r = resumo.resumir("pf", "Varejo", produto="Cartão de crédito")
    assert r.carteira == pytest.approx(110.0)


def test_company_classes_include_mei_from_individuals(loja):
    assert resumo.resumir("pj", "MEI").carteira == pytest.approx(55.0)
    assert resumo.resumir("pj", "Pequena").carteira == pytest.approx(550.0)


def test_all_classes_sum_to_the_group_total(loja):
    todas = resumo.todas("pf")
    assert [r.classe for r in todas][:4] == [
        "Varejo",
        "Renda média",
        "Média alta",
        "Alta renda",
    ]
    assert sum(r.carteira for r in todas) == pytest.approx((1050 + 2000) * 1.1)


def test_trend_series_per_month(loja):
    serie = resumo.resumir("pf", "Varejo").tendencia
    assert [p[0] for p in serie] == [AGO_ANTES, AGO]
    assert serie[0][1] == pytest.approx(40 / 1050 * 100)  # system
    assert serie[0][2] == pytest.approx(10 / 150 * 100)  # cooperatives


def test_rural_summary_is_contracted_flow(loja):
    r = resumo.resumir_rural("Pequeno produtor")
    assert r.valor == pytest.approx(200.0)
    assert r.contratos == 5
    assert r.share_coop == pytest.approx(50.0)
    assert r.share_sicoob == pytest.approx(50.0)
    assert r.ticket_medio == pytest.approx(40.0)
    assert dict(r.finalidades)["Custeio"] == pytest.approx(160.0)
