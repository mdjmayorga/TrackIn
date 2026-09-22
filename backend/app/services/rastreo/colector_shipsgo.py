"""Persistencia de una lectura de ShipsGo — `US-45` / RF-20, RF-21, RNF-13.

Toma lo que `shipsgo.interpretar` extrajo y lo escribe donde corresponde. Es el
único módulo de los tres que toca la base.

Qué se guarda y dónde
----------------------

| Dato | Destino | Por qué |
|---|---|---|
| Payload completo | `historial_tracking.payload_api` | RF-21 / RNF-13, y porque ShipsGo **archiva** lo entregado |
| Posición | `historial_tracking` + `elementos_rastreados.posicion_actual` | RF-20: el mapa lee la desnormalizada |
| Nave e IMO | `elementos_rastreados.nombre` / `.imo` | `US-45`; el mapa (`US-27`) y el detalle (`US-44`) los consumen |
| ETA | `elementos_rastreados.eta_api` | Es el tercer escalón de la precedencia de RN-14 que usa `US-09` |
| ATA | `elementos_rastreados.ata_api` | Solo si hay hito de arribo **en el destino** |

El payload se guarda aunque no haya posición
---------------------------------------------

Es el punto que separa a esta fuente de AIS. Con AIS, sin posición no hay nada
que registrar. Con ShipsGo, la respuesta **sin** posición sigue trayendo hitos,
ETA y transbordo, y encima el embarque puede archivarse: si no se guarda, la
única copia de lo que la fuente dijo desaparece.

Por eso, cuando no hay coordenadas, se registra igual usando la posición previa
conocida del elemento —o ninguna— y el payload entero. `historial_tracking`
exige coordenadas, así que sin posición previa se anota solo en el elemento y
se deja constancia en el log: perder el payload sería peor, pero inventar una
posición sería mucho peor.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.services import historial
from app.services.rastreo import shipsgo

logger = logging.getLogger(__name__)

#: Motivos por los que una lectura no se aplica.
DESCARTE_SIN_MADURAR = "embarque_sin_madurar"
DESCARTE_SIN_DATOS = "lectura_sin_datos"


@dataclass(frozen=True, slots=True)
class ResultadoLectura:
    """Qué se hizo con la lectura."""

    aplicada: bool
    motivo: str
    lectura: shipsgo.LecturaEmbarque | None = None
    #: `True` si la posición llegó a `historial_tracking`.
    posicion_registrada: bool = False
    #: `True` si el payload quedó guardado, con o sin posición.
    payload_guardado: bool = False
    transbordo_detectado: bool = False


async def procesar(
    sesion: AsyncSession,
    elemento: ElementoRastreado,
    shipment: dict[str, Any] | None,
    geojson: dict[str, Any] | None = None,
    instante: dt.datetime | None = None,
) -> ResultadoLectura:
    """Aplica una respuesta de ShipsGo al elemento rastreado.

    **No hace commit**: quien llama procesa un lote.
    """
    if not shipsgo.esta_maduro(shipment):
        # El tercer estado: dado de alta y todavía sin datos (~90 s). No es un
        # fallo ni una respuesta vacía definitiva.
        logger.info(
            "ShipsGo: el embarque de %s sigue madurando; se reintenta luego.",
            elemento.tracking_externo,
        )
        return ResultadoLectura(False, DESCARTE_SIN_MADURAR)

    lectura = shipsgo.interpretar(shipment, geojson)
    if not lectura.hitos and lectura.eta is None:
        return ResultadoLectura(False, DESCARTE_SIN_DATOS, lectura)

    ahora = instante or dt.datetime.now(dt.UTC)
    resultado_posicion = False

    # --- El elemento rastreado ---------------------------------------------
    if lectura.vehiculo_actual is not None:
        elemento.nombre = lectura.vehiculo_actual.nombre[:120]
        if lectura.vehiculo_actual.imo is not None:
            elemento.imo = lectura.vehiculo_actual.imo
    if lectura.eta is not None:
        elemento.eta_api = lectura.eta
    if lectura.ata is not None:
        elemento.ata_api = lectura.ata
    elemento.ultima_actualizacion_api = ahora

    # --- El historial -------------------------------------------------------
    if lectura.posicion is not None:
        longitud, latitud = lectura.posicion
        registro = await historial.registrar_posicion(
            sesion,
            id_elemento=elemento.id,
            fecha_registro=ahora,
            latitud=latitud,
            longitud=longitud,
            payload=shipment or {},
            # ShipsGo **no entrega** velocidad ni rumbo, y no hacen falta:
            # RN-16 los quería para estimar la ETA y ésta llega ya calculada.
            velocidad=None,
            rumbo=None,
            estado_api=lectura.estado_fuente,
            # Un arribo se guarda sí o sí: perderlo por el submuestreo sería
            # peor que una fila de más.
            forzar=lectura.arribado,
        )
        resultado_posicion = registro.guardada
        if registro.guardada:
            elemento.posicion_actual = historial.punto_wkt(longitud, latitud)
    else:
        # Medido en el BL de COSCO: `current: null` en todas las *features*.
        logger.info(
            "ShipsGo: %s sin posición; se conservan hitos y ETA. El mapa cae al respaldo AIS.",
            elemento.tracking_externo,
        )

    if lectura.hay_transbordo:
        logger.info(
            "ShipsGo: %s viaja con transbordo (%s). Insumo de US-30.",
            elemento.tracking_externo,
            " → ".join(n.nombre for n in lectura.vehiculos),
        )

    if lectura.archivado_en is not None:
        # ShipsGo archiva solo lo terminado. El payload guardado pasa a ser la
        # única copia, y el planificador tiene que sacarlo del ciclo (`US-07`).
        logger.warning(
            "ShipsGo: el embarque de %s quedó archivado (%s); puede dejar de ser consultable.",
            elemento.tracking_externo,
            lectura.archivado_en,
        )

    return ResultadoLectura(
        aplicada=True,
        motivo="aplicada",
        lectura=lectura,
        posicion_registrada=resultado_posicion,
        payload_guardado=resultado_posicion,
        transbordo_detectado=lectura.hay_transbordo,
    )


__all__ = [
    "DESCARTE_SIN_DATOS",
    "DESCARTE_SIN_MADURAR",
    "ResultadoLectura",
    "procesar",
]
