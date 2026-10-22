"""Cooperative systems: classification, share, growth and return on equity."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import cooperativas as coop

JUN25, JUN26 = dt.date(2025, 6, 30), dt.date(2026, 6, 30)


def _linhas(data, cnpj, nome, uf, ativo, carteira, pl, lucro, *, segmento="B3S"):
    contas = {"Ativo Total": ativo, "Carteira de Crédito": carteira, "Captações": carteira * 1.25,
              "Patrimônio Líquido": pl, "Lucro Líquido": lucro}  # fmt: skip
    return [
        {"data": data, "instituicao": cnpj, "nome": nome, "uf": uf, "municipio": "X", "segmento": segmento,
         "conta": conta, "valor": valor}
        for conta, valor in contas.items()
    ]  # fmt: skip


@pytest.fixture
def dados():
    linhas = []
    for data, fator in ((JUN25, 1.0), (JUN26, 1.2)):
        linhas += _linhas(
            data, "1", "COOPERATIVA X - SICOOB X", "MG", 600, 300 * fator, 100, 10
        )
        linhas += _linhas(data, "2", "SICREDI Y", "RS", 300, 200, 50, 5)
        linhas += _linhas(
            data, "3", "COOPERATIVA DE LIVRE ADMISSAO Z", "MG", 100, 50, 20, 1
        )
        linhas += _linhas(
            data, "9", "CENTRAL SICOOB", "MG", 5000, 10, 100, 1, segmento="B3C"
        )
    return coop.largo(pd.DataFrame(linhas))


def test_system_by_name_and_exception(monkeypatch):
    assert coop.sistema("COOPERATIVA X - SICOOB X", "1") == "Sicoob"
    assert coop.sistema("COOPERATIVA DE LIVRE ADMISSAO Z", "3") == coop.OUTRAS
    config = {**coop.cfg.configuracao(), "sistemas_excecoes": {"3": "Ailos"}}
    monkeypatch.setattr(coop.cfg, "configuracao", lambda: config)
    assert coop.sistema("COOPERATIVA DE LIVRE ADMISSAO Z", "3") == "Ailos"


def test_systems_table_leaves_centrals_out(dados):
    s = coop.por_sistema(dados)
    assert list(s.index) == ["Sicoob", "Sicredi", coop.OUTRAS]
    assert s.loc["Sicoob", "ativo"] == 600 and s.loc[
        "Sicoob", "share_ativo"
    ] == pytest.approx(60)
    assert s.loc["Sicoob", "cresc_carteira"] == pytest.approx(20) and s.loc[
        "Sicredi", "cresc_carteira"
    ] == pytest.approx(0)
    assert s.loc["Sicoob", "roe"] == pytest.approx(
        20
    )  # half-year profit ×2 over equity
    assert s.loc["Sicoob", "carteira_captacoes"] == pytest.approx(80)


def test_share_over_time_and_ranking(dados):
    p = coop.participacao(dados)
    assert p.loc[JUN26].sum() == pytest.approx(100) and p.loc[
        JUN26, "Sicoob"
    ] == pytest.approx(60)
    r = coop.ranking(dados[dados.uf == "MG"])
    assert list(r.instituicao) == ["1", "3"] and r.iloc[
        0
    ].cresc_carteira == pytest.approx(20)
