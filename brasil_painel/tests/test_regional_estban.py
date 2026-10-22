"""ESTBAN (bank branches by municipality) and municipal SICOR."""

import datetime as dt
import io
import zipfile

import pandas as pd
import pytest

from brasil_painel.regional import armazem, estban, sicor

CABECALHO = (
    "#DATA_BASE;UF;CODMUN;MUNICIPIO;CNPJ;NOME_INSTITUICAO;VERBETE_160_OPERACOES_DE_CREDITO;"
    "VERBETE_163_FIN_RURAIS_AGRICUL_CUST/INVEST;VERBETE_167_FINANCIAMENTOS_AGROINDUSTRIAIS;"
    "VERBETE_401_SERVICOS_PUBLICOS + VERBETE_402_ATIVIDADES_EMPRESARIAIS;VERBETE_420_DEPOSITOS_DE_POUPANCA;"
    "VERBETE_432_DEPOSITOS_A_PRAZO;VERBETE_399_TOTAL_DO_ATIVO"
)
LINHAS = [
    "202606;MG;3155;RIO PARANAIBA;0;BANCO SICOOB S.A.;100,5;10;0;5;20;1;9",
    "202606;MG;3155;RIO PARANAIBA;1;BCO DO BRASIL S.A.;899,5;90;0;15;80;9;9",
    "202606;DF;42680;BRASILIA (TAGUATINGA);1;BCO DO BRASIL S.A.;50;0;0;0;0;0;9",
    "202606;DF;1;BRASILIA;1;BCO DO BRASIL S.A.;50;0;0;0;0;0;9",
    "202606;RJ;24574;PARATI;1;BCO DO BRASIL S.A.;7;0;0;0;0;0;9",
    "202606;SP;99999;CIDADE QUE NAO EXISTE;1;BCO X;1;0;0;0;0;0;9",
]


def _zip(linhas=LINHAS) -> bytes:
    texto = (
        "ESTBAN (Documento 4500) por municipio\nData de geracao dos dados: 2026-10-01\n"
    )
    texto += "\n".join([CABECALHO, *linhas]) + "\n"
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        z.writestr("202606_ESTBAN.CSV", texto.encode("latin-1"))
    return saida.getvalue()


def test_reads_the_csv_and_links_bcb_codes_to_ibge():
    por_instituicao, sem_codigo = estban.ler_zip(io.BytesIO(_zip()))
    df = estban.municipal(por_instituicao)
    assert list(df.columns) == armazem.SCHEMA_MUNICIPAL.names
    assert sem_codigo == ["CIDADE QUE NAO EXISTE (SP)"]
    valores = df.set_index(["municipio", "indicador"]).valor
    assert valores["3155504", "credito"] == pytest.approx(1000)
    assert valores["3155504", "credito_sicoob"] == pytest.approx(100.5)
    assert valores["3155504", "rural"] == pytest.approx(100)
    assert (
        valores["3155504", "poupanca"] == 100
        and valores["3155504", "poupanca_sicoob"] == 20
    )
    assert valores["3155504", "depositos"] == 30
    assert valores["5300108", "credito"] == 100  # every DF region adds up in Brasília
    assert valores["3303807", "credito"] == 7  # old spelling (Parati → Paraty)
    assert set(df.data) == {dt.date(2026, 6, 1)} and set(
        df[df.municipio == "3155504"].uf
    ) == {"MG"}


def test_missing_month_is_none():
    class Sessao:
        def get(self, url, timeout):
            return type(
                "R",
                (),
                {
                    "status_code": 404,
                    "content": b"<html>",
                    "raise_for_status": lambda self: None,
                },
            )()

    assert estban.baixar(dt.date(2026, 7, 1), pasta=None, sessao=Sessao()) is None


def test_rural_by_municipality_maps_investment_through_custeio_codes():
    custeio = [
        {
            "AnoEmissao": "2026",
            "MesEmissao": "08",
            "cdPrograma": "0001",
            "VlCusteio": 10.0,
            "codCadMu": "3155",
            "codIbge": "3155504",
        },
        {
            "AnoEmissao": "2026",
            "MesEmissao": "08",
            "cdPrograma": "0999",
            "VlCusteio": 5.0,
            "codCadMu": "3155",
            "codIbge": "3155504",
        },
    ]
    invest = [
        {"AnoEmissao": "2026", "MesEmissao": "08", "cdPrograma": "0050", "VlInvest": 7.0, "cdMunicipio": "3155"},
        {"AnoEmissao": "2026", "MesEmissao": "08", "cdPrograma": "0050", "VlInvest": 1.0, "cdMunicipio": "77777"},
    ]  # fmt: skip
    df = sicor.por_municipio(custeio, invest)
    valores = df.set_index("indicador").valor
    assert (
        valores["custeio_pequeno"] == 10
        and valores["custeio_grande"] == 5
        and valores["investimento_medio"] == 7
    )
    assert set(df.municipio) == {"3155504"} and set(df.uf) == {"MG"}


def test_doubled_balance_is_removed_from_the_head_office_only():
    linhas = []
    for mes, dobrado in (
        (1, False),
        (2, True),
        (3, False),
        (4, True),
        (5, True),
    ):  # like Itaú in 2025-2026
        # true balances: head office 60 of assets and 30 of credit, branch town 40 and 20;
        # in a doubled month the head office also carries the whole balance again (100 and 50)
        extra_ativo, extra_credito = (100.0, 50.0) if dobrado else (0.0, 0.0)
        linhas.append(
            {
                "data": dt.date(2026, mes, 1),
                "municipio": "5300108",
                "cnpj": "A",
                "sicoob": False,
                "ativo": 60.0 + extra_ativo,
                "credito": 30.0 + extra_credito,
                "rural": 0.0,
                "poupanca": 0.0,
                "depositos": 0.0,
            }
        )
        linhas.append(
            {
                "data": dt.date(2026, mes, 1),
                "municipio": "3106200",
                "cnpj": "A",
                "sicoob": False,
                "ativo": 40.0,
                "credito": 20.0,
                "rural": 0.0,
                "poupanca": 0.0,
                "depositos": 0.0,
            }
        )
        linhas.append(
            {
                "data": dt.date(2026, mes, 1),
                "municipio": "3106200",
                "cnpj": "B",
                "sicoob": True,
                "ativo": 30.0,
                "credito": 20.0,
                "rural": 0.0,
                "poupanca": 1.0,
                "depositos": 0.0,
            }
        )
    df, corrigidos = estban.corrigir_duplicacao(pd.DataFrame(linhas))
    assert [(c, d.month) for c, d in corrigidos] == [("A", 2), ("A", 4), ("A", 5)]
    a = df[df.cnpj == "A"]
    assert set(a[a.municipio == "5300108"].credito) == {30.0}
    assert set(a[a.municipio == "3106200"].credito) == {
        20.0
    }  # the branch town is untouched
    assert set(df[df.cnpj == "B"].credito) == {20.0}
