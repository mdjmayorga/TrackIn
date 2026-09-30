"""Cambios al maestro de destinos que mueven fechas — `US-12`.

El lead time de un destino es un sumando de RN-01: cambiarlo cambia la fecha
proyectada de cada pedido activo que va a ese destino. Por eso no se edita la
columna a secas: se edita **por aquí**, que guarda y recalcula en la misma
transacción. Si el recálculo se dejara para después, la grilla mostraría fechas
hechas con el valor viejo, que es justo lo que `US-12` prohíbe.

`US-13` (30/09/2026) añadió aquí lo que es de administración: el alta, la
edición, la baja con advertencia y el control de duplicados. La API la expone en
`/api/v1/destinos`.

Qué no se puede cambiar de un destino
--------------------------------------

**El código y la vía.** El código es la clave natural con la que la ingesta y
ShipsGo ubican el destino (`CRCAL`, `MROC`), y la vía ata al destino con cada
pedido que ya tiene. Cambiarlos sería otro destino: se da de alta el nuevo y se
desactiva el viejo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maestro_destino import MaestroDestino
from app.models.pedido_transito import PedidoTransito
from app.services import historial, recalculo

logger = logging.getLogger(__name__)


class LeadTimeInvalido(ValueError):
    """El valor no es un número entero de días, o es negativo."""


class DestinoDuplicado(ValueError):
    """Ya hay un destino con ese código, o con ese nombre en esa vía."""


class ConfirmacionRequerida(Exception):
    """Desactivar el destino afecta pedidos activos: hay que confirmarlo."""

    def __init__(self, pedidos_activos: int) -> None:
        self.pedidos_activos = pedidos_activos
        super().__init__(
            f"El destino tiene {pedidos_activos} pedido(s) activo(s). Siguen con este "
            "destino, pero la carga ya no podrá asignárselo a líneas nuevas. "
            "Repita la operación confirmando."
        )


@dataclass(frozen=True, slots=True)
class FichaDestino:
    """Un destino con lo que la pantalla del maestro necesita ver."""

    destino: MaestroDestino
    latitud: float
    longitud: float
    pedidos_activos: int


@dataclass(frozen=True, slots=True)
class CambioLeadTime:
    destino: str
    anterior: int
    nuevo: int
    recalculo: recalculo.ResumenRecalculo | None
    """`None` si el valor no cambió y no hubo nada que recalcular."""


def validar_lead_time(valor: object) -> int:
    """Días enteros y no negativos. `True` no cuenta como 1, ni `2.5` como 2.

    El mensaje dice qué se esperaba, que es el segundo criterio de `US-13`.
    """
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise LeadTimeInvalido(
            f"El lead time debe ser un número entero de días; se recibió {valor!r}."
        )
    if valor < 0:
        raise LeadTimeInvalido(f"El lead time no puede ser negativo; se recibió {valor}.")
    return valor


async def cambiar_lead_time(sesion: AsyncSession, id_destino: int, dias: object) -> CambioLeadTime:
    """Guarda el lead time y recalcula los pedidos activos del destino.

    **No hace commit**: es de quien llama, como en el resto de servicios. Lo
    que sí garantiza es que el valor nuevo y las fechas que produce quedan en
    la misma transacción: o entran los dos, o ninguno.
    """
    nuevo = validar_lead_time(dias)
    destino = await sesion.get(MaestroDestino, id_destino)
    if destino is None:
        raise LookupError(f"No existe el destino {id_destino}.")

    anterior = destino.lead_time_dias
    if anterior == nuevo:
        return CambioLeadTime(destino.codigo, anterior, nuevo, None)

    destino.lead_time_dias = nuevo
    await sesion.flush()
    resumen = await recalculo.recalcular_destino(sesion, destino.id)
    logger.info(
        "Lead time de %s: %d → %d días. Recálculo: %s.",
        destino.codigo,
        anterior,
        nuevo,
        resumen.texto(),
    )
    return CambioLeadTime(destino.codigo, anterior, nuevo, resumen)


async def pedidos_activos(sesion: AsyncSession, id_destino: int) -> int:
    """Los pedidos no cerrados que van a ese destino."""
    total = await sesion.scalar(
        select(func.count()).where(
            PedidoTransito.id_destino == id_destino, PedidoTransito.motivo_cierre.is_(None)
        )
    )
    return total or 0


async def _duplicado(
    sesion: AsyncSession,
    *,
    codigo: str | None,
    nombre: str | None,
    via: str,
    excepto: int | None = None,
) -> str | None:
    """Por qué el alta o el cambio duplicaría un destino, o `None`."""
    if codigo is not None:
        igual = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == codigo))
        if igual is not None and igual.id != excepto:
            return f"Ya existe un destino con el código {codigo} ({igual.nombre})."
    if nombre is not None:
        igual = await sesion.scalar(
            select(MaestroDestino).where(
                func.lower(MaestroDestino.nombre) == nombre.lower(),
                MaestroDestino.via_transporte == via,
            )
        )
        if igual is not None and igual.id != excepto:
            return (
                f"Ya existe «{igual.nombre}» por vía {via} (código {igual.codigo}). "
                "El mismo destino no se da de alta dos veces."
            )
    return None


async def crear_destino(
    sesion: AsyncSession,
    *,
    codigo: str,
    nombre: str,
    pais: str,
    via_transporte: str,
    latitud: float,
    longitud: float,
    lead_time_dias: object,
    radio_geocerca_km: int | None = None,
    observacion: str | None = None,
) -> MaestroDestino:
    """Da de alta un destino. **No hace commit.**

    Queda activo y disponible para la ingesta desde ese momento: un incoterm
    que lo nombre, o ShipsGo cuando declare su código, ya lo encuentran.
    """
    dias = validar_lead_time(lead_time_dias)
    codigo = codigo.strip().upper()
    nombre = nombre.strip()
    motivo = await _duplicado(sesion, codigo=codigo, nombre=nombre, via=via_transporte)
    if motivo:
        raise DestinoDuplicado(motivo)

    destino = MaestroDestino(
        codigo=codigo,
        nombre=nombre,
        pais=pais.strip().upper(),
        via_transporte=via_transporte,
        # Longitud primero: es el orden de PostGIS (ver `historial.punto_wkt`).
        ubicacion=historial.punto_wkt(longitud, latitud),
        radio_geocerca_km=radio_geocerca_km,
        lead_time_dias=dias,
        observacion=observacion,
    )
    sesion.add(destino)
    await sesion.flush()
    logger.info("Destino nuevo: %s %s (%s, %d días).", codigo, nombre, via_transporte, dias)
    return destino


#: Marca «no se envió», distinta de `None`, que sí es un valor (borrar el radio).
SIN_CAMBIO: Any = object()


async def actualizar_destino(
    sesion: AsyncSession,
    id_destino: int,
    *,
    nombre: str | None = None,
    lead_time_dias: object = SIN_CAMBIO,
    radio_geocerca_km: Any = SIN_CAMBIO,
    observacion: Any = SIN_CAMBIO,
    activo: bool | None = None,
    confirmar: bool = False,
) -> tuple[MaestroDestino, CambioLeadTime | None]:
    """Edita un destino. **No hace commit.**

    Todo se valida **antes** de tocar nada, para que un error no deje el
    destino a medio cambiar. Desactivar uno con pedidos activos exige
    `confirmar` (tercer criterio de `US-13`): esos pedidos no cambian, pero la
    ingesta deja de ofrecerlo para líneas nuevas.
    """
    destino = await sesion.get(MaestroDestino, id_destino)
    if destino is None:
        raise LookupError(f"No existe el destino {id_destino}.")

    if lead_time_dias is not SIN_CAMBIO:
        validar_lead_time(lead_time_dias)
    if nombre is not None:
        nombre = nombre.strip()
        motivo = await _duplicado(
            sesion, codigo=None, nombre=nombre, via=destino.via_transporte, excepto=destino.id
        )
        if motivo:
            raise DestinoDuplicado(motivo)
    if activo is False and destino.activo and not confirmar:
        activos = await pedidos_activos(sesion, destino.id)
        if activos:
            raise ConfirmacionRequerida(activos)

    if nombre is not None:
        destino.nombre = nombre
    if radio_geocerca_km is not SIN_CAMBIO:
        destino.radio_geocerca_km = radio_geocerca_km
    if observacion is not SIN_CAMBIO:
        destino.observacion = observacion
    if activo is not None:
        destino.activo = activo
    await sesion.flush()

    cambio = None
    if lead_time_dias is not SIN_CAMBIO:
        # Por el camino de `US-12`: guarda y recalcula en la misma transacción.
        cambio = await cambiar_lead_time(sesion, destino.id, lead_time_dias)
    return destino, cambio


def _fichas_consulta() -> Any:
    punto = cast(MaestroDestino.ubicacion, Geometry)
    activos = (
        select(PedidoTransito.id_destino, func.count().label("n"))
        .where(PedidoTransito.motivo_cierre.is_(None))
        .group_by(PedidoTransito.id_destino)
        .subquery()
    )
    return (
        select(
            MaestroDestino,
            func.ST_Y(punto),
            func.ST_X(punto),
            func.coalesce(activos.c.n, 0),
        )
        .outerjoin(activos, activos.c.id_destino == MaestroDestino.id)
        .order_by(MaestroDestino.via_transporte, MaestroDestino.nombre)
    )


async def listar_destinos(
    sesion: AsyncSession, incluir_inactivos: bool = False
) -> list[FichaDestino]:
    consulta = _fichas_consulta()
    if not incluir_inactivos:
        consulta = consulta.where(MaestroDestino.activo.is_(True))
    filas = await sesion.execute(consulta)
    return [FichaDestino(d, float(lat), float(lon), int(n)) for d, lat, lon, n in filas]


async def ficha(sesion: AsyncSession, id_destino: int) -> FichaDestino | None:
    fila = (await sesion.execute(_fichas_consulta().where(MaestroDestino.id == id_destino))).first()
    if fila is None:
        return None
    destino, lat, lon, n = fila
    return FichaDestino(destino, float(lat), float(lon), int(n))


__all__ = [
    "SIN_CAMBIO",
    "CambioLeadTime",
    "ConfirmacionRequerida",
    "DestinoDuplicado",
    "FichaDestino",
    "LeadTimeInvalido",
    "actualizar_destino",
    "cambiar_lead_time",
    "crear_destino",
    "ficha",
    "listar_destinos",
    "pedidos_activos",
    "validar_lead_time",
]
