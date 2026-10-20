"""News from the official feeds and the agro outlet, merged into one list."""

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass

from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient

BRASILIA = dt.timezone(dt.timedelta(hours=-3))

# (origin label, route, params)
FONTES = [
    (
        "BCB",
        "news/world",
        {"provider": "bcb", "category": "press_releases", "limit": 20},
    ),
    ("Copom", "news/world", {"provider": "bcb", "category": "copom", "limit": 5}),
    ("IBGE", "news/world", {"provider": "ibge", "limit": 20}),
    (
        "Agência Brasil",
        "news/rss",
        {"outlet": "gov_br", "source": "agencia_brasil_economia", "limit": 20},
    ),
    (
        "Agro (Canal Rural)",
        "news/rss",
        {"outlet": "agro", "source": "canal_rural", "limit": 20},
    ),
]


@dataclass(frozen=True)
class Noticia:
    """One headline."""

    titulo: str
    data: dt.datetime
    url: str
    origem: str


def parse_data(texto: str) -> dt.datetime:
    """ISO date → aware UTC datetime; naive values are Brasília time."""
    valor = dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=BRASILIA)
    return valor.astimezone(dt.timezone.utc)


def _chave(titulo: str) -> str:
    return re.sub(r"\s+", " ", titulo).strip().casefold()


def juntar(
    listas: list[list[Noticia]], limite: int = 40, por_origem: int = 10
) -> list[Noticia]:
    """Newest first; the same headline (normalised) or URL appears once.

    `por_origem` keeps a prolific outlet from crowding out the official sources.
    """
    vistos: set[str] = set()
    contagem: Counter[str] = Counter()
    resultado = []
    todas = sorted(
        (x for lista in listas for x in lista), key=lambda x: x.data, reverse=True
    )
    for noticia in todas:
        chaves = {_chave(noticia.titulo), noticia.url}
        if chaves & vistos or contagem[noticia.origem] >= por_origem:
            continue
        vistos |= chaves
        contagem[noticia.origem] += 1
        resultado.append(noticia)
    return resultado[:limite]


def coletar(client: OpenBBClient, limite: int = 40) -> tuple[list[Noticia], list[str]]:
    """Fetch every origin; returns the merged news and the origins that failed."""
    listas, falhas = [], []
    for origem, rota, params in FONTES:
        try:
            rows = client.get(rota, **params)
        except FonteIndisponivel:
            falhas.append(origem)
            continue
        listas.append(
            [
                Noticia(
                    titulo=" ".join(r["title"].split()),
                    data=parse_data(r["date"]),
                    url=r["url"],
                    origem=origem,
                )
                for r in rows
                if r.get("title") and r.get("date") and r.get("url")
            ]
        )
    return juntar(listas, limite), falhas
