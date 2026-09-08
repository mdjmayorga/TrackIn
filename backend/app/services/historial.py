"""Registro del historial de posiciones — RF-21 / RNF-13 (`US-04`).

Cada lectura de una fuente se guarda con **la respuesta completa** en
`payload_api`, que es lo que exige RNF-13: sin el crudo no se puede auditar por
qué el sistema decidió lo que decidió, ni reprocesar cuando se corrija un
cálculo.

Dos mecanismos evitan que la tabla crezca sin control, y conviene no
confundirlos porque resuelven problemas distintos:

- **Submuestreo** (`intervalo_minimo_persistencia_s`): descarta lecturas
  *nuevas* que llegan demasiado seguidas. Un buque en alta mar puede emitir AIS
  cada pocos segundos y su posición no cambia lo suficiente para justificar una
  fila. Es una decisión de negocio, ajustable sin desplegar código.
- **Idempotencia** (índice único por elemento y fecha): descarta lecturas
  *repetidas*, las que ya están guardadas. Ocurre cuando el worker reprocesa o
  la fuente reenvía. No es configurable: guardar dos veces la misma lectura es
  siempre un error.

La tabla es *append-only*. La inmutabilidad no se confía al ORM: la impone un
disparador en la base (migración `0003`), porque el `UPDATE` puede venir de
`psql`, de una herramienta de administración o de un `bulk_update` que no pasa
por el modelo.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historial_tracking import HistorialTracking
from app.services import parametros

logger = logging.getLogger(__name__)

#: Motivos por los que una lectura no produce fila. No son errores.
DESCARTE_SUBMUESTREO = "submuestreo"
DESCARTE_DUPLICADA = "duplicada"


@dataclass(frozen=True, slots=True)
class ResultadoRegistro:
    """Qué pasó con la lectura."""

    guardada: bool
    registro: HistorialTracking | None
    motivo: str

    def __bool__(self) -> bool:
        return self.guardada


def _punto(longitud: float, latitud: float) -> str:
    """WKT del punto, en el orden que espera PostGIS: **longitud primero**.

    Es el error clásico de los datos geoespaciales. Las fuentes AIS y ADS-B
    reportan `lat, lon` y PostGIS toma `lon, lat`; invertirlos coloca los buques
    del Caribe en Somalia sin que nada falle.
    """
    return f"SRID=4326;POINT({longitud} {latitud})"


async def ultima_lectura(sesion: AsyncSession, id_elemento: int) -> HistorialTracking | None:
    """Posición más reciente guardada de ese elemento, o `None` si no hay."""
    return await sesion.scalar(
        select(HistorialTracking)
        .where(HistorialTracking.id_elemento_rastreado == id_elemento)
        .order_by(desc(HistorialTracking.fecha_registro))
        .limit(1)
    )


async def registrar_posicion(
    sesion: AsyncSession,
    *,
    id_elemento: int,
    fecha_registro: dt.datetime,
    latitud: float,
    longitud: float,
    payload: dict[str, Any],
    velocidad: Decimal | float | None = None,
    rumbo: Decimal | float | None = None,
    estado_api: str | None = None,
    forzar: bool = False,
) -> ResultadoRegistro:
    """Guarda una lectura, salvo que el submuestreo o la idempotencia lo impidan.

    No hace *commit*: eso es de quien llama, que normalmente procesa un lote.

    `forzar` salta el submuestreo pero **nunca** la idempotencia. Sirve para la
    lectura que confirma un arribo, donde perder la posición por el intervalo
    sería peor que una fila de más.
    """
    if fecha_registro.tzinfo is None:
        # Una fecha ingenua se interpretaría como hora local del servidor y la
        # comparación con la última lectura daría cualquier cosa.
        raise ValueError("fecha_registro debe traer zona horaria; las fuentes reportan UTC.")

    duplicada = await sesion.scalar(
        select(func.count())
        .select_from(HistorialTracking)
        .where(
            HistorialTracking.id_elemento_rastreado == id_elemento,
            HistorialTracking.fecha_registro == fecha_registro,
        )
    )
    if duplicada:
        return ResultadoRegistro(False, None, DESCARTE_DUPLICADA)

    if not forzar:
        previa = await ultima_lectura(sesion, id_elemento)
        if previa is not None:
            intervalo = await parametros.obtener_entero(sesion, "intervalo_minimo_persistencia_s")
            transcurrido = (fecha_registro - previa.fecha_registro).total_seconds()
            # Una lectura anterior a la última guardada llega fuera de orden.
            # `abs` la trata igual que una demasiado próxima: en ambos casos no
            # aporta un punto nuevo al trayecto.
            if abs(transcurrido) < intervalo:
                logger.debug(
                    "Elemento %s: lectura descartada, %.0f s < %s s.",
                    id_elemento,
                    transcurrido,
                    intervalo,
                )
                return ResultadoRegistro(False, None, DESCARTE_SUBMUESTREO)

    registro = HistorialTracking(
        id_elemento_rastreado=id_elemento,
        fecha_registro=fecha_registro,
        posicion=_punto(longitud, latitud),
        velocidad=Decimal(str(velocidad)) if velocidad is not None else None,
        rumbo=Decimal(str(rumbo)) if rumbo is not None else None,
        estado_api=estado_api,
        payload_api=payload,
    )
    sesion.add(registro)
    await sesion.flush()
    return ResultadoRegistro(True, registro, "guardada")


async def registrar_lote(sesion: AsyncSession, lecturas: list[dict[str, Any]]) -> dict[str, int]:
    """Procesa varias lecturas y devuelve el recuento por resultado.

    Cada lectura se evalúa contra lo ya guardado, de modo que el submuestreo
    también aplica **dentro** del lote: un worker que acumula mensajes durante
    un minuto no puede meterlos todos por venir juntos.
    """
    conteo = {"guardadas": 0, DESCARTE_SUBMUESTREO: 0, DESCARTE_DUPLICADA: 0}
    for lectura in lecturas:
        resultado = await registrar_posicion(sesion, **lectura)
        if resultado.guardada:
            conteo["guardadas"] += 1
        else:
            conteo[resultado.motivo] += 1
    return conteo


__all__ = [
    "DESCARTE_DUPLICADA",
    "DESCARTE_SUBMUESTREO",
    "ResultadoRegistro",
    "registrar_lote",
    "registrar_posicion",
    "ultima_lectura",
]
