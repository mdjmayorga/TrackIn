"""Guardar y leer los transbordos de un embarque — `US-30`.

El worker los deduce de cada lectura de ShipsGo (`LecturaEmbarque.transbordos`)
y los registra **una sola vez por embarque**: la misma pareja de naves no se
duplica entre consultas. Lo que sí cambia de una consulta a otra se actualiza:
un transbordo previsto que ocurre, o una fecha estimada que se corrige.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.transbordo import Transbordo
from app.services.rastreo.shipsgo import CambioDeVehiculo


async def registrar(
    sesion: AsyncSession,
    elemento: ElementoRastreado,
    cambios: Sequence[CambioDeVehiculo],
    *,
    instante: dt.datetime | None = None,
) -> int:
    """Registra los transbordos nuevos y actualiza los conocidos. **No hace commit.**

    Devuelve cuántos son nuevos.
    """
    existentes = {
        (t.vehiculo_anterior, t.vehiculo_nuevo): t
        for t in await sesion.scalars(
            select(Transbordo).where(Transbordo.id_elemento_rastreado == elemento.id)
        )
    }
    nuevos = 0
    for orden, cambio in enumerate(cambios, start=1):
        anterior, nuevo = cambio.anterior[:120], cambio.nuevo[:120]
        fila = existentes.get((anterior, nuevo))
        if fila is None:
            fila = Transbordo(
                id_elemento_rastreado=elemento.id,
                vehiculo_anterior=anterior,
                vehiculo_nuevo=nuevo,
                detectado_en=instante or dt.datetime.now(dt.UTC),
            )
            sesion.add(fila)
            existentes[(anterior, nuevo)] = fila
            nuevos += 1
        fila.orden = orden
        fila.puerto = cambio.puerto[:10] if cambio.puerto else None
        fila.puerto_nombre = cambio.puerto_nombre[:120] if cambio.puerto_nombre else None
        fila.fecha = cambio.instante
        fila.ocurrido = cambio.ocurrido
    await sesion.flush()
    return nuevos


async def del_elemento(sesion: AsyncSession, id_elemento: int) -> list[Transbordo]:
    """Los transbordos de un embarque, en el orden del trayecto."""
    return list(
        await sesion.scalars(
            select(Transbordo)
            .where(Transbordo.id_elemento_rastreado == id_elemento)
            .order_by(Transbordo.orden, Transbordo.id)
        )
    )


__all__ = ["del_elemento", "registrar"]
