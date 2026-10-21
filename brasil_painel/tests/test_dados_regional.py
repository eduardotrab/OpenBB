"""Map indicators computed from the regional store."""

import datetime as dt
import json

import pandas as pd
import pytest

from brasil_painel.dados import regional
from brasil_painel.regional import armazem, scr

AGO, AGO_ANTES = dt.date(2026, 8, 31), dt.date(2025, 8, 31)


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    linhas = []
    for data, fator in ((AGO_ANTES, 1.0), (AGO, 2.0)):
        for uf, coop, cliente, ativa, inad in [
            ("MG", True, "PF", 100.0, 10.0),
            ("MG", False, "PF", 300.0, 6.0),
            ("MG", False, "PJ", 600.0, 6.0),
            ("SP", False, "PF", 1000.0, 50.0),
        ]:
            linhas.append(
                dict(
                    data=data,
                    uf=uf,
                    cooperativa=coop,
                    cliente=cliente,
                    carteira_ativa=ativa * fator,
                    carteira_inadimplencia=inad,
                    vencido_15_90=0.0,
                )
            )
    armazem.gravar(pd.DataFrame(linhas), "scr_uf", scr.SCHEMA)
    pop = pd.DataFrame(
        [
            dict(data=dt.date(2026, 1, 1), uf=u, indicador="populacao", valor=v)
            for u, v in (("MG", 10.0), ("SP", 20.0), ("BR", 30.0))
        ]
    )
    armazem.gravar(pop, "populacao_uf", armazem.SCHEMA_LONGO)
    des = pd.DataFrame(
        [
            dict(data=dt.date(2026, 6, 1), uf=u, indicador="desemprego", valor=v)
            for u, v in (("MG", 3.8), ("SP", 5.9), ("BR", 5.4))
        ]
    )
    armazem.gravar(des, "desemprego_uf", armazem.SCHEMA_LONGO)
    return tmp_path


def test_default_rate_by_uf_and_brazil(loja):
    df = regional.serie("inadimplencia", cliente="todos", segmento="todos")
    ago = df[df.data == AGO].set_index("uf").valor
    assert ago["MG"] == pytest.approx(22 / 2000 * 100)
    assert ago["BR"] == pytest.approx(72 / 4000 * 100)


def test_filters_by_client_and_cooperatives(loja):
    df = regional.serie("inadimplencia", cliente="PF", segmento="cooperativas")
    ago = df[df.data == AGO].set_index("uf").valor
    assert ago.to_dict() == pytest.approx({"MG": 5.0, "BR": 5.0})


def test_cooperative_share_and_per_capita(loja):
    share = regional.serie("participacao_coop", cliente="todos", segmento="todos")
    assert share[
        (share.data == AGO) & (share.uf == "MG")
    ].valor.item() == pytest.approx(10.0)
    per_capita = regional.serie(
        "carteira_per_capita", cliente="todos", segmento="todos"
    )
    assert per_capita[
        (per_capita.data == AGO) & (per_capita.uf == "BR")
    ].valor.item() == pytest.approx(4000 / 30)


def test_latest_snapshot_with_brazil_and_12_month_change(loja):
    foto = regional.retrato(regional.serie("carteira_per_capita", "todos", "todos"))
    assert foto.data == AGO
    assert foto.brasil == pytest.approx(4000 / 30)
    assert foto.valores["SP"] == pytest.approx(100.0)
    assert foto.variacao_12m["SP"] == pytest.approx(50.0)


def test_ranking_puts_brazil_in_its_place(loja):
    foto = regional.retrato(regional.serie("desemprego", "todos", "todos"))
    assert [uf for uf, _ in regional.ranking(foto)] == ["SP", "BR", "MG"]


def test_missing_dataset_raises_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_DADOS_DIR", str(tmp_path))
    with pytest.raises(regional.DadosAusentes, match="painel-dados atualizar"):
        regional.serie("pix_pago_pf", "todos", "todos")


def test_catalog_flags_polarity():
    assert regional.INDICADORES["inadimplencia"].divergente
    assert not regional.INDICADORES["carteira_per_capita"].divergente
    assert regional.INDICADORES["inadimplencia"].filtros == (
        "cliente",
        "segmento",
        "classe",
        "produto",
    )


def _callback(cliente_http, saidas, entradas, mudou=()):
    """POST to Dash's callback endpoint, as the browser does."""
    ids = [f"{i}.{p}" for i, p in saidas]
    output = ids[0] if len(ids) == 1 else ".." + "...".join(ids) + ".."
    payload = {
        "output": output,
        # Dash expects a single output as an object, several as a list
        "outputs": (
            [{"id": i, "property": p} for i, p in saidas]
            if len(saidas) > 1
            else {"id": saidas[0][0], "property": saidas[0][1]}
        ),
        "inputs": [{"id": i, "property": p, "value": v} for i, p, v in entradas],
        "changedPropIds": list(mudou),
    }
    return cliente_http.post("/_dash-update-component", json=payload)


def test_map_callback_draws_states_ranking_brazil_and_the_state_panel(loja):
    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    http = create_app(Settings(users_file=None)).server.test_client()
    resposta = _callback(
        http,
        [
            ("mapa-grafico", "figure"),
            ("mapa-cabecalho", "children"),
            ("mapa-ranking", "children"),
            ("mapa-painel", "children"),
        ],
        [
            ("mapa-indicador", "value", "inadimplencia"),
            ("mapa-cliente", "value", "todos"),
            ("mapa-segmento", "value", "todos"),
            ("mapa-classe", "value", ""),
            ("mapa-produto", "value", ""),
            ("filtros", "data", {"uf": "MG", "data": ""}),
        ],
    )
    assert resposta.status_code == 200
    texto = json.dumps(resposta.get_json(), ensure_ascii=False)
    assert "choropleth" in texto
    assert "linha-brasil" in texto and "linha-escolhida" in texto
    assert "Minas Gerais" in texto and "Posição:" in texto
    assert "Dado de ago/2026" in texto


def test_clicking_a_state_sets_the_global_uf_filter(loja):
    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    http = create_app(Settings(users_file=None)).server.test_client()
    resposta = _callback(
        http,
        [("filtro-uf", "value")],
        [("mapa-grafico", "clickData", {"points": [{"location": "35"}]})],
        mudou=["mapa-grafico.clickData"],
    )
    assert resposta.status_code == 200, resposta.get_data(as_text=True)[:300]
    assert resposta.get_json()["response"]["filtro-uf"]["value"] == "SP"
