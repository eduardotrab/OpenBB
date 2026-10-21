"""FinScope components: structure and Brazilian formatting."""

import datetime as dt

import pytest

from brasil_painel.componentes import fs
from brasil_painel.dados import formato


def _texto(c) -> str:
    filhos = getattr(c, "children", c)
    if isinstance(filhos, list | tuple):
        return " ".join(_texto(f) for f in filhos if f is not None)
    if isinstance(filhos, str):
        return filhos
    return _texto(filhos) if filhos is not None else ""


def _procurar(c, classe: str):
    """Every component whose className contains `classe`."""
    achados = [c] if classe in (getattr(c, "className", "") or "").split() else []
    filhos = getattr(c, "children", None)
    if not isinstance(filhos, list | tuple):
        filhos = [filhos]
    for f in filhos:
        if f is not None and not isinstance(f, str):
            achados += _procurar(f, classe)
    return achados


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (4_900_000, "4,9 mi"),
        (634_500, "634,5 mil"),
        (1_452, "1.452"),
        (7.72e12, "7,7 tri"),
        (536.3e9, "536,3 bi"),
    ],
)
def test_compact_numbers(valor, esperado):
    assert formato.compacto(valor) == esperado


def test_kpi_carries_value_for_count_up():
    kpi = fs.kpi(
        "Share das cooperativas",
        6.94,
        unidade="%",
        casas=1,
        variacao=0.4,
        comparacao="em 12 meses",
    )
    numero = _procurar(kpi, "fs-numero")[0]
    assert numero.children == "6,9"
    props = numero.to_plotly_json()["props"]
    assert (props["data-valor"], props["data-casas"]) == (6.94, 1)
    assert "▲ +0,4 em 12 meses" in _texto(kpi)


def test_funnel_bars_are_relative_to_the_first_stage():
    funil = fs.funil(
        [("Carteira total", 1000.0), ("Em dia", 950.0), ("Inadimplente", 50.0)]
    )
    barras = _procurar(funil, "fs-funil-barra")
    assert [b.style["width"] for b in barras] == ["100.0%", "95.0%", "5.0%"]
    assert "50 (5,0%)" in _texto(funil)


def test_comparative_bars_scale_to_the_largest():
    barras = fs.barras_comparativas(
        [("Cooperativas", 536.3e9, "coop"), ("Sistema", 7.72e12, "sistema")],
        prefixo="R$ ",
    )
    larguras = [b.style["width"] for b in _procurar(barras, "fs-barra")]
    assert larguras[1] == "100.0%" and float(larguras[0][:-1]) == pytest.approx(
        6.9, abs=0.1
    )
    assert "R$ 536,3 bi" in _texto(barras)


def test_class_column_and_date_seal():
    coluna = fs.coluna_classe(
        "Varejo", [fs.selo_datas(dt.date(2026, 10, 20), dt.date(2026, 8, 31))]
    )
    assert "fs-coluna" in coluna.className
    assert "Varejo" in _texto(coluna)
    assert "Data-base: ago/2026" in _texto(
        coluna
    ) and "Atualizado em 20/10/2026" in _texto(coluna)


def test_skeleton_has_requested_lines():
    assert len(_procurar(fs.esqueleto(4), "fs-esqueleto-linha")) == 4
