"""OpenBB explorer: every function of the local API as a CLI-like tree (plan 19).

The catalog comes from the API itself (`widgets.json` for functions and
parameters, `openapi.json` for the response columns), so new functions show
up without code changes.
"""

import functools
from dataclasses import dataclass, field

import requests

PREFIXO = "/api/v1/"
PESADOS = {"oecd"}  # first call loads ~1.6 GB into the API (see 04-aprendizados)
# Default order of the provider list: Brazilian sources, then open ones; heavy or keyed last.
PREFERIDOS = ("bcb", "ibge", "tesouro", "cvm", "receita", "imf", "ecb", "federal_reserve", "us_treasury", "sec", "cboe",
              "finra", "cftc", "nasdaq", "tmx", "jodi", "deribit", "famafrench", "government_us", "padrão")  # fmt: skip
TIPOS = {"text", "date", "number", "boolean", "tabs", "endpoint"}


@dataclass(frozen=True)
class Parametro:
    """One input of a function, normalized for the form."""

    nome: str
    rotulo: str
    tipo: str  # text, date, number, boolean, opcoes, endpoint
    valor: object = None
    opcoes: list[tuple[str, object]] = field(default_factory=list)
    multi: bool = False
    descricao: str = ""
    obrigatorio: bool = False
    visivel: bool = True


@dataclass(frozen=True)
class Funcao:
    """One API route with its variants by data provider."""

    endpoint: str
    caminho: tuple[str, ...]
    nome: str
    descricao: str
    categoria: str
    variantes: dict[str, list[Parametro]]  # provider → parameters

    @property
    def provedores(self) -> list[str]:
        """Providers available for this function."""

        def ordem(p: str) -> tuple:
            return (
                PREFERIDOS.index(p)
                if p in PREFERIDOS
                else len(PREFERIDOS) + (p in PESADOS),
                p,
            )

        return sorted(self.variantes, key=ordem)

    def pesada(self, provedor: str) -> bool:
        """Whether running with this provider is known to be heavy for the API."""
        return provedor in PESADOS


def normalizar(bruto: dict) -> Parametro | None:
    """Widget parameter → Parametro (None when it has no name)."""
    nome = bruto.get("paramName")
    if not nome:
        return None
    opcoes = [
        (str(o.get("label", o.get("value"))), o.get("value"))
        for o in bruto.get("options") or []
    ]
    tipo = bruto.get("type") or "text"
    if opcoes and tipo in ("text", "tabs", "number"):
        tipo = "opcoes"
    elif tipo not in TIPOS:
        tipo = "text"
    return Parametro(
        nome=nome,
        rotulo=bruto.get("label") or nome.replace("_", " ").capitalize(),
        tipo=tipo,
        valor=bruto.get("value"),
        opcoes=opcoes,
        multi=bool(bruto.get("multiSelect")),
        descricao=bruto.get("description") or "",
        obrigatorio=bruto.get("optional") is False,
        visivel=bruto.get("show", True) is not False and nome != "provider",
    )


def montar(widgets: dict) -> dict[str, Funcao]:
    """Group widgets by endpoint; each provider keeps its own parameter list."""
    funcoes: dict[str, dict] = {}
    for w in widgets.values():
        endpoint = w.get("endpoint", "")
        if not endpoint.startswith(PREFIXO):
            continue
        params = [p for p in (normalizar(b) for b in w.get("params", [])) if p]
        provedor = (
            next((p.valor for p in params if p.nome == "provider"), None) or "padrão"
        )
        item = funcoes.setdefault(
            endpoint,
            {
                "nome": w.get("name", endpoint),
                "descricao": w.get("description", ""),
                "categoria": w.get("category", ""),
                "variantes": {},
            },  # fmt: skip
        )
        item["variantes"][str(provedor)] = params
    return {
        e: Funcao(
            e,
            tuple(e[len(PREFIXO) :].strip("/").split("/")),
            d["nome"],
            d["descricao"],
            d["categoria"],
            d["variantes"],
        )
        for e, d in funcoes.items()
    }


def filhos(
    funcoes: dict[str, Funcao], caminho: tuple[str, ...]
) -> tuple[list[tuple[str, int]], list[Funcao]]:
    """Sub-folders (with how many functions below) and functions at one level."""
    n = len(caminho)
    pastas: dict[str, int] = {}
    aqui = []
    for f in funcoes.values():
        if f.caminho[:n] != caminho or len(f.caminho) == n:
            continue
        if len(f.caminho) == n + 1:
            aqui.append(f)
        else:
            pastas[f.caminho[n]] = pastas.get(f.caminho[n], 0) + 1
    # a segment can be both a folder and a function (e.g. equity/price vs equity/price/quote)
    return sorted(pastas.items()), sorted(aqui, key=lambda f: f.caminho)


def buscar(funcoes: dict[str, Funcao], texto: str, limite: int = 40) -> list[Funcao]:
    """Functions whose path, name or description contain every word of `texto`."""
    palavras = texto.lower().split()
    achadas = [
        f for f in funcoes.values()
        if all(p in " ".join([*f.caminho, f.nome, f.descricao]).lower() for p in palavras)
    ]  # fmt: skip
    return sorted(achadas, key=lambda f: (len(f.caminho), f.caminho))[:limite]


def colunas(
    openapi: dict, endpoint: str, provedor: str | None = None
) -> list[tuple[str, str, str]]:
    """Response columns (name, type, description) of an endpoint from the OpenAPI schema.

    When the schema has one alternative per provider (`oneOf`), the one whose
    name contains the provider is used; otherwise the first.
    """
    esquemas = openapi.get("components", {}).get("schemas", {})

    def resolver(no: dict) -> dict:
        while "$ref" in no:
            no = esquemas.get(no["$ref"].rsplit("/", 1)[-1], {})
        return no

    try:
        resposta = openapi["paths"][endpoint]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
    except KeyError:
        return []
    resultados = resolver(resposta).get("properties", {}).get("results", {})
    for opcao in resultados.get("anyOf", [resultados]):
        itens = resolver(opcao).get("items") or (opcao if "$ref" in opcao else None)
        if itens and "oneOf" in itens:
            alternativas = itens["oneOf"]
            escolhida = next(
                (
                    a
                    for a in alternativas
                    if provedor and provedor.lower() in a.get("$ref", "").lower()
                ),
                alternativas[0],
            )
            itens = escolhida
        if itens:
            dados = resolver(itens)
            saida = []
            for nome, prop in dados.get("properties", {}).items():
                tipos = [
                    t.get("type")
                    for t in prop.get("anyOf", [prop])
                    if t.get("type") != "null"
                ]
                tipo = prop.get("format") or (tipos[0] if tipos else "string")
                saida.append((nome, tipo or "string", prop.get("description", "")))
            return saida
    return []


@functools.cache
def _baixar(base: str, arquivo: str) -> dict:
    resposta = requests.get(f"{base}/{arquivo}", timeout=60)
    resposta.raise_for_status()
    return resposta.json()


def catalogo(api_base: str) -> tuple[dict[str, Funcao], dict]:
    """Functions and the OpenAPI document of the local API (cached per process)."""
    raiz = api_base.split(PREFIXO.rstrip("/"), maxsplit=1)[0].rstrip("/")
    return montar(_baixar(raiz, "widgets.json")), _baixar(raiz, "openapi.json")


class FaltaCredencial(Exception):
    """The provider needs an API key that this installation does not have."""


class ErroExecucao(Exception):
    """The function ran and failed (bad parameter, source down, no data)."""


def executar(
    api_base: str, endpoint: str, params: dict, timeout: int = 150
) -> list[dict]:
    """Run a function on the local API and return its rows."""
    raiz = api_base.split(PREFIXO.rstrip("/"), maxsplit=1)[0].rstrip("/")
    limpos = {k: v for k, v in params.items() if v not in (None, "", [])}
    limpos = {
        k: ",".join(map(str, v)) if isinstance(v, list) else v
        for k, v in limpos.items()
    }
    try:
        resposta = requests.get(f"{raiz}{endpoint}", params=limpos, timeout=timeout)
    except requests.RequestException as error:
        raise ErroExecucao(f"a API não respondeu: {error}") from error
    if resposta.ok:
        corpo = resposta.json()
        resultados = corpo.get("results") if isinstance(corpo, dict) else corpo
        if not resultados:
            raise ErroExecucao("a função não devolveu dados para estes parâmetros")
        return resultados if isinstance(resultados, list) else [resultados]
    try:
        detalhe = resposta.json().get("detail", resposta.text)
    except ValueError:
        detalhe = resposta.text
    texto = detalhe if isinstance(detalhe, str) else str(detalhe)
    if (
        "credential" in texto.lower()
        or "api key" in texto.lower()
        or "api_key" in texto.lower()
    ):
        raise FaltaCredencial(texto)
    raise ErroExecucao(texto[:400])
