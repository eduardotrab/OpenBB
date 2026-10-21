"""Explorer screen: generated form, level-by-level list and the result block."""

import pandas as pd

from brasil_painel.dados import explorador
from brasil_painel.paginas import explorador as tela
from tests.test_explorador import WIDGETS


def _controle(div):
    return div.children[1]


def test_form_control_follows_the_parameter_type():
    cpi = explorador.montar(WIDGETS)["/api/v1/economy/cpi"]
    pais, data, _ = cpi.variantes["oecd"]
    lista = _controle(tela.campo(pais))
    assert (
        lista.multi
        and lista.value == ["brazil"]
        and lista.id == {"type": "exp-param", "nome": "country"}
    )
    assert _controle(tela.campo(data)).type == "date"
    harmonizado = _controle(tela.campo(cpi.variantes["imf"][0]))
    assert harmonizado.value == []
    simbolo = explorador.montar(WIDGETS)["/api/v1/equity/price/quote"].variantes[
        "padrão"
    ][0]
    assert "(obrigatório)" in tela.campo(simbolo).children[0].children


def test_list_shows_folders_then_functions_and_search():
    funcoes = explorador.montar(WIDGETS)
    raiz = tela.lista(funcoes, [], None)
    assert [b.id["alvo"] for b in raiz] == ["economy", "equity"]
    preco = tela.lista(funcoes, ["equity", "price"], None)
    assert [b.id["endpoint"] for b in preco] == [
        "/api/v1/equity/price/historical",
        "/api/v1/equity/price/quote",
    ]
    achadas = tela.lista(funcoes, [], "quote")
    assert achadas[0].children == "1 função encontrada"


def test_path_levels_are_clickable():
    itens = tela.trilha(["economy", "cpi"])
    assert [
        i.id["nivel"] for i in itens if hasattr(i, "id") and isinstance(i.id, dict)
    ] == [0, 1, 2]


def test_checkbox_value_becomes_true_text():
    ids = [
        {"type": "exp-param", "nome": "harmonized"},
        {"type": "exp-param", "nome": "country"},
    ]
    assert tela._parametros(ids, [["true"], ["brazil"]]) == {
        "harmonized": "true",
        "country": ["brazil"],
    }


def test_result_block_labels_the_origin():
    df = pd.DataFrame(
        {"date": pd.date_range("2025-01-01", periods=6, freq="MS"), "value": range(6)}
    )
    bloco = tela.resultado(df, "Dados de exemplo (fictícios)")
    assert bloco.children[0].children[0].children == "Dados de exemplo (fictícios)"


def test_long_help_is_cut_to_one_short_sentence():
    assert (
        tela.ajuda("Start date of the data. In YYYY-MM-DD format.")
        == "Start date of the data."
    )
    longa = tela.ajuda(
        "Frequency aggregation to convert high frequency data to lower frequency " * 4
    )
    assert len(longa) <= 121 and longa.endswith("…")
