"""Release calendar: Copom (static file), Focus (weekly rule) and IBGE (calendar API).

CAGED has no public release calendar API; it is left out (see the plan log).
"""

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import requests
import tomllib

from brasil_painel.dados.formato import MESES

COPOM_FILE = Path(__file__).with_name("copom.toml")
IBGE_CALENDARIO = "https://servicodados.ibge.gov.br/api/v3/calendario/"
# Fixed-date national holidays (month, day); movable ones (Carnaval, Corpus Christi) are not handled.
FERIADOS_FIXOS = {
    (1, 1),
    (4, 21),
    (5, 1),
    (9, 7),
    (10, 12),
    (11, 2),
    (11, 15),
    (11, 20),
    (12, 25),
}

# (substring of the IBGE title, short label); order matters: specific first.
IBGE_INDICADORES = [
    ("Preços ao Consumidor Amplo 15", "IPCA-15"),
    ("Preços ao Consumidor Amplo", "IPCA"),
    ("Índice Nacional de Preços ao Consumidor", "INPC"),
    ("Amostra de Domicílios Contínua", "PNAD Contínua"),
    ("Contas Nacionais Trimestrais", "PIB trimestral"),
    ("Pesquisa Mensal de Comércio", "Pesquisa Mensal de Comércio"),
    ("Pesquisa Mensal de Serviços", "Pesquisa Mensal de Serviços"),
    ("Pesquisa Industrial Mensal", "Produção industrial"),
    ("Levantamento Sistemático da Produção Agrícola", "Safra (LSPA)"),
]


@dataclass(frozen=True)
class Evento:
    """One scheduled release."""

    data: dt.date
    hora: str | None
    titulo: str
    fonte: str


def _hora(texto: str) -> str:
    """'12:00:00' → '12h'; '09:30:00' → '9h30'."""
    h, m = (int(x) for x in texto.split(":")[:2])
    return f"{h}h{m:02d}" if m else f"{h}h"


def eventos_copom(reunioes: list[list[str]]) -> list[Evento]:
    """Decision on the second day; minutes on the following Tuesday at 8h."""
    eventos = []
    for _, segundo_dia in reunioes:
        decisao = dt.date.fromisoformat(segundo_dia)
        ata = decisao + dt.timedelta(days=(1 - decisao.weekday()) % 7 or 7)
        eventos.append(
            Evento(decisao, "após 18h", "Decisão do Copom sobre a Selic", "BCB")
        )
        eventos.append(Evento(ata, "8h", "Ata do Copom", "BCB"))
    return eventos


def carregar_copom(path: Path = COPOM_FILE) -> list[Evento]:
    """Copom events from the versioned calendar file."""
    return eventos_copom(tomllib.loads(path.read_text(encoding="utf-8"))["reunioes"])


def _dia_util(dia: dt.date) -> dt.date:
    while dia.weekday() >= 5 or (dia.month, dia.day) in FERIADOS_FIXOS:
        dia += dt.timedelta(days=1)
    return dia


def eventos_focus(inicio: dt.date, fim: dt.date) -> list[Evento]:
    """Boletim Focus: every Monday, or the next business day after a fixed holiday."""
    segunda = inicio - dt.timedelta(days=inicio.weekday())
    eventos = []
    while segunda <= fim:
        dia = _dia_util(segunda)
        if inicio <= dia <= fim:
            eventos.append(Evento(dia, "manhã", "Boletim Focus", "BCB"))
        segunda += dt.timedelta(days=7)
    return eventos


def eventos_ibge(rows: list[dict]) -> list[Evento]:
    """Market-relevant IBGE releases, with the reference month in the label."""
    eventos = []
    for row in rows:
        if row.get("tipo") != "Divulgação de Indicadores":
            continue
        rotulo = next(
            (r for chave, r in IBGE_INDICADORES if chave in row["titulo"]), None
        )
        if rotulo is None:
            continue
        mes, ano = (
            row.get("mes_referencia_inicio") or 0,
            row.get("ano_referencia_inicio") or 0,
        )
        if mes and ano:
            rotulo = f"{rotulo} ({MESES[mes - 1]}/{ano})"
        quando = dt.datetime.strptime(row["data_divulgacao"], "%d/%m/%Y %H:%M:%S")
        eventos.append(
            Evento(quando.date(), _hora(quando.strftime("%H:%M:%S")), rotulo, "IBGE")
        )
    return eventos


def buscar_ibge(inicio: dt.date, fim: dt.date, timeout: float = 20) -> list[dict]:
    """Raw IBGE calendar items between two dates."""
    params = {
        "de": inicio.strftime("%m-%d-%Y"),
        "ate": fim.strftime("%m-%d-%Y"),
        "qtd": 300,
    }
    response = requests.get(IBGE_CALENDARIO, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json().get("items", [])


def proximos(eventos: list[Evento], hoje: dt.date, dias: int = 7) -> list[Evento]:
    """Events from today up to `dias` days ahead, in date order."""
    fim = hoje + dt.timedelta(days=dias)
    return sorted(
        (e for e in eventos if hoje <= e.data <= fim), key=lambda e: (e.data, e.titulo)
    )


def semana(
    hoje: dt.date | None = None, dias: int = 7
) -> tuple[list[Evento], list[str]]:
    """Events of the next `dias` days and the sources that failed."""
    hoje = hoje or dt.date.today()
    fim = hoje + dt.timedelta(days=dias)
    eventos = carregar_copom() + eventos_focus(hoje, fim)
    falhas = []
    try:
        eventos += eventos_ibge(buscar_ibge(hoje, fim))
    except (requests.RequestException, ValueError):
        falhas.append("IBGE")
    return proximos(eventos, hoje, dias), falhas
