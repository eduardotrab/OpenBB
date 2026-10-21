"""The FinScope palette is checked by computation, not by eye."""

import pytest

from brasil_painel import marca


def test_known_contrast_values():
    assert marca.contraste("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert marca.contraste(marca.VERDE_ESCURO, marca.BRANCO) > 13


def test_categorical_palette_passes_adjacent_pairs():
    assert marca.problemas(marca.CATEGORICA) == []


def test_the_close_pair_is_kept_apart():
    """Medium and light green fail as neighbours, so they never sit side by side."""
    i, j = (
        marca.CATEGORICA.index(marca.VERDE_MEDIO),
        marca.CATEGORICA.index(marca.VERDE_CLARO),
    )
    assert abs(i - j) > 1
    assert marca.problemas([marca.VERDE_MEDIO, marca.VERDE_CLARO])


@pytest.mark.parametrize("serie", [marca.COOPERATIVAS, marca.SISTEMA])
def test_brazil_baseline_stays_distinct_from_main_series(serie):
    normal, cvd = marca.pior_delta(marca.BRASIL, serie)
    assert normal >= 15 and cvd >= 8


def test_low_contrast_marks_are_flagged_unless_labelled():
    assert marca.problemas(["#DDDDDD", marca.VERDE_ESCURO])
    assert not any("contraste" in e for e in marca.problemas(marca.CATEGORICA))


def test_text_colors_meet_wcag_aa():
    assert marca.contraste(marca.TEXTO, marca.FUNDO) >= 4.5
    assert marca.contraste(marca.TEXTO_SUAVE, marca.BRANCO) >= 4.5
    assert marca.contraste(marca.BRANCO, marca.VERDE_ESCURO) >= 4.5


def test_sequential_ramp_gets_darker():
    from brasil_painel.marca import _linear

    luz = [sum(_linear(c)) for c in marca.SEQUENCIAL]
    assert luz == sorted(luz, reverse=True)
