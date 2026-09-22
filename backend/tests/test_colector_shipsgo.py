"""Pruebas de `app.services.rastreo.colector_shipsgo` — `US-45`.

Contra la base y con los **payloads reales grabados**: lo que se verifica aquí
es que lo leído llega a donde tiene que llegar sin violar ningún `CHECK`, y que
un embarque sin posición se procesa igual en vez de perderse.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.historial_tracking import HistorialTracking
from app.services.rastreo import colector_shipsgo

_SALIDA = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
_MADUROS = _SALIDA / "06_payload_personal.json"
_PENDIENTES = _SALIDA / "07_pendientes_personal.json"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (_MADUROS.exists() and _PENDIENTES.exists()),
        reason="faltan los payloads grabados del spike TASK-28",
    ),
]

MAERSK_CON_POSICION = "MRSU8507472"
COSCO_SIN_POSICION = "TGBU4872990"


def _casos() -> dict[str, tuple[dict[str, Any], dict[str, Any] | None]]:
    casos: dict[str, tuple[dict[str, Any], dict[str, Any] | None]] = {}
    for archivo, clave in ((_MADUROS, "contenedor"), (_PENDIENTES, None)):
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        for embarque in datos["embarques"]:
            payload = embarque["payload_shipment"]
            nombre = (
                embarque[clave]
                if clave
                else (payload.get("container_number") or payload.get("awb_number"))
            )
            casos[nombre] = (payload, embarque.get("payload_geojson"))
    return casos


CASOS = _casos() if _MADUROS.exists() else {}


@pytest.fixture
async def elemento(sesion) -> ElementoRastreado:
    """Un contenedor seguido, sin datos todavía."""
    nuevo = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR",
        tracking_externo=MAERSK_CON_POSICION,
        via_transporte="MARITIMO",
    )
    sesion.add(nuevo)
    await sesion.flush()
    return nuevo


# --- Lo que se escribe en el elemento --------------------------------------


async def test_rellena_el_buque_y_su_imo(sesion, elemento) -> None:
    """El criterio de `US-45`, y la deuda que `US-02` dejó escrita el 08/09."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    resultado = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
    await sesion.flush()

    assert resultado.aplicada
    assert elemento.nombre == "POLAR BRASIL"  # la nave del tramo en curso
    assert elemento.imo == 9797216


async def test_guarda_la_eta_de_la_fuente(sesion, elemento) -> None:
    """Es el tercer escalón de la precedencia de RN-14 que consume `US-09`."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)

    assert elemento.eta_api is not None
    assert elemento.eta_api.date() == dt.date(2026, 9, 15)


async def test_no_inventa_una_ata_mientras_navega(sesion, elemento) -> None:
    """El embarque sigue `SAILING` y sus `ARRV` ocurridos son de transbordo."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)

    assert elemento.ata_api is None


async def test_marca_la_hora_de_la_ultima_consulta(sesion, elemento) -> None:
    """`US-23` la necesita para indicar la frescura de los datos."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]
    instante = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)

    await colector_shipsgo.procesar(sesion, elemento, shipment, geojson, instante=instante)

    assert elemento.ultima_actualizacion_api == instante


# --- La posición y el historial --------------------------------------------


async def test_la_posicion_llega_al_historial_y_al_elemento(sesion, elemento) -> None:
    """El mapa lee la desnormalizada del elemento (RF-20)."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    resultado = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
    await sesion.flush()

    assert resultado.posicion_registrada is True
    assert elemento.posicion_actual is not None
    filas = await sesion.scalar(
        select(func.count())
        .select_from(HistorialTracking)
        .where(HistorialTracking.id_elemento_rastreado == elemento.id)
    )
    assert filas == 1


async def test_el_payload_original_queda_guardado(sesion, elemento) -> None:
    """RF-21 / RNF-13, y hace falta de verdad: ShipsGo **archiva** lo entregado.

    Si no se guardara, la única copia de lo que la fuente dijo desaparecería
    cuando el embarque pase a `DELIVERED`.
    """
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
    await sesion.flush()

    registro = await sesion.scalar(
        select(HistorialTracking).where(HistorialTracking.id_elemento_rastreado == elemento.id)
    )
    assert registro is not None
    assert registro.payload_api["containers"], "el payload entero, no un resumen"


async def test_la_velocidad_y_el_rumbo_quedan_nulos(sesion, elemento) -> None:
    """ShipsGo **no los entrega**, y no hacen falta: RN-16 los quería para
    estimar la ETA y ésta llega ya calculada."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
    await sesion.flush()

    registro = await sesion.scalar(
        select(HistorialTracking).where(HistorialTracking.id_elemento_rastreado == elemento.id)
    )
    assert registro is not None
    assert registro.velocidad is None
    assert registro.rumbo is None


# --- Sin posición: el caso que NO se puede perder --------------------------


async def test_un_embarque_sin_posicion_se_procesa_igual(sesion) -> None:
    """Medido en el BL de COSCO: `current: null` en todas sus *features*.

    Es la diferencia con AIS: allí sin posición no hay nada que registrar; aquí
    la respuesta sigue trayendo hitos, ETA y transbordo.
    """
    elemento = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR",
        tracking_externo=COSCO_SIN_POSICION,
        via_transporte="MARITIMO",
    )
    sesion.add(elemento)
    await sesion.flush()
    shipment, geojson = CASOS[COSCO_SIN_POSICION]

    resultado = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
    await sesion.flush()

    assert resultado.aplicada is True
    assert resultado.posicion_registrada is False
    # Lo importante sí se guardó.
    assert elemento.eta_api is not None
    assert elemento.nombre == "MEDKON ZOE"
    assert elemento.posicion_actual is None


# --- El transbordo ---------------------------------------------------------


async def test_detecta_y_reporta_el_transbordo(sesion, elemento) -> None:
    """Insumo de `US-30`, que estaba especificada como captura manual."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]

    resultado = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)

    assert resultado.transbordo_detectado is True
    assert resultado.lectura is not None
    assert len(resultado.lectura.vehiculos) == 2


# --- El tercer estado ------------------------------------------------------


async def test_un_embarque_sin_madurar_no_se_aplica(sesion, elemento) -> None:
    """No es un fallo ni una respuesta vacía: hay que reintentarlo."""
    recien = {"id": 1, "status": "NEW", "route": None, "containers": []}

    resultado = await colector_shipsgo.procesar(sesion, elemento, recien)

    assert resultado.aplicada is False
    assert resultado.motivo == colector_shipsgo.DESCARTE_SIN_MADURAR
    assert elemento.eta_api is None


async def test_una_lectura_sin_hitos_ni_eta_se_descarta(sesion, elemento) -> None:
    vacio = {"id": 1, "status": "SAILING", "route": {}, "containers": [{"movements": []}]}

    resultado = await colector_shipsgo.procesar(sesion, elemento, vacio)

    assert resultado.aplicada is False
    assert resultado.motivo == colector_shipsgo.DESCARTE_SIN_DATOS


# --- Idempotencia ----------------------------------------------------------


async def test_procesar_dos_veces_no_duplica_el_historial(sesion, elemento) -> None:
    """El mismo instante es la misma lectura: la idempotencia de `US-04`."""
    shipment, geojson = CASOS[MAERSK_CON_POSICION]
    instante = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)

    await colector_shipsgo.procesar(sesion, elemento, shipment, geojson, instante=instante)
    segundo = await colector_shipsgo.procesar(
        sesion, elemento, shipment, geojson, instante=instante
    )
    await sesion.flush()

    assert segundo.posicion_registrada is False
    filas = await sesion.scalar(
        select(func.count())
        .select_from(HistorialTracking)
        .where(HistorialTracking.id_elemento_rastreado == elemento.id)
    )
    assert filas == 1
