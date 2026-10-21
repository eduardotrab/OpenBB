"""Every client class side by side, always against the Brazil total (plan 12)."""

import datetime as dt
from dataclasses import dataclass

from brasil_painel.dados import classes
from brasil_painel.regional import classes as cfg

GRUPOS = {"pf": "Pessoas", "pj": "Empresas"}


@dataclass(frozen=True)
class Linha:
    """One row of the comparison matrix."""

    grupo: str  # "Pessoas", "Empresas" or "Brasil"
    resumo: classes.ResumoClasse


def tabela(
    *, uf: str | None = None, produto: str | None = None, data: dt.date | None = None
) -> list[Linha]:
    """Brazil first, then the income classes and the company sizes."""
    filtros = {"uf": uf, "produto": produto, "data": data}
    linhas = [Linha("Brasil", classes.resumir_total(**filtros))]
    for grupo, nome in GRUPOS.items():
        principais = set(cfg.principais(grupo))
        linhas += [
            Linha(nome, r)
            for r in classes.todas(grupo, **filtros)
            if r.classe in principais
        ]
    return linhas


def rurais(
    *, uf: str | None = None, data: dt.date | None = None
) -> list[classes.ResumoRural]:
    """Brazil total of rural credit, then each producer size."""
    return [classes.resumir_rural(None, uf=uf, data=data)] + classes.todas_rurais(
        uf=uf, data=data
    )
