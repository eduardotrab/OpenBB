"""Unit tests for the IBGE aggregates (SIDRA) model (no network)."""

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_ibge.models.aggregates import (
    IbgeAggregatesFetcher,
    IbgeAggregatesQueryParams,
    build_aggregates_url,
)

BASE = "https://servicodados.ibge.gov.br/api/v3/agregados/"


def test_build_url_encodes_pipes_and_brackets():
    query = IbgeAggregatesQueryParams(table=1737, variables="63,2265", periods="-2")
    assert build_aggregates_url(query) == (
        BASE + "1737/periodos/-2/variaveis/63%7C2265?localidades=N1%5Ball%5D"
    )


def test_build_url_with_level_locations_and_classification():
    query = IbgeAggregatesQueryParams(
        table=7060,
        variables="63",
        periods="202601-202609",
        level="N6",
        locations="3550308,3304557",
        classification="315[7169]",
    )
    assert build_aggregates_url(query) == (
        BASE + "7060/periodos/202601-202609/variaveis/63"
        "?localidades=N6%5B3550308,3304557%5D&classificacao=315%5B7169%5D"
    )


def test_query_defaults_to_last_12_periods_brazil_all_variables():
    query = IbgeAggregatesFetcher.transform_query({"table": 1737})
    assert (query.variables, query.periods, query.level, query.locations) == (
        "allxp",
        "-12",
        "N1",
        "all",
    )


RAW = [
    {
        "id": "63",
        "variavel": "IPCA - Variação mensal",
        "unidade": "%",
        "resultados": [
            {
                "classificacoes": [],
                "series": [
                    {
                        "localidade": {
                            "id": "1",
                            "nivel": {"id": "N1", "nome": "Brasil"},
                            "nome": "Brasil",
                        },
                        "serie": {"202608": "-0.32", "202609": "0.82", "202610": "..."},
                    }
                ],
            }
        ],
    },
    {
        "id": "2265",
        "variavel": "IPCA - Variação acumulada em 12 meses",
        "unidade": "%",
        "resultados": [
            {
                "classificacoes": [
                    {
                        "id": "315",
                        "nome": "Geral",
                        "categoria": {"7169": "Índice geral"},
                    }
                ],
                "series": [
                    {
                        "localidade": {
                            "id": "1",
                            "nivel": {"id": "N1", "nome": "Brasil"},
                            "nome": "Brasil",
                        },
                        "serie": {"202609": "4.58"},
                    }
                ],
            }
        ],
    },
]


def test_transform_data_flattens_series_and_drops_unavailable_markers():
    query = IbgeAggregatesQueryParams(table=1737)
    rows = IbgeAggregatesFetcher.transform_data(query, RAW)
    assert [
        (r.period, r.variable_id, r.unit, r.location, r.classification, r.value)
        for r in rows
    ] == [
        ("202608", "63", "%", "Brasil", None, -0.32),
        ("202609", "63", "%", "Brasil", None, 0.82),
        ("202610", "63", "%", "Brasil", None, None),
        ("202609", "2265", "%", "Brasil", "Geral: Índice geral", 4.58),
    ]
    assert rows[0].variable == "IPCA - Variação mensal"
    assert (rows[0].location_id, rows[0].level) == ("1", "N1")


def test_transform_data_without_rows_raises_empty_data():
    with pytest.raises(OpenBBError):
        IbgeAggregatesFetcher.transform_data(IbgeAggregatesQueryParams(table=1737), [])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("-", 0.0), ("...", None), ("..", None), ("X", None), ("Z", None), ("1.5", 1.5)],
)
def test_sidra_markers_dash_is_absolute_zero_others_unavailable(raw, expected):
    data = [
        {
            "id": "1",
            "variavel": "v",
            "unidade": "%",
            "resultados": [
                {
                    "classificacoes": [],
                    "series": [
                        {
                            "localidade": {
                                "id": "1",
                                "nivel": {"id": "N1", "nome": "Brasil"},
                                "nome": "Brasil",
                            },
                            "serie": {"202609": raw},
                        }
                    ],
                }
            ],
        }
    ]
    query = IbgeAggregatesQueryParams(table=1)
    assert IbgeAggregatesFetcher.transform_data(query, data)[0].value == expected
