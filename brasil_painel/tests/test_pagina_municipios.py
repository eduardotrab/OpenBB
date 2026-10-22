"""Municipal block of the map page."""

import json

from tests.test_dados_municipios import BH, loja  # noqa: F401 - pytest fixture


def _post(http, entradas):
    saidas = ["mun-titulo.children", "mun-vazio.style", "mun-conteudo.style", "mun-grafico.figure",
              "mun-contexto.children", "mun-ranking.children", "mun-painel.children"]  # fmt: skip
    payload = {
        "output": ".." + "...".join(saidas) + "..",
        "outputs": [
            {"id": s.split(".")[0], "property": s.split(".")[1]} for s in saidas
        ],
        "inputs": entradas,
        "changedPropIds": [],
    }
    return http.post("/_dash-update-component", json=payload).get_json()["response"]


def _entradas(uf, escolhido=None):
    return [
        {"id": "mun-indicador", "property": "value", "value": "pix_pj_pc"},
        {"id": "filtros", "property": "data", "value": {"uf": uf, "data": ""}},
        {"id": "mun-escolhido", "property": "data", "value": escolhido},
    ]


def test_municipal_block_follows_the_state_filter(loja):  # noqa: F811
    from brasil_painel.app import create_app
    from brasil_painel.config import Settings

    http = create_app(Settings(users_file=None)).server.test_client()
    sem_uf = _post(http, _entradas("BR"))
    assert sem_uf["mun-conteudo"]["style"] == {"display": "none"}
    mg = _post(http, _entradas("MG", BH))
    assert mg["mun-titulo"]["children"] == "Municípios de Minas Gerais"
    texto = json.dumps(mg, ensure_ascii=False)
    assert (
        "Belo Horizonte" in texto
        and "Mediana do estado" in texto
        and "choropleth" in texto
    )
