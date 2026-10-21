"""FinScope identity on the Sicoob palette: color roles and a palette validator.

The validator recomputes what the `dataviz` skill checks (Node is not installed
here): WCAG contrast against the surface and OKLab ΔE between series, with and
without color-vision deficiency (Machado et al. 2009, severity 1.0).
"""

import itertools
import math

NOME = "FinScope"
FONTE = 'Tahoma, Verdana, "DejaVu Sans", sans-serif'

# Brand (Sicoob identity guide)
TURQUESA = "#00AE9D"
VERDE_ESCURO = "#003641"
VERDE_MEDIO = "#7DB61C"
VERDE_CLARO = "#C9D200"
ROXO = "#49479D"
BRANCO = "#FFFFFF"

# Neutrals tinted toward the dark green, not pure gray
FUNDO = "#F2F6F6"
SUPERFICIE = BRANCO
BORDA = "#D5E0E1"
TEXTO = VERDE_ESCURO
TEXTO_SUAVE = "#5B6B70"

# Series roles. The order keeps the close pair (medium × light green) apart.
CATEGORICA = [TURQUESA, VERDE_ESCURO, VERDE_MEDIO, ROXO, VERDE_CLARO]
COOPERATIVAS = TURQUESA
SISTEMA = VERDE_ESCURO
BRASIL = TEXTO_SUAVE  # always dashed: secondary encoding for the baseline
SEQUENCIAL = ["#E0F5F2", "#9EDDD4", "#4CC3B5", TURQUESA, "#00796E", VERDE_ESCURO]
DIVERGENTE = [VERDE_ESCURO, "#4CA79C", "#EEF1F1", "#E9A07C", "#B4432C"]  # good ↔ bad

# Status (never reused as a series color; always with icon + label)
BOM, ATENCAO, ALERTA, CRITICO = "#0CA30C", "#FAB219", "#EC835A", "#D03B3B"

# Colors below 3:1 on white need a visible value label (as in the models).
EXIGEM_ROTULO = {TURQUESA, VERDE_MEDIO, VERDE_CLARO}

_CVD = {
    "protanopia": [
        [0.152286, 1.052583, -0.204868],
        [0.114503, 0.786281, 0.099216],
        [-0.003882, -0.048116, 1.051998],
    ],
    "deuteranopia": [
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.011820, 0.042940, 0.968881],
    ],
    "tritanopia": [
        [1.255528, -0.076749, -0.178779],
        [-0.078411, 0.930809, 0.147602],
        [0.004733, 0.691367, 0.303900],
    ],
}


def _linear(hex_: str) -> list[float]:
    canais = [int(hex_.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]


def contraste(a: str, b: str) -> float:
    """WCAG contrast ratio between two colors."""

    def luminancia(h: str) -> float:
        r, g, b_ = _linear(h)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_

    claro, escuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def _oklab(rgb: list[float]) -> tuple[float, float, float]:
    r, g, b = rgb
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    l_, m_, s_ = (math.copysign(abs(x) ** (1 / 3), x) for x in lms)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _simular(hex_: str, visao: str) -> list[float]:
    rgb = _linear(hex_)
    if visao == "normal":
        return rgb
    matriz = _CVD[visao]
    return [
        min(1.0, max(0.0, sum(matriz[i][j] * rgb[j] for j in range(3))))
        for i in range(3)
    ]


def delta_e(a: str, b: str, visao: str = "normal") -> float:
    """OKLab distance ×100 between two colors as seen with `visao`."""
    return 100 * math.dist(_oklab(_simular(a, visao)), _oklab(_simular(b, visao)))


def pior_delta(a: str, b: str) -> tuple[float, float]:
    """Return (normal ΔE, worst ΔE among the three deficiencies)."""
    return delta_e(a, b), min(delta_e(a, b, v) for v in _CVD)


def problemas(
    paleta: list[str], fundo: str = BRANCO, todos_os_pares: bool = False
) -> list[str]:
    """Rule violations of a categorical palette (empty list = passes).

    Adjacent pairs (or all pairs) need ΔE ≥ 15 normal and ≥ 8 with CVD;
    marks below 3:1 contrast must be in EXIGEM_ROTULO (labelled by design).
    """
    erros = []
    pares = (
        itertools.combinations(paleta, 2) if todos_os_pares else zip(paleta, paleta[1:])
    )
    for a, b in pares:
        normal, cvd = pior_delta(a, b)
        if normal < 15:
            erros.append(f"{a}×{b}: ΔE normal {normal:.1f} < 15")
        if cvd < 8:
            erros.append(f"{a}×{b}: ΔE daltonismo {cvd:.1f} < 8")
    for cor in paleta:
        if contraste(cor, fundo) < 3 and cor not in EXIGEM_ROTULO:
            erros.append(f"{cor}: contraste {contraste(cor, fundo):.2f} < 3 sem rótulo")
    return erros
