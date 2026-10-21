"""Automatic insights, upload parsing and example data."""

import base64

import pandas as pd
import pytest

from brasil_painel.dados import insights


def _upload(texto: str, mime="text/csv") -> str:
    return f"data:{mime};base64," + base64.b64encode(texto.encode()).decode()


def test_csv_with_semicolons_and_decimal_comma():
    df = insights.ler_envio(
        _upload("date;value\n2026-01-01;1,5\n2026-02-01;2,5\n"), "base.csv"
    )
    assert df.value.tolist() == [1.5, 2.5]


def test_bad_uploads_are_refused():
    with pytest.raises(insights.BaseInvalida, match="csv ou .xlsx"):
        insights.ler_envio(_upload("x"), "base.pdf")
    with pytest.raises(insights.BaseInvalida, match="10 MB"):
        insights.ler_envio(_upload("a" * (insights.LIMITE_BYTES + 1)), "base.csv")


def test_missing_columns_are_reported():
    df = pd.DataFrame({"Date": [1], "valor": [2]})
    assert insights.validar(df, ["date", "value"]) == ["value"]


def test_insights_describe_period_trend_and_extremes():
    df = pd.DataFrame(
        {
            "date": [f"2026-{m:02d}-01" for m in range(1, 7)] * 2,
            "country": ["A"] * 6 + ["B"] * 6,
            "value": [100, 101, 102, 103, 104, 110, 50, 50, 51, 52, 53, 55],
        }
    )
    r = insights.analisar(df)
    texto = " ".join(r.frases)
    assert r.linhas == 12 and r.periodo[0].month == 1
    assert "Período de 01/01/2026 a 01/06/2026." in texto
    assert "Maior value: A (110,00). Menor: B (55,00)." in texto


def test_outliers_are_counted():
    valores = [10.0] * 30 + [1000.0]
    df = pd.DataFrame({"value": valores})
    assert "fora do padrão" in insights.analisar(df).frases[-1]


def test_example_follows_the_columns():
    df = insights.exemplo(
        [("date", "date", ""), ("price", "number", ""), ("symbol", "string", "")], n=5
    )
    assert list(df.columns) == ["date", "price", "symbol"] and len(df) == 5
    assert (
        insights.modelo_csv(
            [("date", "date", ""), ("price", "number", "")]
        ).splitlines()[0]
        == "date;price"
    )


def test_automatic_chart_picks_lines_or_bars():
    from brasil_painel.componentes.graficos import figura_automatica

    tempo = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-02-01"],
            "country": ["A", "B"],
            "value": [1.0, 2.0],
        }
    )
    assert {t.type for t in figura_automatica(tempo).data} == {"scatter"}
    barras = pd.DataFrame({"name": ["x", "y"], "price": [3.0, 1.0]})
    assert figura_automatica(barras).data[0].type == "bar"
    assert figura_automatica(pd.DataFrame({"name": ["x"]})) is None
