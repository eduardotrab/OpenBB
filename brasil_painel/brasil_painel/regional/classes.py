"""Client classes (income, size, producer) and credit products (plan 10).

Classes come from `classes.toml`; products are a rule over the SCR.data
modality/submodality, expressed in SQL so DuckDB applies it while reading.
"""

import functools
from pathlib import Path

import tomllib

ARQUIVO = Path(__file__).with_name("classes.toml")
NAO_INFORMADO = {"pf": "Não informada", "pj": "Não informado"}

# (product, SQL condition) in priority order; the first match wins.
PRODUTOS = [
    (
        "Cartão de crédito",
        "submodalidade ILIKE 'Cartão de crédito%' OR submodalidade ILIKE '%vinculado a cartão%'"
        " OR submodalidade ILIKE 'Antecipação de fatura de cartão%'",
    ),
    ("Consignado", "submodalidade ILIKE 'Crédito pessoal - com consignação%'"),
    (
        "Crédito pessoal",
        "submodalidade ILIKE 'Crédito pessoal - sem consignação%' OR submodalidade = 'Microcrédito'",
    ),
    (
        "Cheque especial e conta garantida",
        "submodalidade IN ('Cheque especial', 'Conta Garantida', 'Adiantamentos a depositantes')",
    ),
    ("Capital de giro", "submodalidade ILIKE 'Capital de giro%'"),
    ("Veículos", "submodalidade ILIKE '%veículos autom%'"),
    (
        "Imobiliário",
        "modalidade = 'Financiamentos imobiliários' OR submodalidade IN"
        " ('Home Equity', 'Arrendamento financeiro imobiliário')",
    ),
    (
        "Rural e agroindustrial",
        "modalidade ILIKE 'Financiamentos rurais%' OR submodalidade = 'Financiamentos agroindustriais'",
    ),
    (
        "Desconto de recebíveis",
        "modalidade = 'Direitos creditórios descontados' OR submodalidade IN"
        " ('Recebíveis adquiridos', 'Vendor', 'Compror')",
    ),
    (
        "Comércio exterior",
        "modalidade ILIKE 'Financiamentos à exportação%' OR modalidade ILIKE 'Financiamentos à importação%'",
    ),
    (
        "Infraestrutura e projetos",
        "modalidade = 'Financiamentos de infraestrutura e desenvolvimento'"
        " OR submodalidade = 'Financiamento de projeto'",
    ),
]
OUTROS = "Outros"


def sql_produto() -> str:
    """CASE expression mapping a SCR.data row to its product."""
    ramos = "\n".join(f"  WHEN {condicao} THEN '{nome}'" for nome, condicao in PRODUTOS)
    return f"CASE\n{ramos}\n  ELSE '{OUTROS}'\nEND"


@functools.cache
def configuracao() -> dict:
    """Read `classes.toml` (cached)."""
    return tomllib.loads(ARQUIVO.read_text(encoding="utf-8"))


def _inverso(grupo: str) -> dict[str, str]:
    return {
        rotulo: classe
        for classe, rotulos in configuracao()[grupo].items()
        for rotulo in rotulos
    }


def classe_pf(porte: str) -> str:
    """Income class of an individual (SCR.data `porte`)."""
    return _inverso("pf").get(porte, NAO_INFORMADO["pf"])


def classe_pj(porte: str, mei: bool = False) -> str:
    """Size class of a company; individuals with MEI occupation count as "MEI"."""
    if mei:
        return "MEI"
    return _inverso("pj").get(porte, NAO_INFORMADO["pj"])


def classe_rural(programa: str) -> str:
    """Return the producer size from the SICOR program code (Pronaf, Pronamp, others)."""
    for classe, codigos in configuracao()["rural"].items():
        if programa in codigos:
            return classe
    return next(c for c, codigos in configuracao()["rural"].items() if not codigos)


def ordem(grupo: str) -> list[str]:
    """Classes of a group in display order (as written in the TOML)."""
    return list(configuracao()[grupo])


def principais(grupo: str) -> list[str]:
    """Classes shown as columns (the "not informed" class is shown apart)."""
    return [c for c in ordem(grupo) if c != NAO_INFORMADO.get(grupo)]


def descricao(classe: str) -> str:
    """Short subtitle of a class column (empty when not configured)."""
    return configuracao().get("descricoes", {}).get(classe, "")
