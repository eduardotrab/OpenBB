"""Merging news from several origins."""

import datetime as dt

from brasil_painel.dados.api import FonteIndisponivel
from brasil_painel.dados.noticias import Noticia, coletar, juntar, parse_data

UTC = dt.timezone.utc


def n(titulo, quando, origem="A", url=None):
    return Noticia(
        titulo=titulo, data=quando, url=url or f"https://x/{titulo}", origem=origem
    )


def test_parse_data_handles_z_offset_and_naive_brasilia_time():
    assert parse_data("2026-10-16T12:00:49Z") == dt.datetime(
        2026, 10, 16, 12, 0, 49, tzinfo=UTC
    )
    assert parse_data("2026-10-20T02:11:10+00:00") == dt.datetime(
        2026, 10, 20, 2, 11, 10, tzinfo=UTC
    )
    assert parse_data("2026-10-16T01:28:30") == dt.datetime(
        2026, 10, 16, 4, 28, 30, tzinfo=UTC
    )


def test_juntar_sorts_newest_first_dedupes_and_limits():
    t = dt.datetime(2026, 10, 20, tzinfo=UTC)
    a = [
        n("Copom  mantém Selic", t, "BCB", url="u1"),
        n("Velha", t - dt.timedelta(days=3)),
    ]
    b = [
        n("Copom mantém Selic ", t + dt.timedelta(hours=1), "Agência", url="u2"),
        n("Nova", t + dt.timedelta(hours=2), "Agro"),
    ]
    resultado = juntar([a, b], limite=3)
    assert [(x.titulo, x.origem) for x in resultado] == [
        ("Nova", "Agro"),
        ("Copom mantém Selic ", "Agência"),
        ("Velha", "A"),
    ]


class FakeClient:
    def get(self, path, **params):
        if params.get("provider") == "ibge":
            raise FonteIndisponivel("ibge")
        return [
            {
                "date": "2026-10-16T12:00:49Z",
                "title": f"{path} {params.get('category') or params.get('source')}",
                "url": f"https://x/{path}/{params}",
            }
        ]


def test_coletar_isolates_failing_origins():
    noticias, falhas = coletar(FakeClient())
    assert falhas == ["IBGE"]
    assert {x.origem for x in noticias} == {
        "BCB",
        "Copom",
        "Agência Brasil",
        "Agro (Canal Rural)",
    }


def test_juntar_caps_items_per_origin():
    t = dt.datetime(2026, 10, 20, tzinfo=UTC)
    agro = [n(f"agro {i}", t + dt.timedelta(minutes=i), "Agro") for i in range(10)]
    bcb = [n("bcb", t - dt.timedelta(days=2), "BCB")]
    resultado = juntar([agro, bcb], limite=40, por_origem=3)
    assert [x.origem for x in resultado] == ["Agro"] * 3 + ["BCB"]
