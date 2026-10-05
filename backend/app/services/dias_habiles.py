"""Aritmética de días hábiles — `US-47` / RN-19.

La ventana de Calidad se cuenta en **días hábiles**: de lunes a viernes. Los
feriados de Costa Rica **no se descuentan todavía**: no hay un calendario de
feriados en el sistema y la ventana ya es un rango de 7 a 15 días, así que un
feriado mueve el extremo un día dentro de una incertidumbre de ocho.
"""

from __future__ import annotations

import datetime as dt

#: `date.weekday()`: lunes es 0, sábado 5 y domingo 6.
_SABADO = 5


def es_habil(fecha: dt.date) -> bool:
    return fecha.weekday() < _SABADO


def sumar_dias_habiles(fecha: dt.date, dias: int) -> dt.date:
    """`fecha` más `dias` días hábiles. El día de partida no cuenta.

    Recibido un viernes, el primer día hábil de la ventana es el lunes.
    """
    if dias < 0:
        raise ValueError("Los días hábiles a sumar no pueden ser negativos.")
    resultado = fecha
    restantes = dias
    while restantes:
        resultado += dt.timedelta(days=1)
        if es_habil(resultado):
            restantes -= 1
    return resultado


__all__ = ["es_habil", "sumar_dias_habiles"]
