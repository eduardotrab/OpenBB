"""Ingestion of interest rates by lender and of payment cards."""

import datetime as dt

from brasil_painel.regional import cartoes, juros


def test_rates_table_keeps_rank_and_rates():
    linhas = [
        {"InicioPeriodo": "2026-09-01", "Segmento": "PESSOA FÍSICA", "Modalidade": "Cheque especial - Prefixado",
         "InstituicaoFinanceira": "BANCO SICOOB S.A.", "Posicao": 6, "TaxaJurosAoMes": 4.42, "TaxaJurosAoAno": 68.0},
    ]  # fmt: skip
    df = juros.tabela(linhas)
    assert list(df.columns) == juros.SCHEMA.names
    assert df.iloc[0].inicio == dt.date(2026, 9, 1) and df.iloc[0].posicao == 6


def test_cards_are_summed_by_function_and_brand():
    linhas = [
        {"trimestre": "20262", "nomeBandeira": "Visa", "nomeFuncao": "Crédito", "qtdCartoesEmitidos": 10,
         "qtdCartoesAtivos": 4, "qtdTransacoesNacionais": 100, "valorTransacoesNacionais": 1000.0},
        {"trimestre": "20262", "nomeBandeira": "Visa", "nomeFuncao": "Crédito", "qtdCartoesEmitidos": 5,
         "qtdCartoesAtivos": 1, "qtdTransacoesNacionais": 10, "valorTransacoesNacionais": None},
    ]  # fmt: skip
    df = cartoes.tabela(linhas)
    linha = df.iloc[0]
    assert (linha.data, linha.emitidos, linha.ativos, linha.valor) == (
        dt.date(2026, 6, 1),
        15.0,
        5.0,
        1000.0,
    )


def test_olinda_query_encodes_spaces_as_percent_20():
    from brasil_painel.regional import olinda

    class Sessao:
        url = ""

        def get(self, url, timeout):
            Sessao.url = url

            class R:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"value": []}

            return R()

    olinda.consultar("x", {"$filter": "a eq 'b'"}, Sessao())
    assert "+" not in Sessao.url and "a%20eq%20'b'" in Sessao.url
