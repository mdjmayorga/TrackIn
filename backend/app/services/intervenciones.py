"""Las intervenciones manuales sobre un pedido — `US-14` (y las que siguen).

Cada intervención hace tres cosas en la misma transacción, o ninguna:

1. **Cambia el pedido** —una fecha, una etapa—, validando antes todo lo que
   pueda rechazarla para no dejarlo a medias.
2. **Recalcula** fecha proyectada y estado (`US-12`): el cambio es un insumo.
3. **La audita** (`US-15`), con el autor de la sesión (`US-42`) y el motivo.

`US-18`, `US-47` y `US-40` se suman aquí con el mismo esquema.

`US-14`: confirmar el desembarco y pasar a proceso aduanal
-----------------------------------------------------------

Son **dos actos**, como en la operación real (reunión con Planeación del 04/09):

- **Confirmar el desembarco** registra la llegada real (`ata_confirmada`) y deja
  el pedido «En destino». Es el único camino para los pedidos sin rastreo —casi
  todos hoy— y la corrección para los que sí lo tienen cuando la fuente no
  reporta o reporta mal. Por RN-14, la ATA confirmada manda sobre todo.
- **Pasar a proceso aduanal** es el acto humano que autoriza el cambio de
  etapa. Exige que el arribo se conozca —confirmado o por el hito de la
  fuente—: no se pasa a aduana algo que no llegó.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido_transito import PedidoTransito
from app.services import auditoria, estado, recalculo

logger = logging.getLogger(__name__)

EN_DESTINO = "EN_DESTINO"
EN_PROCESO_ADUANAL = "EN_PROCESO_ADUANAL"


class IntervencionRechazada(Exception):
    """El pedido no admite esta intervención en su estado actual (409)."""


class FechaInvalida(ValueError):
    """La fecha no se puede aceptar: futura, o sin zona horaria (422)."""


class ConfirmacionRequerida(Exception):
    """Ya había un valor: sobrescribirlo exige confirmarlo explícitamente."""

    def __init__(self, valor_actual: dt.datetime) -> None:
        self.valor_actual = valor_actual
        super().__init__(
            f"El pedido ya tiene una llegada confirmada ({valor_actual.isoformat()}). "
            "Para reemplazarla, repita la operación confirmando."
        )


async def _pedido(sesion: AsyncSession, id_pedido: int) -> PedidoTransito:
    pedido = await sesion.get(PedidoTransito, id_pedido)
    if pedido is None:
        raise LookupError(f"No existe el pedido {id_pedido}.")
    if pedido.motivo_cierre is not None:
        raise IntervencionRechazada(
            f"El pedido está cerrado ({pedido.motivo_cierre}): RN-13 no admite cambios."
        )
    return pedido


async def confirmar_desembarco(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    ata: dt.datetime,
    motivo: str,
    id_usuario: int,
    confirmar: bool = False,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Registra la llegada real del pedido. **No hace commit.**

    Los cuatro criterios de `US-14`: la ATA manda sobre la ETA de la fuente
    (RN-14), una fecha futura se rechaza, sobrescribir una ATA ya confirmada
    exige `confirmar`, y todo queda recalculado y auditado.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    if ata.tzinfo is None:
        raise FechaInvalida("La llegada debe indicar la zona horaria (por ejemplo, -06:00).")
    if ata > ahora:
        raise FechaInvalida(
            f"La llegada no puede ser futura: {ata.isoformat()} es posterior a ahora."
        )
    pedido = await _pedido(sesion, id_pedido)
    anterior = pedido.ata_confirmada
    if anterior is not None and not confirmar:
        raise ConfirmacionRequerida(anterior)

    pedido.ata_confirmada = ata
    # Solo avanza: corregir la ATA de un pedido ya en aduana no lo devuelve.
    if estado.avanza(pedido.etapa_viaje, EN_DESTINO):
        pedido.etapa_viaje = EN_DESTINO
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo="CONFIRMACION_DESEMBARCO",
        campo="ata_confirmada",
        anterior=anterior,
        nuevo=ata,
        motivo=motivo,
        instante=ahora,
    )
    await sesion.flush()
    logger.info("Pedido %s: desembarco confirmado (%s).", pedido.tracking_interno, ata)
    return pedido


async def pasar_a_aduanal(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    motivo: str,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Pasa el pedido de «En destino» a «En proceso aduanal». **No hace commit.**"""
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    pedido = await _pedido(sesion, id_pedido)
    if pedido.etapa_viaje == EN_PROCESO_ADUANAL:
        raise IntervencionRechazada("El pedido ya está en proceso aduanal.")
    if pedido.etapa_viaje != EN_DESTINO:
        if estado.avanza(EN_PROCESO_ADUANAL, pedido.etapa_viaje):
            raise IntervencionRechazada(
                f"El pedido ya pasó el proceso aduanal (etapa {pedido.etapa_viaje})."
            )
        raise IntervencionRechazada(
            f"El pedido no ha llegado a destino (etapa {pedido.etapa_viaje}). "
            "Confirme primero el desembarco."
        )

    pedido.etapa_viaje = EN_PROCESO_ADUANAL
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo="PASO_A_ADUANAL",
        campo="etapa_viaje",
        anterior=EN_DESTINO,
        nuevo=EN_PROCESO_ADUANAL,
        motivo=motivo,
        instante=ahora,
    )
    await sesion.flush()
    logger.info("Pedido %s: pasa a proceso aduanal.", pedido.tracking_interno)
    return pedido


__all__ = [
    "ConfirmacionRequerida",
    "FechaInvalida",
    "IntervencionRechazada",
    "confirmar_desembarco",
    "pasar_a_aduanal",
]
