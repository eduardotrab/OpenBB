"""Municipal datasets: Pix by municipality and IBGE population and GDP."""

import datetime as dt

from brasil_painel.regional import armazem, ibge, pix

HOJE = dt.date(2026, 10, 20)


def _pix(mes, municipio, estado, pf=1.0):
    return {"AnoMes": mes, "Municipio_Ibge": municipio, "Estado_Ibge": estado, "VL_PagadorPF": pf,
            "VL_PagadorPJ": 2.0, "VL_RecebedorPF": 3.0, "VL_RecebedorPJ": 4.0}  # fmt: skip


def test_pix_by_municipality_keeps_the_ibge_code_and_drops_the_current_month(tmp_path):
    df = pix.por_municipio(
        [
            _pix(202609, 3106200, 31, 9.5),
            _pix(202610, 3106200, 31),
            _pix(202609, None, 31),
        ],
        HOJE,
    )
    assert list(df.columns) == armazem.SCHEMA_MUNICIPAL.names
    assert (
        set(df.data) == {dt.date(2026, 9, 1)}
        and set(df.municipio) == {"3106200"}
        and set(df.uf) == {"MG"}
    )
    assert df.set_index("indicador").loc["pix_pago_pf", "valor"] == 9.5
    armazem.gravar(df, "pix_municipio", armazem.SCHEMA_MUNICIPAL, tmp_path)


def test_ibge_municipal_rows():
    linhas = [
        {"period": "2023", "level": "N6", "location_id": "3106200", "value": 1000.0},
        {"period": "2023", "level": "N6", "location_id": "5300108", "value": None},
    ]
    df = ibge.longo_municipal(linhas, "pib", escala=1000)
    assert df.to_dict("records") == [
        {
            "data": dt.date(2023, 1, 1),
            "municipio": "3106200",
            "uf": "MG",
            "indicador": "pib",
            "valor": 1_000_000.0,
        }
    ]
