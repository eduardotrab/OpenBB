"""Opportunities: room to grow and early-warning alerts by niche."""

import datetime as dt

import pandas as pd
import pytest

from brasil_painel.dados import oportunidades as op

MESES = [dt.date(2025, m, 28) for m in range(1, 13)] + [dt.date(2026, 1, 28)]


def _linhas(
    uf,
    coop,
    carteira,
    inad=0.0,
    venc=0.0,
    *,
    classe="Varejo",
    produto="Veículos",
    datas=MESES,
):
    return [
        {"data": d, "uf": uf, "cooperativa": coop, "classe": classe, "produto": produto,
         "carteira_ativa": carteira(i) if callable(carteira) else carteira,
         "carteira_inadimplencia": inad(i) if callable(inad) else inad,
         "vencido_15_90": venc(i) if callable(venc) else venc}
        for i, d in enumerate(datas)
    ]  # fmt: skip


def _df(*partes):
    return pd.DataFrame([linha for parte in partes for linha in parte])


@pytest.fixture
def mercado():
    # Brasil: cooperativas com 20% (SP 30%, MG 5%); inadimplência 5% em SP, 2% em MG
    return _df(
        _linhas("SP", False, 700, inad=35),
        _linhas("SP", True, 300, inad=15),
        _linhas("MG", False, lambda i: 950 + i * 10, inad=lambda i: 19 + i * 0.2),
        _linhas("MG", True, 50, inad=1),
    )


def test_niche_numbers(mercado):
    n = op.nichos(mercado, ("uf",)).set_index("uf")
    assert n.loc["SP", "carteira"] == 1000 and n.loc["SP", "share"] == pytest.approx(30)
    assert n.loc["MG", "cresc_12m"] == pytest.approx((1120 / 1000 - 1) * 100)
    assert n.loc["MG", "inad"] == pytest.approx((21.4 + 1) / 1120 * 100)


def test_room_to_grow_uses_the_national_share_as_reference(mercado):
    e = op.espaco(mercado, ("uf",), minimo=0)
    # only MG: market growing, default below Brasil, share 50/1120 below the national one
    assert list(e.uf) == ["MG"]
    linha = e.iloc[0]
    assert linha.share_ref == pytest.approx(350 / 2120 * 100)
    assert linha.espaco == pytest.approx(1120 * (linha.share_ref - linha.share) / 100)


def test_room_to_grow_respects_size_and_the_state_filter(mercado):
    assert op.espaco(mercado, ("uf",), minimo=2000).empty
    # filtering by state keeps the national reference
    so_mg = op.espaco(mercado, ("uf",), minimo=0, uf="MG")
    assert so_mg.iloc[0].share_ref == pytest.approx(350 / 2120 * 100)


def test_reference_is_per_class_and_product():
    df = _df(
        _linhas("SP", False, 900, produto="Veículos"),
        _linhas("SP", True, 100, produto="Veículos"),
        _linhas("MG", False, lambda i: 1000 + i, produto="Veículos"),
        _linhas("SP", True, 500, produto="Cartão de crédito"),
        _linhas("SP", False, 500, produto="Cartão de crédito"),
    )
    e = op.espaco(df, ("uf", "produto"), minimo=0)
    assert list(zip(e.uf, e.produto, strict=True)) == [("MG", "Veículos")]
    assert e.iloc[0].share_ref == pytest.approx(100 / 2000 * 100, rel=0.01)


def test_alerts_rank_the_rise_of_15_to_90_day_arrears(mercado):
    sobe = _df(
        _linhas("RS", False, 1000, venc=lambda i: 10 if i < 10 else 40),
        _linhas("RS", True, 100, venc=1),
    )
    a = op.alertas(pd.concat([mercado, sobe]), ("uf",), minimo=0)
    assert a.iloc[0].uf == "RS" and a.iloc[0].delta == pytest.approx(
        (40 - 10) / 1100 * 100
    )
    assert (a.delta > 0).all()


def test_alerts_can_follow_only_the_cooperatives(mercado):
    coop = _df(
        _linhas("PR", False, 1000, venc=10),
        _linhas("PR", True, 200, venc=lambda i: 2 if i < 10 else 12),
    )
    a = op.alertas(pd.concat([mercado, coop]), ("uf",), sinal="cooperativas", minimo=0)
    assert a.iloc[0].uf == "PR" and a.iloc[0].delta == pytest.approx(5)
    # in the whole market the same rise is diluted
    assert (
        op.alertas(pd.concat([mercado, coop]), ("uf",), minimo=0)
        .set_index("uf")
        .loc["PR", "delta"]
        < 1
    )


def test_niche_series_for_the_chart(mercado):
    s = op.serie_nicho(mercado, {"uf": "SP"})
    assert (
        len(s) == len(MESES)
        and s.iloc[-1].inad == pytest.approx(5)
        and s.iloc[-1].inad_coop == pytest.approx(5)
    )


def test_alerts_rank_by_amount_and_skip_remainders():
    df = _df(
        _linhas(
            "SP", False, 10_000, venc=lambda i: 100 if i < 10 else 300
        ),  # +2 p.p. on 10k
        _linhas(
            "AC", False, 100, venc=lambda i: 1 if i < 10 else 11
        ),  # +10 p.p. on 100
        _linhas(
            "RJ", False, 10_000, venc=lambda i: 0 if i < 10 else 900, produto="Outros"
        ),
    )
    a = op.alertas(df, ("uf", "produto"), minimo=0)
    assert list(a.uf) == ["SP", "AC"] and a.iloc[0].impacto == pytest.approx(200)


def test_room_to_grow_skips_remainders(mercado):
    outros = mercado.assign(produto="Outros")
    assert op.espaco(
        pd.concat([mercado, outros]), ("uf", "produto"), minimo=0
    ).produto.tolist() == ["Veículos"]
