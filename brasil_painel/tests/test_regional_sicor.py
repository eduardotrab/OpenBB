"""SICOR rural credit: aggregation, incremental months and the store."""

import datetime as dt

import pytest

from brasil_painel.regional import armazem, sicor


def _linha(
    mes="08",
    uf="MG",
    programa="0001",
    segmento="Cooperativa de Crédito",
    banco="SICOOB CREDIMINAS",
    custeio=100.0,
    qtd=2,
    atividade="1",
):
    return {
        "AnoEmissao": "2026", "MesEmissao": mes, "nomeUF": uf, "nomeIF": banco, "nomeSegmento": segmento,
        "cdPrograma": programa, "Atividade": atividade, "VlCusteio": custeio, "VlInvestimento": 10.0,
        "VlComercializacao": 0.0, "VlIndustrializacao": 0.0, "QtdCusteio": qtd, "QtdInvestimento": 1,
        "QtdComercializacao": 0, "QtdIndustrializacao": 0,
    }  # fmt: skip


def test_rows_are_grouped_by_size_lender_and_activity():
    df = sicor.agregar(
        [
            _linha(),
            _linha(banco="COOP CRESOL", custeio=50.0),
            _linha(programa="0050", segmento="Banco Múltiplo", banco="BANCO X"),
            _linha(programa="0999", atividade="2"),
        ]
    )
    assert list(df.columns) == sicor.SCHEMA.names
    pequeno = df[(df.porte == "Pequeno produtor") & df.cooperativa]
    assert sorted(pequeno.valor_custeio) == [50.0, 100.0]
    assert pequeno[pequeno.sicoob].contratos.item() == 3.0
    medio = df[df.porte == "Médio produtor"].iloc[0]
    assert not medio.cooperativa and not medio.sicoob
    assert set(df[df.porte == "Grande produtor"].atividade) == {"Pecuária"}
    assert df.data.unique().tolist() == [dt.date(2026, 8, 1)]


def test_months_to_fetch_are_missing_ones_plus_the_last_two():
    existentes = {dt.date(2026, m, 1) for m in range(1, 7)}
    meses = sicor.meses_a_buscar(existentes, dt.date(2026, 1, 1), dt.date(2026, 10, 20))
    assert meses == [dt.date(2026, m, 1) for m in (5, 6, 7, 8, 9)]


class Sessao:
    def __init__(self, por_mes):
        self.por_mes, self.pedidos = por_mes, []

    def get(self, url, timeout):
        assert "+" not in url, "Olinda needs %20 for spaces"
        mes = (
            url.split("MesEmissao%20eq%20%27")[1][:2]
            if "%27" in url
            else url.split("MesEmissao%20eq%20'")[1][:2]
        )
        self.pedidos.append(mes)

        class R:
            def raise_for_status(self):
                pass

            def json(_self):
                return {"value": self.por_mes.get(mes, [])}

        return R()


def test_update_stores_and_skips_unpublished_months(tmp_path):
    sessao = Sessao({"08": [_linha()], "07": [_linha(mes="07")]})
    df = sicor.atualizar(
        [2026], pasta=tmp_path, sessao=sessao, hoje=dt.date(2026, 9, 15)
    )
    assert sorted(df.data.unique()) == [dt.date(2026, 7, 1), dt.date(2026, 8, 1)]
    assert armazem.ler("sicor_uf", tmp_path).valor_custeio.sum() == pytest.approx(200.0)
    assert len(sessao.pedidos) == 8  # jan..aug
