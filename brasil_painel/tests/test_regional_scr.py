"""SCR.data ingestion: CSV parsing, aggregation and the Parquet contract."""

import datetime as dt
import zipfile

import pandas as pd
import pyarrow as pa
import pytest

from brasil_painel.regional import armazem, scr

CABECALHO = (
    "data_base;uf;segmento;cliente;cnae_ocupacao;porte;modalidade;submodalidade;"
    "origem;indexador;numero_de_operacoes;a_vencer_ate_90_dias;carteira_a_vencer;"
    "vencido_de_15_ate_90_dias;vencido_acima_de_90_dias;carteira_vencida;"
    "carteira_ativa;carteira_inadimplencia;ativo_problematico"
)


def _linha(data, uf, segmento, cliente, ativa, inad, venc15):
    campos = [
        data,
        uf,
        segmento,
        cliente,
        "Construção",
        "Pequeno",
        "Capital de giro",
        "Outros",
        "Sem destinação específica",
        "Prefixado",
        "-1",
        "1,00",
        "1,00",
        venc15,
        inad,
        inad,
        ativa,
        inad,
        inad,
    ]
    return ";".join(f'"{c}"' for c in campos)


def _csv(caminho, linhas):
    caminho.write_text(
        "﻿" + CABECALHO + "\n" + "\n".join(linhas) + "\n", encoding="utf-8"
    )
    return caminho


@pytest.fixture
def csv_agosto(tmp_path):
    return _csv(
        tmp_path / "scrdata_202608.csv",
        [
            _linha(
                "2026-08-31", "MG", "Cooperativa", "PF", "1000,50", "50,25", "10,00"
            ),
            _linha(
                "2026-08-31", "MG", "Cooperativa", "PF", "2000,00", "100,00", "0,00"
            ),
            _linha("2026-08-31", "MG", "Banco", "PF", "5000,00", "200,00", "30,00"),
            _linha("2026-08-31", "SP", "Banco", "PJ", "9000,00", "0,00", "0,00"),
        ],
    )


def test_aggregate_sums_by_month_uf_cooperative_and_client(csv_agosto):
    df = scr.agregar_csv(csv_agosto)
    mg_coop = df[(df.uf == "MG") & df.cooperativa & (df.cliente == "PF")].iloc[0]
    assert mg_coop.carteira_ativa == pytest.approx(3000.50)
    assert mg_coop.carteira_inadimplencia == pytest.approx(150.25)
    assert mg_coop.vencido_15_90 == pytest.approx(10.0)
    assert mg_coop.data == dt.date(2026, 8, 31)
    assert len(df) == 3
    assert list(df.columns) == scr.SCHEMA.names


def test_aggregate_zip_reads_every_month(tmp_path, csv_agosto):
    julho = _csv(
        tmp_path / "scrdata_202607.csv",
        [_linha("2026-07-31", "MG", "Banco", "PF", "10,00", "1,00", "0,00")],
    )
    arquivo = tmp_path / "scrdata_2026.zip"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.write(csv_agosto, csv_agosto.name)
        z.write(julho, julho.name)
    datasets = scr.agregar_zip(arquivo)
    df = datasets["scr_uf"]
    assert sorted(df.data.unique()) == [dt.date(2026, 7, 31), dt.date(2026, 8, 31)]
    classe = datasets["scr_classe"]
    assert classe.carteira_ativa.sum() == pytest.approx(df.carteira_ativa.sum())
    assert set(classe.produto) == {"Outros"}  # fixture submodality is "Outros"
    assert list(classe.columns) == scr.CLASSE.schema.names


def test_store_writes_parquet_and_rejects_bad_schema(tmp_path, csv_agosto):
    df = scr.agregar_csv(csv_agosto)
    destino = armazem.gravar(df, "scr_uf", scr.SCHEMA, tmp_path)
    assert armazem.ler("scr_uf", tmp_path).equals(df)
    with pytest.raises(armazem.SchemaInvalido):
        armazem.gravar(df.drop(columns=["cliente"]), "scr_uf", scr.SCHEMA, tmp_path)
    with pytest.raises(armazem.SchemaInvalido):
        armazem.gravar(df.assign(carteira_ativa=None), "scr_uf", scr.SCHEMA, tmp_path)
    assert armazem.ler("scr_uf", tmp_path).equals(df), (
        "a bad file must not replace the good one"
    )
    assert not list(tmp_path.glob("*.tmp"))
    assert destino.name == "scr_uf.parquet"


def test_store_returns_none_when_dataset_is_missing(tmp_path):
    assert armazem.ler("nada", tmp_path) is None


def test_store_directory_comes_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path / "x"))
    assert armazem.diretorio() == tmp_path / "x"


def test_schema_types_are_explicit():
    assert scr.SCHEMA.field("data").type == pa.date32()
    assert scr.SCHEMA.field("cooperativa").type == pa.bool_()


def test_years_to_update_default_to_this_and_last_year():
    assert scr.anos_padrao(dt.date(2026, 10, 20)) == [2025, 2026]


def test_merge_years_keeps_one_row_per_key():
    base = dict(
        uf="MG",
        cooperativa=True,
        cliente="PF",
        carteira_inadimplencia=0.0,
        vencido_15_90=0.0,
    )
    antigo = pd.DataFrame([dict(data=dt.date(2026, 7, 31), carteira_ativa=1.0, **base)])
    novo = pd.DataFrame([dict(data=dt.date(2026, 7, 31), carteira_ativa=2.0, **base)])
    juntos = scr.juntar([antigo, novo])
    assert juntos.carteira_ativa.tolist() == [2.0]


def test_cli_reports_failures_without_stopping(monkeypatch, capsys):
    from brasil_painel.regional import cli

    def falha(anos=None):
        raise RuntimeError("fonte fora do ar")

    monkeypatch.setitem(cli.DATASETS, "scr", falha)
    assert cli.main(["atualizar", "scr"]) == 1
    assert "scr: ERRO fonte fora do ar" in capsys.readouterr().err


def test_cli_rejects_unknown_dataset():
    from brasil_painel.regional import cli

    with pytest.raises(SystemExit):
        cli.main(["atualizar", "nada"])


def test_class_dataset_flags_mei_and_keeps_the_income_band(tmp_path):
    linhas = [
        _linha("2026-08-31", "MG", "Cooperativa", "PF", "100,00", "1,00", "0,00"),
    ]
    caminho = _csv(tmp_path / "scrdata_202608.csv", linhas)
    caminho.write_text(
        caminho.read_text(encoding="utf-8").replace(
            '"Construção";"Pequeno"', '"MEI";"Mais de 3 a 5 salários mínimos"'
        ),
        encoding="utf-8",
    )
    df = scr.agregar_csv(caminho, scr.CLASSE)
    linha = df.iloc[0]
    assert bool(linha.mei) and linha.porte == "Mais de 3 a 5 salários mínimos"
