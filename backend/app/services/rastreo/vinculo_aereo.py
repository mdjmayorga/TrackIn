"""El `icao24` como vínculo temporal del tramo — `US-06` / RF-07.

El hallazgo que da sentido a esta historia
-------------------------------------------

TG-11 siguió a la aeronave `0ac9e1` durante 48 horas:

```
AVA072  SKBO → ?        AVA068  SKBO → MMUN
AVA263  KORD → SKBO     AVA262  SKBO → KORD
AVA021  KJFK → SKBO
```

**Cinco vuelos, cinco callsigns, una sola aeronave.** El `icao24` identifica el
**avión**; el callsign identifica el **vuelo**. Guardar el `icao24` como
atributo fijo del pedido haría que TrackIn siguiera un avión que ya está
volando a otro destino con otra carga — y lo haría en silencio, mostrando una
posición perfectamente plausible.

Por eso el vínculo vive en `pedido_elemento_rastreado`, la asociativa de
tramos, con su `fecha_desde` y su `fecha_hasta`. La tabla ya existía para el
transbordo marítimo (RF-26) y resuelve exactamente el mismo problema: la
relación pedido-elemento es N:M **a lo largo del tiempo**.

El índice parcial `uq_pedido_elemento_rastreado_vigente` garantiza en la base
que un pedido no tenga dos tramos abiertos a la vez, así que cerrar el anterior
antes de abrir el siguiente no es una cortesía: es un requisito.

El callsign llega tarde
------------------------

`0ae105` reportó `callsign: null` y `TIAGO` **tres minutos después**. Así que
resolver por callsign puede fallar la primera vez y funcionar a la siguiente:
el vínculo se abre cuando se encuentra, y mientras tanto no se inventa nada. Una
vez abierto, **se sigue por `icao24`**, que sí es estable dentro del tramo.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services.rastreo.opensky import PosicionAerea, por_callsign

logger = logging.getLogger(__name__)

#: Tipo de referencia con que se guarda la aeronave.
TIPO_ICAO24 = "VUELO"

#: Por qué no se pudo resolver.
SIN_CALLSIGN = "el_pedido_no_declara_vuelo"
NO_ESTA_VOLANDO = "el_vuelo_no_aparece_en_el_area"


@dataclass(frozen=True, slots=True)
class ResultadoVinculo:
    """Qué pasó al resolver la aeronave de un tramo."""

    resuelto: bool
    motivo: str
    icao24: str | None = None
    tramo: int | None = None
    #: `True` si se abrió un tramo nuevo (antes no había vínculo vigente).
    abierto: bool = False
    #: `True` si el vínculo anterior se cerró porque la aeronave cambió.
    cerrado_anterior: bool = False


async def tramo_vigente(
    sesion: AsyncSession, pedido: PedidoTransito
) -> PedidoElementoRastreado | None:
    """El tramo abierto del pedido, si lo hay. La base garantiza que es uno."""
    return await sesion.scalar(
        select(PedidoElementoRastreado).where(
            PedidoElementoRastreado.id_pedido == pedido.id,
            PedidoElementoRastreado.fecha_hasta.is_(None),
        )
    )


async def _siguiente_tramo(sesion: AsyncSession, pedido: PedidoTransito) -> int:
    ultimo = await sesion.scalar(
        select(PedidoElementoRastreado.tramo)
        .where(PedidoElementoRastreado.id_pedido == pedido.id)
        .order_by(PedidoElementoRastreado.tramo.desc())
        .limit(1)
    )
    return (ultimo or 0) + 1


async def _obtener_o_crear_aeronave(
    sesion: AsyncSession, icao24: str, callsign: str | None
) -> ElementoRastreado:
    """La aeronave como elemento rastreado, reutilizándola si ya existe.

    Se reutiliza por la misma razón que en marítimo: varias líneas pueden viajar
    en el mismo vuelo y duplicar el elemento duplicaría las consultas.
    """
    normalizado = icao24.strip().lower()
    existente = await sesion.scalar(
        select(ElementoRastreado).where(
            ElementoRastreado.tipo_tracking_externo == TIPO_ICAO24,
            ElementoRastreado.tracking_externo == normalizado,
            ElementoRastreado.activo.is_(True),
        )
    )
    if existente is not None:
        if callsign and existente.nombre != callsign:
            # El callsign llega tarde: se actualiza cuando aparece.
            existente.nombre = callsign[:120]
        return existente

    aeronave = ElementoRastreado(
        tipo_tracking_externo=TIPO_ICAO24,
        tracking_externo=normalizado,
        via_transporte="AEREO",
        nombre=callsign[:120] if callsign else None,
        # Un avión no tiene IMO: eso es de la OMI y solo aplica a naves.
        imo=None,
    )
    sesion.add(aeronave)
    await sesion.flush()
    return aeronave


async def resolver(
    sesion: AsyncSession,
    pedido: PedidoTransito,
    callsign: str | None,
    posiciones: list[PosicionAerea],
    instante: dt.datetime | None = None,
) -> ResultadoVinculo:
    """Resuelve el `icao24` del vuelo y lo vincula al tramo. **Sin commit.**

    `callsign` es el número de vuelo del tramo, que hoy llega del archivo o de
    los hitos de `US-46`. Sin él no hay nada que resolver: se informa y se sigue.
    """
    ahora = instante or dt.datetime.now(dt.UTC)

    if not callsign or not callsign.strip():
        return ResultadoVinculo(False, SIN_CALLSIGN)

    avistamiento = por_callsign(posiciones, callsign)
    if avistamiento is None:
        # Puede ser que no haya despegado, que ya aterrizara, o que el callsign
        # todavía no se reporte: la API no los distingue. No se inventa nada.
        return ResultadoVinculo(False, NO_ESTA_VOLANDO)

    vigente = await tramo_vigente(sesion, pedido)
    if vigente is not None:
        aeronave_actual = await sesion.get(ElementoRastreado, vigente.id_elemento_rastreado)
        if aeronave_actual is not None and aeronave_actual.tracking_externo == avistamiento.icao24:
            # Mismo avión: el vínculo sigue valiendo, no se toca nada.
            return ResultadoVinculo(True, "vinculo_vigente", avistamiento.icao24, vigente.tramo)

        # La aeronave cambió: se cierra el tramo anterior **antes** de abrir el
        # siguiente. El índice parcial de la tabla no admite dos abiertos.
        vigente.fecha_hasta = ahora
        await sesion.flush()
        logger.info(
            "Pedido %s: cambia de aeronave; tramo %d cerrado el %s.",
            pedido,
            vigente.tramo,
            ahora,
        )

    aeronave = await _obtener_o_crear_aeronave(sesion, avistamiento.icao24, avistamiento.callsign)
    numero = await _siguiente_tramo(sesion, pedido)
    sesion.add(
        PedidoElementoRastreado(
            id_pedido=pedido.id,
            id_elemento_rastreado=aeronave.id,
            tramo=numero,
            fecha_desde=ahora,
            fecha_hasta=None,
        )
    )
    # El FK del pedido apunta a la nave **vigente**; el historial vive en la
    # asociativa. RN-02 exige además que la etapa salga de `SIN_TRACKING`.
    pedido.id_elemento_rastreado = aeronave.id
    if pedido.etapa_viaje == "SIN_TRACKING":
        pedido.etapa_viaje = "EN_ORIGEN"
        if pedido.estado_calculado == "SIN_TRACKING":
            pedido.estado_calculado = "EN_ORIGEN"
    await sesion.flush()

    logger.info(
        "Pedido %s: vuelo %s resuelto a la aeronave %s (tramo %d).",
        pedido,
        callsign,
        avistamiento.icao24,
        numero,
    )
    return ResultadoVinculo(
        True,
        "vinculo_abierto",
        avistamiento.icao24,
        numero,
        abierto=True,
        cerrado_anterior=vigente is not None,
    )


async def cerrar_tramo(
    sesion: AsyncSession, pedido: PedidoTransito, instante: dt.datetime | None = None
) -> bool:
    """Cierra el tramo vigente. **El segundo criterio de `US-06`.**

    *«Dada una aeronave que cambió de vuelo, cuando finaliza el tramo, el
    vínculo queda cerrado y no se sigue consultando»*. Lo llama quien sabe que
    el tramo terminó: el arribo (`US-11`) o el cierre del pedido.
    """
    vigente = await tramo_vigente(sesion, pedido)
    if vigente is None:
        return False

    vigente.fecha_hasta = instante or dt.datetime.now(dt.UTC)
    await sesion.flush()
    logger.info("Pedido %s: tramo %d cerrado.", pedido, vigente.tramo)
    return True


__all__ = [
    "NO_ESTA_VOLANDO",
    "SIN_CALLSIGN",
    "TIPO_ICAO24",
    "ResultadoVinculo",
    "cerrar_tramo",
    "resolver",
    "tramo_vigente",
]
