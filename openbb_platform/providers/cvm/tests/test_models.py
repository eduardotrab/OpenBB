"""Unit tests for the CVM fund models (no network)."""

import datetime
import io
import zipfile

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_cvm.models.fund_daily import (
    CvmFundDailyFetcher,
    CvmFundDailyQueryParams,
    daily_report_urls,
    parse_daily_zip,
)
from openbb_cvm.models.funds import CvmFundsFetcher, CvmFundsQueryParams, parse_classes
from openbb_cvm.utils.helpers import digits

DAILY_CSV = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;VL_TOTAL;VL_QUOTA;"
    "VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST\n"
    "CLASSES - FIF;00.017.024/0001-53;;2026-10-01;1119426.37;44.9907626;"
    "1221524.87;0.00;2902.97;1\n"
    "CLASSES - FIF;00.017.024/0001-53;;2026-10-02;1119000.00;45.0000000;"
    "1221000.00;10.00;0.00;1\n"
    "CLASSES - FIF;97.929.213/0001-34;;2026-10-15;70065090.17;15.9020371;"
    "70089909.65;0.00;0.00;7\n"
)


def _zip(name: str, text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, text.encode("latin-1"))
    return buffer.getvalue()


def test_digits_normalizes_cnpj():
    assert digits("00.017.024/0001-53") == "00017024000153"


def test_daily_report_urls_one_zip_per_month():
    assert daily_report_urls(
        datetime.date(2026, 8, 20), datetime.date(2026, 10, 1)
    ) == [
        "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_202608.zip",
        "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_202609.zip",
        "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_202610.zip",
    ]


def test_parse_daily_zip_keeps_only_requested_cnpjs():
    rows = parse_daily_zip(_zip("inf.csv", DAILY_CSV), {"00017024000153"})
    assert rows == [
        {
            "date": datetime.date(2026, 10, 1),
            "cnpj": "00.017.024/0001-53",
            "fund_type": "CLASSES - FIF",
            "subclass": None,
            "total_value": 1119426.37,
            "quota": 44.9907626,
            "net_assets": 1221524.87,
            "inflows": 0.0,
            "outflows": 2902.97,
            "shareholders": 1,
        },
        {
            "date": datetime.date(2026, 10, 2),
            "cnpj": "00.017.024/0001-53",
            "fund_type": "CLASSES - FIF",
            "subclass": None,
            "total_value": 1119000.0,
            "quota": 45.0,
            "net_assets": 1221000.0,
            "inflows": 10.0,
            "outflows": 0.0,
            "shareholders": 1,
        },
    ]


def test_fund_daily_query_requires_cnpj_and_defaults_dates():
    query = CvmFundDailyFetcher.transform_query({"cnpj": "00.017.024/0001-53"})
    assert query.end_date == datetime.date.today()
    assert query.start_date == datetime.date.today() - datetime.timedelta(days=30)
    with pytest.raises(ValueError):
        CvmFundDailyQueryParams()


def test_fund_daily_transform_filters_dates():
    query = CvmFundDailyQueryParams(
        cnpj="00017024000153", start_date="2026-10-02", end_date="2026-10-31"
    )
    raw = parse_daily_zip(_zip("inf.csv", DAILY_CSV), {"00017024000153"})
    rows = CvmFundDailyFetcher.transform_data(query, raw)
    assert [(r.date, r.quota) for r in rows] == [(datetime.date(2026, 10, 2), 45.0)]


def test_fund_daily_transform_empty_raises():
    query = CvmFundDailyQueryParams(
        cnpj="1", start_date="2026-10-01", end_date="2026-10-02"
    )
    with pytest.raises(OpenBBError):
        CvmFundDailyFetcher.transform_data(query, [])


CLASSES_CSV = (
    "ID_Registro_Fundo;ID_Registro_Classe;CNPJ_Classe;Codigo_CVM;Data_Registro;"
    "Data_Constituicao;Data_Inicio;Tipo_Classe;Denominacao_Social;Situacao;"
    "Data_Inicio_Situacao;Classificacao;Indicador_Desempenho;Classe_Cotas;"
    "Classificacao_Anbima;Tributacao_Longo_Prazo;Entidade_Investimento;"
    "Permitido_Aplicacao_CemPorCento_Exterior;Classe_ESG;Forma_Condominio;"
    "Exclusivo;Publico_Alvo;Patrimonio_Liquido;Data_Patrimonio_Liquido\n"
    "1;10;11.111.111/0001-11;123;2020-01-01;2020-01-01;2020-01-02;Classes de Cotas"
    " de Fundos FIF;SICOOB RENDA FIXA;Em Funcionamento Normal;2020-01-02;Renda Fixa;"
    "CDI;N;Renda Fixa Duração Baixa;S;N;N;N;Aberto;N;Público Geral;1500000.50;"
    "2026-09-30\n"
    "2;20;22.222.222/0001-22;456;2019-01-01;2019-01-01;2019-01-02;Classes de Cotas"
    " de Fundos FIF;OUTRO FUNDO ACOES;Cancelada;2021-01-01;Ações;;N;;N;N;N;N;"
    "Aberto;N;Qualificado;;\n"
)


def test_parse_classes_maps_columns():
    rows = parse_classes(_zip("registro_classe.csv", CLASSES_CSV))
    assert rows[0] == {
        "cnpj": "11.111.111/0001-11",
        "name": "SICOOB RENDA FIXA",
        "cvm_code": "123",
        "class_type": "Classes de Cotas de Fundos FIF",
        "status": "Em Funcionamento Normal",
        "classification": "Renda Fixa",
        "anbima_classification": "Renda Fixa Duração Baixa",
        "benchmark": "CDI",
        "target_public": "Público Geral",
        "exclusive": False,
        "net_assets": 1500000.5,
        "net_assets_date": datetime.date(2026, 9, 30),
        "start_date": datetime.date(2020, 1, 2),
    }
    assert (rows[1]["net_assets"], rows[1]["benchmark"]) == (None, None)


def test_funds_search_is_accent_and_case_insensitive_and_active_by_default():
    rows = parse_classes(_zip("registro_classe.csv", CLASSES_CSV))
    found = CvmFundsFetcher.transform_data(CvmFundsQueryParams(search="sicoob"), rows)
    assert [r.name for r in found] == ["SICOOB RENDA FIXA"]
    assert (
        CvmFundsFetcher.transform_data(
            CvmFundsQueryParams(search="acoes", active_only=False), rows
        )[0].name
        == "OUTRO FUNDO ACOES"
    )
    with pytest.raises(OpenBBError):
        CvmFundsFetcher.transform_data(CvmFundsQueryParams(search="acoes"), rows)


def test_funds_filter_by_cnpj_digits():
    rows = parse_classes(_zip("registro_classe.csv", CLASSES_CSV))
    found = CvmFundsFetcher.transform_data(
        CvmFundsQueryParams(cnpj="11111111000111"), rows
    )
    assert [r.cnpj for r in found] == ["11.111.111/0001-11"]
