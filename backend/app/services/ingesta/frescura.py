"""¿Está cargado el Z-tracking de esta semana? — `US-23`.

Reunión con Compras del 22/10/2026: SAP se actualiza **los lunes** y Compras
carga el Z-tracking en TrackIn **a más tardar el martes** (`dia_limite_carga`).
El encabezado del panel lo muestra así:

| Situación | Cuándo |
|---|---|
| `AL_DIA` | Hay una carga aplicada desde el lunes de esta semana |
| `TOCA_CARGAR` | No la hay, pero todavía no pasó el día límite: se recuerda |
| `ATRASADA` | No la hay y ya pasó el día límite: se avisa |
| `NUNCA` | Nunca se aplicó una carga desde la interfaz |

Solo cuentan las cargas **aplicadas**: un archivo rechazado entero no cambió
ningún pedido. La semana se cuenta en hora de Costa Rica, donde se trabaja: a
las 18:00 de un domingo, en UTC ya es lunes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.carga_ztracking import EXCEL, CargaZTracking
from app.services import parametros

#: Costa Rica no cambia de hora: UTC-6 todo el año.
ZONA_CR: Final = dt.timezone(dt.timedelta(hours=-6), "America/Costa_Rica")

CLAVE_DIA_LIMITE: Final = "dia_limite_carga"

Situacion = Literal["AL_DIA", "TOCA_CARGAR", "ATRASADA", "NUNCA"]


@dataclass(frozen=True, slots=True)
class EstadoCargaSemanal:
    situacion: Situacion
    #: La última carga aplicada, la de esta semana o una anterior.
    ultima: CargaZTracking | None
    #: El lunes de la semana en curso, en Costa Rica.
    semana_desde: dt.date
    #: 1 lunes … 7 domingo.
    dia_limite: int


def _lunes(fecha: dt.date) -> dt.date:
    return fecha - dt.timedelta(days=fecha.isoweekday() - 1)


async def estado_semanal(
    sesion: AsyncSession, *, instante: dt.datetime | None = None
) -> EstadoCargaSemanal:
    """Lee la última carga aplicada y la compara con la semana en curso."""
    ahora = (instante or dt.datetime.now(dt.UTC)).astimezone(ZONA_CR)
    hoy = ahora.date()
    lunes = _lunes(hoy)
    # Un valor fuera de 1..7 en la base no puede romper el encabezado: se acota.
    dia_limite = min(7, max(1, await parametros.obtener_entero(sesion, CLAVE_DIA_LIMITE)))

    ultima = await sesion.scalar(
        select(CargaZTracking)
        .where(CargaZTracking.estado == "APLICADA")
        # La obligación semanal es la del Excel (`US-23`). Un lote incremental de
        # SAP no la cumple: puede traer una sola línea (`US-65`).
        .where(CargaZTracking.origen == EXCEL)
        .options(selectinload(CargaZTracking.usuario))
        .order_by(CargaZTracking.realizada_en.desc(), CargaZTracking.id.desc())
        .limit(1)
    )

    situacion: Situacion
    if ultima is None:
        situacion = "NUNCA"
    elif ultima.realizada_en.astimezone(ZONA_CR).date() >= lunes:
        situacion = "AL_DIA"
    elif hoy.isoweekday() <= dia_limite:
        situacion = "TOCA_CARGAR"
    else:
        situacion = "ATRASADA"
    return EstadoCargaSemanal(situacion, ultima, lunes, dia_limite)


__all__ = ["EstadoCargaSemanal", "Situacion", "ZONA_CR", "estado_semanal"]
