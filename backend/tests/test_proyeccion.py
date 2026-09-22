"""Pruebas de `app.services.proyeccion` — `US-09` / RF-10, RN-01, RN-14.

Corren **sin base de datos** a propósito. RN-01 es una regla de negocio, no una
consulta: poder ejercitarla con una tabla de casos es lo que permite cubrir los
bordes que importan —la precedencia de RN-14, el destino sin lead time, el
ajuste manual negativo— sin levantar PostgreSQL para cada uno.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.proyeccion import (
    ORIGEN_ATA_CONFIRMADA,
    ORIGEN_ATA_INFERIDA,
    ORIGEN_ETA_DECLARADA,
    ORIGEN_ETA_FUENTE,
    PRECEDENCIA,
    calcular,
)

ETA = dt.date(2026, 10, 1)


# --- La suma de RN-01 ------------------------------------------------------


def test_la_formula_es_base_mas_lead_time_mas_ajuste() -> None:
    """RN-01: *«ETA o ATA + lead time del destino + un ajuste manual»*."""
    resultado = calcular(eta_fuente=ETA, lead_time_dias=5, ajuste_manual_dias=2)

    assert resultado.fecha == dt.date(2026, 10, 8)
    assert bool(resultado) is True


def test_sin_ajuste_manual_la_suma_es_solo_el_lead_time() -> None:
    assert calcular(eta_fuente=ETA, lead_time_dias=5).fecha == dt.date(2026, 10, 6)


def test_el_ajuste_manual_puede_adelantar() -> None:
    """`ajuste_manual_dias` es un entero con signo: se usa para corregir en las
    dos direcciones, no solo para añadir holgura."""
    assert calcular(eta_fuente=ETA, lead_time_dias=5, ajuste_manual_dias=-3).fecha == dt.date(
        2026, 10, 3
    )


def test_un_lead_time_de_cero_deja_la_fecha_base() -> None:
    assert calcular(eta_fuente=ETA, lead_time_dias=0).fecha == ETA


# --- Precedencia de RN-14: lo ocurrido manda sobre lo estimado -------------


def test_la_ata_confirmada_gana_a_todo() -> None:
    """RN-14. Una persona confirmó el arribo: es un hecho y está auditado."""
    resultado = calcular(
        ata_confirmada=dt.date(2026, 9, 1),
        ata_inferida=dt.date(2026, 9, 5),
        eta_fuente=dt.date(2026, 9, 10),
        eta_declarada=dt.date(2026, 9, 15),
        lead_time_dias=5,
    )

    assert resultado.origen == ORIGEN_ATA_CONFIRMADA
    assert resultado.base == dt.date(2026, 9, 1)


def test_la_ata_inferida_gana_a_las_dos_eta() -> None:
    """Deducido de un hito o una geocerca sigue siendo un hecho (RN-05)."""
    resultado = calcular(
        ata_inferida=dt.date(2026, 9, 5),
        eta_fuente=dt.date(2026, 9, 10),
        eta_declarada=dt.date(2026, 9, 15),
        lead_time_dias=5,
    )

    assert resultado.origen == ORIGEN_ATA_INFERIDA


def test_la_eta_de_la_fuente_gana_a_la_declarada() -> None:
    """La declarada la mantiene una persona a mano y no se actualiza sola.

    Es, literalmente, el campo que este sistema existe para reemplazar.
    """
    resultado = calcular(
        eta_fuente=dt.date(2026, 9, 10),
        eta_declarada=dt.date(2026, 9, 15),
        lead_time_dias=5,
    )

    assert resultado.origen == ORIGEN_ETA_FUENTE


def test_la_declarada_se_usa_cuando_es_lo_unico_que_hay() -> None:
    """Hoy es el caso de las pocas líneas del archivo que traen `ETA CR`."""
    resultado = calcular(eta_declarada=dt.date(2026, 9, 15), lead_time_dias=5)

    assert resultado.origen == ORIGEN_ETA_DECLARADA
    assert resultado.fecha == dt.date(2026, 9, 20)


def test_la_precedencia_declarada_es_la_que_se_aplica() -> None:
    """Si alguien reordena `PRECEDENCIA`, el comportamiento cambia con ella.

    Fija el orden como contrato, no como detalle de implementación.
    """
    assert PRECEDENCIA == (
        ORIGEN_ATA_CONFIRMADA,
        ORIGEN_ATA_INFERIDA,
        ORIGEN_ETA_FUENTE,
        ORIGEN_ETA_DECLARADA,
    )


def test_acepta_datetime_y_date_indistintamente() -> None:
    """Las ATA son `TIMESTAMPTZ` y la ETA declarada es `DATE`.

    La hora importa para auditar cuándo se supo algo, no para una fecha de
    disponibilidad: nadie planifica materiales con precisión de minutos.
    """
    con_hora = calcular(
        ata_confirmada=dt.datetime(2026, 9, 1, 18, 30, tzinfo=dt.UTC), lead_time_dias=5
    )
    con_fecha = calcular(ata_confirmada=dt.date(2026, 9, 1), lead_time_dias=5)

    assert con_hora.fecha == con_fecha.fecha == dt.date(2026, 9, 6)


# --- Cuándo NO hay fecha proyectada ----------------------------------------


def test_sin_ninguna_fecha_base_no_se_proyecta() -> None:
    """El caso mayoritario hoy: un pedido `SIN_TRACKING` sin ETA de nadie."""
    resultado = calcular(lead_time_dias=5)

    assert resultado.fecha is None
    assert resultado.origen is None
    assert bool(resultado) is False
    assert "no tiene ATA confirmada ni inferida" in resultado.motivo


def test_sin_lead_time_no_se_proyecta_aunque_haya_eta() -> None:
    """Tercer criterio de `US-09`.

    No se proyecta con un lead time supuesto: el tramo puerto→planta sigue
    pendiente con Planeación desde el 04/09.
    """
    resultado = calcular(eta_fuente=ETA, lead_time_dias=None)

    assert resultado.fecha is None
    assert resultado.motivo == "el destino no tiene lead time definido"
    # Conserva la base: se sabe de dónde habría salido si hubiera lead time.
    assert resultado.base == ETA
    assert resultado.origen == ORIGEN_ETA_FUENTE


def test_sin_base_y_sin_lead_time_manda_la_falta_de_base() -> None:
    """Se informa el primer obstáculo, no los dos: quien corrige necesita saber
    qué hacer primero, y conseguir la ETA es lo que desbloquea."""
    resultado = calcular(lead_time_dias=None)
    assert "no tiene ATA confirmada" in resultado.motivo


# --- El desglose que pide RF-05 --------------------------------------------


def test_el_desglose_explica_la_suma() -> None:
    """*«El desglose del cálculo que produjo la fecha proyectada»* (RF-05).

    Una fecha sin explicación no se puede discutir con quien la recibe.
    """
    desglose = calcular(eta_fuente=ETA, lead_time_dias=5, ajuste_manual_dias=2).desglose

    assert "2026-10-01" in desglose
    assert ORIGEN_ETA_FUENTE in desglose
    assert "5 d de lead time" in desglose
    assert "2 d de ajuste manual" in desglose
    assert "2026-10-08" in desglose


def test_el_desglose_omite_el_ajuste_cuando_es_cero() -> None:
    """Escribir «+ 0 d de ajuste manual» solo añade ruido."""
    assert "ajuste" not in calcular(eta_fuente=ETA, lead_time_dias=5).desglose


def test_el_desglose_explica_la_ausencia() -> None:
    desglose = calcular(lead_time_dias=5).desglose
    assert desglose.startswith("Sin fecha proyectada:")


# --- Inmutabilidad ---------------------------------------------------------


def test_la_proyeccion_no_se_retoca() -> None:
    """`frozen=True`: el resultado es evidencia del cálculo, no un borrador."""
    resultado = calcular(eta_fuente=ETA, lead_time_dias=5)
    with pytest.raises(AttributeError):
        resultado.fecha = dt.date(2030, 1, 1)  # type: ignore[misc]
