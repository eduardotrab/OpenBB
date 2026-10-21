"""Decision views: where cooperatives have room to grow and where arrears are rising.

The unit is a niche: a state, optionally crossed with class and product. Every
function takes the long frame of `base()` (columns data, uf, cooperativa,
classe, produto and the three amounts) so the tests can feed small frames.
"""

import datetime as dt

import pandas as pd

from brasil_painel.dados import classes
from brasil_painel.regional import classes as cfg

DETALHES = {
    "uf": ("uf",),
    "uf_classe": ("uf", "classe"),
    "uf_produto": ("uf", "produto"),
    "uf_classe_produto": ("uf", "classe", "produto"),
}
MINIMO_MERCADO = 100e6  # niches below R$ 100 mi swing too much month to month
MINIMO_COOP = 20e6
VALORES = ["carteira_ativa", "carteira_inadimplencia", "vencido_15_90"]
# remainders, not niches anyone can act on
SOBRAS = {cfg.OUTROS, *cfg.NAO_INFORMADO.values()}


def base(grupo: str | None = None) -> pd.DataFrame:
    """`scr_classe` with the class of each row; `None` joins individuals and companies.

    Individuals with MEI occupation appear in both groups (as in the segment
    screens); joined, they count once, on the individuals' side.
    """
    if grupo:
        return classes.com_classes(grupo)
    pj = classes.com_classes("pj")
    return pd.concat(
        [classes.com_classes("pf"), pj[pj.cliente == "PJ"]], ignore_index=True
    )


def _pct(parte: pd.Series, todo: pd.Series) -> pd.Series:
    return (parte / todo.where(todo > 0)) * 100


def _agregar(df: pd.DataFrame, chaves: tuple[str, ...], data) -> pd.DataFrame:
    """Market and cooperative amounts of each niche on one date."""
    mes = df[df.data == data]
    total = mes.groupby(list(chaves))[VALORES].sum()
    coop = mes[mes.cooperativa].groupby(list(chaves))[VALORES].sum()
    return total.join(coop, rsuffix="_coop").fillna(0.0)


def _datas(df: pd.DataFrame, data: dt.date | None) -> tuple:
    datas = sorted(df.data.unique())
    data = data or datas[-1]
    anteriores = [d for d in datas if d <= data]
    tres = anteriores[-4] if len(anteriores) >= 4 else None
    return data, tres, classes._ano_antes(pd.Series(datas), data)


def nichos(
    df: pd.DataFrame, chaves: tuple[str, ...], data: dt.date | None = None
) -> pd.DataFrame:
    """One row per niche: size, cooperative share, growth, default and arrears now and 3 months ago."""
    data, tres, ano = _datas(df, data)
    agora = _agregar(df, chaves, data)
    n = pd.DataFrame(index=agora.index)
    n["carteira"] = agora.carteira_ativa
    n["carteira_coop"] = agora.carteira_ativa_coop
    n["share"] = _pct(agora.carteira_ativa_coop, agora.carteira_ativa)
    n["inad"] = _pct(agora.carteira_inadimplencia, agora.carteira_ativa)
    n["inad_coop"] = _pct(agora.carteira_inadimplencia_coop, agora.carteira_ativa_coop)
    n["atraso"] = _pct(agora.vencido_15_90, agora.carteira_ativa)
    n["atraso_coop"] = _pct(agora.vencido_15_90_coop, agora.carteira_ativa_coop)
    if ano is not None:
        antes = _agregar(df, chaves, ano).carteira_ativa.reindex(n.index)
        n["cresc_12m"] = (n.carteira / antes.where(antes > 0) - 1) * 100
    else:
        n["cresc_12m"] = float("nan")
    if tres is not None:
        t = _agregar(df, chaves, tres).reindex(n.index)
        n["atraso_3m"] = _pct(t.vencido_15_90, t.carteira_ativa)
        n["atraso_coop_3m"] = _pct(t.vencido_15_90_coop, t.carteira_ativa_coop)
    else:
        n["atraso_3m"] = n["atraso_coop_3m"] = float("nan")
    return n.reset_index()


def espaco(
    df: pd.DataFrame,
    chaves: tuple[str, ...],
    data: dt.date | None = None,
    *,
    uf: str | None = None,
    minimo: float | None = None,
) -> pd.DataFrame:
    """Niches with room to grow, largest room first.

    A niche qualifies when the market grew in 12 months, its default rate is at
    most the national one for the same class and product, and the cooperatives'
    share is below their national share there. `espaco` is how much their
    portfolio would grow (R$) at the national share.
    """
    n = nichos(df, chaves, data)
    resto = [c for c in chaves if c != "uf"]
    brasil = (
        nichos(df, tuple(resto), data)
        if resto
        else nichos(df.assign(_todo=1), ("_todo",), data)
    )
    ref = brasil[[*resto, "share", "inad"]].rename(
        columns={"share": "share_ref", "inad": "inad_ref"}
    )
    n = (
        n.merge(ref, on=resto, how="left")
        if resto
        else n.assign(share_ref=ref.share_ref.iloc[0], inad_ref=ref.inad_ref.iloc[0])
    )
    n = _acionaveis(n, chaves, uf)
    minimo = MINIMO_MERCADO if minimo is None else minimo
    n = n[
        (n.carteira >= minimo)
        & (n.cresc_12m > 0)
        & (n.inad <= n.inad_ref)
        & (n.share < n.share_ref)
    ].copy()
    n["espaco"] = n.carteira * (n.share_ref - n.share) / 100
    return n.sort_values("espaco", ascending=False, ignore_index=True)


def alertas(
    df: pd.DataFrame,
    chaves: tuple[str, ...],
    data: dt.date | None = None,
    *,
    sinal: str = "mercado",
    uf: str | None = None,
    minimo: float | None = None,
) -> pd.DataFrame:
    """Niches whose 15-to-90-day arrears rate rose in 3 months.

    `delta` is the rise in p.p. and `impacto` the amount (R$) it represents on
    the current portfolio; the list is ranked by `impacto`, so a large niche
    with a real rise comes before a small one with a noisy jump.

    The rise comes before default: in the 2025-2026 data, the niches with the
    largest rises had markedly higher default three months later.
    """
    n = _acionaveis(nichos(df, chaves, data), chaves, uf)
    if sinal == "cooperativas":
        tamanho, agora, antes = n.carteira_coop, n.atraso_coop, n.atraso_coop_3m
        minimo = MINIMO_COOP if minimo is None else minimo
    else:
        tamanho, agora, antes = n.carteira, n.atraso, n.atraso_3m
        minimo = MINIMO_MERCADO if minimo is None else minimo
    n = n.assign(delta=agora - antes, impacto=(agora - antes) * tamanho / 100)
    n = n[(tamanho >= minimo) & (n.delta > 0)]
    return n.sort_values("impacto", ascending=False, ignore_index=True)


def _acionaveis(
    n: pd.DataFrame, chaves: tuple[str, ...], uf: str | None
) -> pd.DataFrame:
    for coluna in chaves:
        n = n[~n[coluna].isin(SOBRAS)]
    return n[n.uf == uf] if uf else n


def serie_nicho(df: pd.DataFrame, chave: dict) -> pd.DataFrame:
    """Monthly arrears and default of one niche, market and cooperatives."""
    for coluna, valor in chave.items():
        df = df[df[coluna] == valor]
    total = df.groupby("data")[VALORES].sum()
    coop = df[df.cooperativa].groupby("data")[VALORES].sum().reindex(total.index)
    return pd.DataFrame(
        {
            "atraso": _pct(total.vencido_15_90, total.carteira_ativa),
            "inad": _pct(total.carteira_inadimplencia, total.carteira_ativa),
            "atraso_coop": _pct(coop.vencido_15_90, coop.carteira_ativa),
            "inad_coop": _pct(coop.carteira_inadimplencia, coop.carteira_ativa),
        }
    ).reset_index()
