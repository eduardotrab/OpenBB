"""Brazilian number and date formatting."""

import datetime as dt

MESES = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]


def numero(valor: float, casas: int = 2, sinal: bool = False) -> str:
    """1234.5 → '1.234,50' (with '+' when `sinal` and positive)."""
    texto = f"{valor:{'+' if sinal else ''},.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def data(valor: dt.date, mensal: bool = False) -> str:
    """'20/10/2026', or 'set/2026' for monthly series."""
    if mensal:
        return f"{MESES[valor.month - 1]}/{valor.year}"
    return valor.strftime("%d/%m/%Y")
