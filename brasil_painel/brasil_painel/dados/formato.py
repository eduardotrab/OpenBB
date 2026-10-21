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


# (from, divisor, suffix): below 10 thousand the full integer reads better
ESCALAS = [(1e12, 1e12, "tri"), (1e9, 1e9, "bi"), (1e6, 1e6, "mi"), (1e4, 1e3, "mil")]


def compacto(valor: float, casas: int = 1) -> str:
    """7.72e12 → '7,7 tri'; 634500 → '634,5 mil'; below 10 thousand, the integer."""
    for limite, divisor, sufixo in ESCALAS:
        if abs(valor) >= limite:
            return f"{numero(valor / divisor, casas)} {sufixo}"
    return numero(valor, 0)
