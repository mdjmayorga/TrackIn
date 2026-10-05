"""Pruebas de la aritmética de días hábiles — `US-47` / RN-19."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.dias_habiles import es_habil, sumar_dias_habiles

MARTES = dt.date(2026, 9, 29)
VIERNES = dt.date(2026, 10, 2)
SABADO = dt.date(2026, 10, 3)


@pytest.mark.parametrize(
    ("fecha", "dias", "esperado"),
    [
        (MARTES, 0, MARTES),
        (MARTES, 3, dt.date(2026, 10, 2)),
        (MARTES, 4, dt.date(2026, 10, 5)),
        (MARTES, 7, dt.date(2026, 10, 8)),
        (MARTES, 15, dt.date(2026, 10, 20)),
        (VIERNES, 1, dt.date(2026, 10, 5)),
        (SABADO, 1, dt.date(2026, 10, 5)),
    ],
)
def test_suma_saltando_fines_de_semana(fecha, dias, esperado) -> None:
    assert sumar_dias_habiles(fecha, dias) == esperado


def test_el_fin_de_semana_no_es_habil() -> None:
    assert [es_habil(VIERNES + dt.timedelta(days=n)) for n in range(4)] == [
        True,
        False,
        False,
        True,
    ]


def test_no_se_restan_dias() -> None:
    with pytest.raises(ValueError, match="negativos"):
        sumar_dias_habiles(MARTES, -1)
