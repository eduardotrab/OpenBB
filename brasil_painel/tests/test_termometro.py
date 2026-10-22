"""Thermometer: transparent composite score by state."""

import pandas as pd
import pytest

from brasil_painel.dados import termometro as term

CONFIG = {
    "risco": {"rotulo": "Risco", "unidade": "%", "melhor": "menor", "peso": 1},
    "atividade": {"rotulo": "Atividade", "unidade": "%", "melhor": "maior", "peso": 3},
}


def _componentes():
    return pd.DataFrame(
        {"risco": [1.0, 2.0, 3.0], "atividade": [10.0, 10.0, 40.0]},
        index=["A", "B", "C"],
    )


def test_direction_weights_and_contributions_add_up():
    notas, pontos = term.notas(_componentes(), CONFIG)
    # population standard deviation (the 27 states are the whole set):
    # risk [1, 2, 3] → z = ∓1.2247 (lower is better, so A gains); activity [10, 10, 40] → C has z = 1.4142
    assert pontos.loc["A", "risco"] == pytest.approx(10 * 0.25 * 1.2247, rel=1e-3)
    assert pontos.loc["C", "atividade"] == pytest.approx(10 * 0.75 * 1.4142, rel=1e-3)
    assert (notas == 50 + pontos.sum(axis=1)).all()
    assert notas.idxmax() == "C" and notas.idxmin() == "B"


def test_outliers_are_capped_and_weights_can_change():
    df = pd.DataFrame(
        {"risco": [0.0] * 9 + [100.0], "atividade": [1.0] * 10},
        index=list("ABCDEFGHIJ"),
    )
    notas, pontos = term.notas(df, CONFIG)
    assert pontos.loc["J", "risco"] == pytest.approx(-10 * 0.25 * term.LIMITE)
    assert pontos.atividade.abs().sum() == 0  # no spread, no points
    _, so_risco = term.notas(df, CONFIG, pesos={"risco": 1, "atividade": 0})
    assert so_risco.loc["J", "risco"] == pytest.approx(-10 * term.LIMITE)


def test_missing_value_counts_as_average():
    df = _componentes()
    df.loc["B", "atividade"] = float("nan")
    notas, pontos = term.notas(df, CONFIG)
    assert pontos.loc["B", "atividade"] == 0 and notas.notna().all()


def test_components_from_the_store(tmp_path, monkeypatch):
    import datetime as dt

    from brasil_painel.regional import armazem, scr

    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    meses = [dt.date(2025, m, 28) for m in range(5, 13)] + [
        dt.date(2026, m, 28) for m in range(1, 9)
    ]
    linhas = []
    for i, d in enumerate(meses):
        # MG: portfolio grows 10% in 12 months, default 4% → 5%, arrears 1% → 2% in the last 3 months
        carteira = 1000 * (1.10 if d >= dt.date(2026, 8, 1) else 1.0)
        inad = 0.05 if d >= dt.date(2026, 8, 1) else 0.04
        atraso = 0.02 if i >= len(meses) - 1 else 0.01
        linhas.append({"data": d, "uf": "MG", "cooperativa": False, "cliente": "PF", "carteira_ativa": carteira,
                       "carteira_inadimplencia": carteira * inad, "vencido_15_90": carteira * atraso})  # fmt: skip
    armazem.gravar(pd.DataFrame(linhas), scr.NOME, scr.SCHEMA)
    armazem.gravar(armazem.ordenar_longo(pd.DataFrame([{"data": dt.date(2026, 4, 1), "uf": "MG", "indicador": "desemprego", "valor": 4.5}])),
                   "desemprego_uf", armazem.SCHEMA_LONGO)  # fmt: skip
    pix = [{"data": dt.date(a, m, 1), "uf": "MG", "indicador": "pix_recebido_pj", "valor": 1.2 if a == 2026 else 1.0}
           for a in (2025, 2026) for m in (6, 7, 8)]  # fmt: skip
    armazem.gravar(
        armazem.ordenar_longo(pd.DataFrame(pix)), "pix_uf", armazem.SCHEMA_LONGO
    )
    c, fontes = term.componentes()
    mg = c.loc["MG"]
    assert mg.inadimplencia == pytest.approx(
        5
    ) and mg.inadimplencia_12m == pytest.approx(1)
    assert mg.atraso_3m == pytest.approx(1) and mg.carteira == pytest.approx(10)
    assert (
        mg.pix_pj == pytest.approx(20)
        and mg.desemprego == 4.5
        and fontes["pix"] == dt.date(2026, 8, 1)
    )
