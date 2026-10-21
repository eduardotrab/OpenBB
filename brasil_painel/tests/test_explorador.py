"""OpenBB explorer: catalog tree, parameters and response columns."""

from brasil_painel.dados import explorador

WIDGETS = {
    "cpi_oecd": {"name": "CPI", "description": "Consumer prices.", "category": "Economy", "endpoint": "/api/v1/economy/cpi",
                 "params": [{"paramName": "country", "label": "Country", "type": "text", "value": "brazil",
                             "options": [{"label": "Brazil", "value": "brazil"}], "multiSelect": True},
                            {"paramName": "start_date", "type": "date", "value": None},
                            {"paramName": "provider", "value": "oecd", "show": False}]},
    "cpi_imf": {"name": "CPI", "endpoint": "/api/v1/economy/cpi",
                "params": [{"paramName": "harmonized", "type": "boolean", "value": False},
                           {"paramName": "provider", "value": "imf", "show": False}]},
    "quote": {"name": "Quote", "endpoint": "/api/v1/equity/price/quote", "params": [{"paramName": "symbol", "type": "text", "optional": False}]},
    "hist": {"name": "Historical", "endpoint": "/api/v1/equity/price/historical", "params": []},
    "outra": {"name": "Fora", "endpoint": "/outra/coisa", "params": []},
}  # fmt: skip


def test_tree_groups_providers_and_counts_leaves():
    funcoes = explorador.montar(WIDGETS)
    assert set(funcoes) == {
        "/api/v1/economy/cpi",
        "/api/v1/equity/price/quote",
        "/api/v1/equity/price/historical",
    }
    cpi = funcoes["/api/v1/economy/cpi"]
    assert (
        cpi.provedores == ["imf", "oecd"]
        and cpi.pesada("oecd")
        and not cpi.pesada("imf")
    )
    pastas, aqui = explorador.filhos(funcoes, ())
    assert pastas == [("economy", 1), ("equity", 2)] and aqui == []
    pastas, aqui = explorador.filhos(funcoes, ("equity", "price"))
    assert pastas == [] and [f.caminho[-1] for f in aqui] == ["historical", "quote"]


def test_parameters_are_normalized_for_the_form():
    cpi = explorador.montar(WIDGETS)["/api/v1/economy/cpi"]
    pais, data, provedor = cpi.variantes["oecd"]
    assert (pais.tipo, pais.multi, pais.opcoes) == (
        "opcoes",
        True,
        [("Brazil", "brazil")],
    )
    assert data.tipo == "date" and not provedor.visivel
    assert cpi.variantes["imf"][0].tipo == "boolean"
    simbolo = explorador.montar(WIDGETS)["/api/v1/equity/price/quote"].variantes[
        "padrão"
    ][0]
    assert simbolo.obrigatorio


def test_search_matches_every_word():
    funcoes = explorador.montar(WIDGETS)
    assert [f.nome for f in explorador.buscar(funcoes, "equity quote")] == ["Quote"]


def test_response_columns_come_from_openapi():
    openapi = {
        "paths": {"/api/v1/economy/cpi": {"get": {"responses": {"200": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/OBBject_Cpi"}}}}}}}},
        "components": {"schemas": {
            "OBBject_Cpi": {"properties": {"results": {"anyOf": [{"type": "array", "items": {"$ref": "#/components/schemas/CpiData"}}, {"type": "null"}]}}},
            "CpiData": {"properties": {"date": {"type": "string", "format": "date", "description": "Date."},
                                       "value": {"anyOf": [{"type": "number"}, {"type": "null"}], "description": "CPI."}}},
        }},
    }  # fmt: skip
    assert explorador.colunas(openapi, "/api/v1/economy/cpi") == [
        ("date", "date", "Date."),
        ("value", "number", "CPI."),
    ]
    assert explorador.colunas(openapi, "/nada") == []


def test_columns_pick_the_provider_alternative():
    openapi = {
        "paths": {"/api/v1/x": {"get": {"responses": {"200": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/O"}}}}}}}},
        "components": {"schemas": {
            "O": {"properties": {"results": {"anyOf": [{"type": "array", "items": {"oneOf": [
                {"$ref": "#/components/schemas/OECDData"}, {"$ref": "#/components/schemas/ImfData"}]}}]}}},
            "OECDData": {"properties": {"a": {"type": "number"}}},
            "ImfData": {"properties": {"b": {"type": "string"}}},
        }},
    }  # fmt: skip
    assert explorador.colunas(openapi, "/api/v1/x", "imf") == [("b", "string", "")]
    assert explorador.colunas(openapi, "/api/v1/x") == [("a", "number", "")]
