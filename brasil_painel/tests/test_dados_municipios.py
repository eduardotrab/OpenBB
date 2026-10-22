"""Municipal table of one state: per-capita figures, growth and the state median."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import municipios as mun
from brasil_painel.regional import armazem

BH, UBERLANDIA = "3106200", "3170206"


def _linhas(registros):
    return armazem.ordenar_municipal(
        pd.DataFrame(
            registros, columns=["data", "municipio", "uf", "indicador", "valor"]
        )
    )


def _mes(ano, mes):
    return dt.date(ano, mes, 1)


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    ibge = [
        (_mes(2026, 1), BH, "MG", "populacao", 2_000_000.0),
        (_mes(2026, 1), UBERLANDIA, "MG", "populacao", 1_000_000.0),
        (_mes(2023, 1), BH, "MG", "pib", 100e9),
        (_mes(2023, 1), UBERLANDIA, "MG", "pib", 40e9),
    ]
    pix = []
    for m in [
        _mes(2025, 7),
        _mes(2025, 8),
        _mes(2025, 9),
        _mes(2026, 7),
        _mes(2026, 8),
        _mes(2026, 9),
    ]:
        cresce = 1.2 if m.year == 2026 else 1.0
        pix += [
            (m, BH, "MG", "pix_recebido_pj", 1e9 * cresce),
            (m, BH, "MG", "pix_recebido_pf", 2e9),
            (m, UBERLANDIA, "MG", "pix_recebido_pj", 5e8),
            (m, UBERLANDIA, "MG", "pix_recebido_pf", 1e9),
        ]
    estban = [
        (_mes(2026, 6), BH, "MG", "credito", 50e9),
        (_mes(2026, 6), BH, "MG", "credito_sicoob", 5e9),
        (_mes(2025, 6), BH, "MG", "credito", 40e9),
        (_mes(2026, 6), BH, "MG", "poupanca", 20e9),
    ]
    rural = [
        (_mes(2026, 8), UBERLANDIA, "MG", "custeio_pequeno", 30e6),
        (_mes(2026, 8), UBERLANDIA, "MG", "custeio_grande", 70e6),
        (_mes(2025, 7), UBERLANDIA, "MG", "custeio_grande", 999e6),
    ]  # outside the 12-month window
    for nome, linhas in (
        ("ibge_municipio", ibge),
        ("pix_municipio", pix),
        ("estban_municipio", estban),
        ("sicor_municipio", rural),
    ):
        armazem.gravar(_linhas(linhas), nome, armazem.SCHEMA_MUNICIPAL)
    return tmp_path  # fmt: skip


def test_state_table(loja):
    t, datas = mun.tabela("MG")
    assert len(t) > 800 and t.loc[BH, "nome"] == "Belo Horizonte"
    bh, udi = t.loc[BH], t.loc[UBERLANDIA]
    assert bh.pix_pj_pc == pytest.approx(
        1.2e9 / 2e6
    ) and bh.pix_pj_cresc == pytest.approx(20)
    assert bh.pib_pc == pytest.approx(50) and bh.credito_pc == pytest.approx(25)
    assert bh.credito_cresc == pytest.approx(25)
    assert udi.rural_12m == pytest.approx(100) and udi.rural_pequeno == pytest.approx(
        30
    )
    assert pd.isna(udi.credito_pc) and datas["estban"] == _mes(2026, 6)


def test_median_and_rank(loja):
    t, _ = mun.tabela("MG")
    assert mun.mediana(t, "pix_pf_pc") == pytest.approx(1000)
    assert (
        mun.posicao(t, "pib_pc", BH) == (1, 2)
        and mun.posicao(t, "credito_pc", UBERLANDIA) is None
    )


def test_missing_dataset(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    with pytest.raises(mun.DadosAusentes):
        mun.tabela("MG")


def test_optional_datasets_may_be_missing(loja):
    (loja / "sicor_municipio.parquet").unlink()
    t, datas = mun.tabela("MG")
    assert (
        "sicor" not in datas and t.rural_12m.isna().all() and t.loc[BH, "pix_pj_pc"] > 0
    )
