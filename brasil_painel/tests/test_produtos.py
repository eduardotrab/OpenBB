"""Product views: credit by product, rates by lender, cards."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import produtos
from brasil_painel.regional import armazem, cartoes, juros, scr

AGO = dt.date(2026, 8, 31)


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    credito = [
        dict(data=AGO, uf="MG", cooperativa=c, cliente="PF", porte="Até 1 salário mínimo", mei=False, produto=p,
             carteira_ativa=v, carteira_inadimplencia=v * 0.1, vencido_15_90=0.0)
        for p, c, v in [("Consignado", False, 300.0), ("Consignado", True, 100.0), ("Cartão de crédito", False, 50.0)]
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(credito), "scr_classe", scr.CLASSE.schema)
    taxas = []
    for inicio, sicoob in ((dt.date(2026, 8, 3), 1.5), (dt.date(2026, 9, 1), 1.2)):
        for pos, (ifs, taxa) in enumerate(
            [("BANCO A", 1.0), ("BANCO SICOOB S.A.", sicoob), ("BANCO C", 2.0)], start=1
        ):
            taxas.append(dict(inicio=inicio, segmento="PESSOA FÍSICA", modalidade="Cheque especial - Prefixado",
                              instituicao=ifs, posicao=pos, taxa_mes=taxa, taxa_ano=taxa * 12))  # fmt: skip
    armazem.gravar(pd.DataFrame(taxas), "juros_if", juros.SCHEMA)
    cards = [
        dict(data=dt.date(2026, 6, 1), funcao="Crédito", bandeira="Visa", emitidos=100.0, ativos=40.0, transacoes=1.0, valor=1.0),
        dict(data=dt.date(2026, 6, 1), funcao="Crédito", bandeira="Elo", emitidos=100.0, ativos=60.0, transacoes=1.0, valor=1.0),
        dict(data=dt.date(2026, 6, 1), funcao="Débito", bandeira="Elo", emitidos=50.0, ativos=10.0, transacoes=1.0, valor=1.0),
    ]  # fmt: skip
    armazem.gravar(pd.DataFrame(cards), "cartoes", cartoes.SCHEMA)


def test_credit_by_product_largest_first(loja):
    resumos = produtos.por_produto()
    assert [r.classe for r in resumos] == ["Consignado", "Cartão de crédito"]
    assert resumos[0].share_coop == pytest.approx(25.0)


def test_rates_highlight_sicoob_against_the_median(loja):
    j = produtos.juros("PESSOA FÍSICA", "Cheque especial - Prefixado")
    assert j.inicio == dt.date(2026, 9, 1)
    assert (j.sicoob_posicao, j.sicoob_taxa, j.mediana) == (2, 1.2, 1.2)
    assert j.serie[0] == (dt.date(2026, 8, 3), 1.5, 1.5)
    assert produtos.modalidades()[0] == ("PESSOA FÍSICA", "Cheque especial - Prefixado")


def test_cards_activation_and_brands(loja):
    c = produtos.cartoes()
    assert c.funcoes[0] == ("Crédito", 200.0, 100.0, 50.0)
    assert c.bandeiras[0] == ("Elo", 60.0)
    assert c.serie_ativacao == [(dt.date(2026, 6, 1), 50.0)]
