"""IF.data summary of the credit cooperatives (quarterly)."""

import datetime as dt

from brasil_painel.dados.api import FonteIndisponivel
from brasil_painel.regional import armazem, ifdata


def _linha(periodo, cnpj, conta, valor, nome="SICOOB TESTE", segmento="B3S"):
    return {"period": periodo, "institution": cnpj, "name": nome, "segment": segmento, "uf": "MG",
            "city": "Belo Horizonte", "report": "Resumo", "group": None, "account": "x", "column": conta, "value": valor}  # fmt: skip


class Cliente:
    def __init__(self, respostas):
        self.respostas, self.pedidos = respostas, []

    def get(self, path, **params):
        self.pedidos.append(params.get("period"))
        resposta = self.respostas.get(params.get("period"))
        if isinstance(resposta, Exception):
            raise resposta
        return resposta or []


def test_quarters_back_from_the_latest():
    assert ifdata.trimestres(dt.date(2026, 6, 30), 3) == ["202606", "202603", "202512"]


def test_ingestion_keeps_rows_with_values_and_skips_failed_quarters(tmp_path):
    cliente = Cliente({
        None: [_linha("2026-06-30", "1", "Ativo Total", 10.0), _linha("2026-06-30", "1", "Lucro Líquido", None)],
        "202603": [_linha("2026-03-31", "1", "Ativo Total", 9.0)],
        "202512": FonteIndisponivel("500"),
    })  # fmt: skip
    df = ifdata.atualizar(pasta=tmp_path, client=cliente, trimestres_=3)
    assert list(df.columns) == ifdata.SCHEMA.names
    assert sorted(df.data) == [dt.date(2026, 3, 31), dt.date(2026, 6, 30)] and set(
        df.conta
    ) == {"Ativo Total"}
    assert armazem.ler(ifdata.NOME, tmp_path).shape == df.shape


def test_stored_quarters_are_not_fetched_again_except_the_latest(tmp_path):
    primeira = Cliente(
        {
            None: [_linha("2026-06-30", "1", "Ativo Total", 10.0)],
            "202603": [_linha("2026-03-31", "1", "Ativo Total", 9.0)],
        }
    )
    ifdata.atualizar(pasta=tmp_path, client=primeira, trimestres_=2)
    segunda = Cliente({None: [_linha("2026-06-30", "1", "Ativo Total", 11.0)]})
    df = ifdata.atualizar(pasta=tmp_path, client=segunda, trimestres_=2)
    assert segunda.pedidos == [None]
    assert df.set_index("data").valor.to_dict() == {
        dt.date(2026, 3, 31): 9.0,
        dt.date(2026, 6, 30): 11.0,
    }
