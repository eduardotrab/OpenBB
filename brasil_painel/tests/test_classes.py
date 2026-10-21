"""Client classes and the product rule."""

import duckdb
import pytest

from brasil_painel.regional import classes

# Every (modality, submodality) seen in SCR.data 2026-08, with the expected product.
VISTAS = [
    (
        "Adiantamentos a depositantes",
        "Adiantamentos a depositantes",
        "Cheque especial e conta garantida",
    ),
    (
        "Direitos creditórios descontados",
        "Desconto de duplicatas",
        "Desconto de recebíveis",
    ),
    (
        "Direitos creditórios descontados",
        "Antecipação de fatura de cartão de crédito",
        "Cartão de crédito",
    ),
    (
        "Empréstimos",
        "Crédito pessoal - com consignação em folha de pagam.",
        "Consignado",
    ),
    (
        "Empréstimos",
        "Capital de giro com prazo de vencimento superior a 365 dias",
        "Capital de giro",
    ),
    (
        "Empréstimos",
        "Crédito pessoal - sem consignação em folha de pagam.",
        "Crédito pessoal",
    ),
    ("Empréstimos", "Outros empréstimos", "Outros"),
    ("Empréstimos", "Cartão de crédito - não migrado", "Cartão de crédito"),
    ("Empréstimos", "Cheque especial", "Cheque especial e conta garantida"),
    ("Empréstimos", "Conta Garantida", "Cheque especial e conta garantida"),
    ("Empréstimos", "Home Equity", "Imobiliário"),
    (
        "Empréstimos",
        "Crédito rotativo vinculado a cartão de crédito",
        "Cartão de crédito",
    ),
    ("Empréstimos", "Microcrédito", "Crédito pessoal"),
    ("Empréstimos", "Vendor", "Desconto de recebíveis"),
    ("Financiamentos", "Aquisição de bens - veículos automotores", "Veículos"),
    ("Financiamentos", "Financiamento de projeto", "Infraestrutura e projetos"),
    ("Financiamentos", "Aquisição de bens - outros bens", "Outros"),
    ("Financiamentos", "Financiamentos agroindustriais", "Rural e agroindustrial"),
    (
        "Financiamentos com interveniência",
        "Aquisição de bens com interveniência - veículos autom.",
        "Veículos",
    ),
    (
        "Financiamentos de infraestrutura e desenvolvimento",
        "Financiamento de infraestrutura e desenvolvimento",
        "Infraestrutura e projetos",
    ),
    ("Financiamentos imobiliários", "Financiamento habitacional - SFH", "Imobiliário"),
    ("Financiamentos imobiliários", "Financiamento de projeto", "Imobiliário"),
    (
        "Financiamentos rurais  (ex-financiamentos rurais e agroindustriais)",
        "Custeio",
        "Rural e agroindustrial",
    ),
    (
        "Financiamentos à exportação",
        "Adiantamento sobre contratos de câmbio",
        "Comércio exterior",
    ),
    ("Financiamentos à importação", "Financiamento à importação", "Comércio exterior"),
    (
        "Operações de arrendamento",
        "Arrendamento financeiro de veículos automotores",
        "Veículos",
    ),
    ("Operações de arrendamento", "Arrendamento financeiro imobiliário", "Imobiliário"),
    (
        "Outros créditos",
        "Cartão de crédito - compra à vista e parcelado lojista ",
        "Cartão de crédito",
    ),
    ("Outros créditos", "Recebíveis adquiridos", "Desconto de recebíveis"),
    ("Outros créditos", "Avais e fianças honrados", "Outros"),
]


def test_product_rule_over_every_seen_submodality():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t (modalidade VARCHAR, submodalidade VARCHAR, esperado VARCHAR)"
    )
    con.executemany("INSERT INTO t VALUES (?, ?, ?)", VISTAS)
    errados = con.execute(  # the CASE is a code constant, not user input
        f"SELECT modalidade, submodalidade, esperado, {classes.sql_produto()} AS produto FROM t WHERE produto <> esperado"  # noqa: S608
    ).fetchall()
    assert errados == []


@pytest.mark.parametrize(
    ("porte", "classe"),
    [
        ("Até 1 salário mínimo", "Varejo"),
        ("Mais de 2 a 3 salários mínimos", "Varejo"),
        ("Mais de 3 a 5 salários mínimos", "Renda média"),
        ("Mais de 10 a 20 salários mínimos", "Média alta"),
        ("Acima de 20 salários mínimos", "Alta renda"),
        ("Sem rendimento", "Não informada"),
        ("algo novo", "Não informada"),
    ],
)
def test_income_classes(porte, classe):
    assert classes.classe_pf(porte) == classe


def test_company_and_producer_classes():
    assert classes.classe_pj("Pequeno") == "Pequena"
    assert classes.classe_pj("Pequeno", mei=True) == "MEI"
    assert classes.classe_rural("0001") == "Pequeno produtor"
    assert classes.classe_rural("0050") == "Médio produtor"
    assert classes.classe_rural("0999") == "Grande produtor"
    assert classes.classe_rural("0070") == "Grande produtor"  # Funcafé


def test_display_order_follows_the_file():
    assert classes.ordem("pf")[:4] == [
        "Varejo",
        "Renda média",
        "Média alta",
        "Alta renda",
    ]
    assert classes.ordem("pj")[0] == "MEI"
