"""Las intervenciones manuales sobre un pedido — `US-14` (y las que siguen).

Cada intervención hace tres cosas en la misma transacción, o ninguna:

1. **Cambia el pedido** —una fecha, una etapa—, validando antes todo lo que
   pueda rechazarla para no dejarlo a medias.
2. **Recalcula** fecha proyectada y estado (`US-12`): el cambio es un insumo.
3. **La audita** (`US-15`), con el autor de la sesión (`US-42`) y el motivo.

`US-40` se suma aquí con el mismo esquema.

`US-47`: la liberación de Calidad cierra el pedido
--------------------------------------------------

«Cerrado» significa **disponible para producción**. Al recibir en planta se
estima la ventana de RN-19 —de 7 a 15 días hábiles—, que es un **rango** y se
guarda como tal. Calidad puede liberar por partes: cada liberación suma a
`cantidad_liberada` y la línea **sigue activa** hasta que lo liberado llega a lo
recibido. Entonces cierra como `RECEPCION_CONFORME`: la recepción fue conforme y
el material ya se puede usar. No se libera más de lo que entró a planta.

`US-18`: la recepción en planta ya no cierra el pedido
-------------------------------------------------------

Desde la reunión con Planeación del 04/09, la carga que entra a planta queda
«Recibido en planta» y **sigue activa**: no se puede usar hasta que Control de
Calidad la libere (`US-47`). RN-10 decide si la recepción es conforme:

- **Dentro de la tolerancia** (`tolerancia_recepcion_pct`, 10 %): el pedido
  pasa a «Recibido en planta», sin cerrarse.
- **Por debajo:** el pedido **no avanza** y se ofrece el cierre forzado, que es
  otro acto (`cerrar_forzado`): registra la recepción parcial y cierra.

Recibir de más no lo impide: RN-10 habla de *satisfacer* lo pedido.

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
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido_transito import PedidoTransito
from app.services import auditoria, dias_habiles, estado, parametros, recalculo

logger = logging.getLogger(__name__)

EN_DESTINO = "EN_DESTINO"
EN_PROCESO_ADUANAL = "EN_PROCESO_ADUANAL"
RECIBIDO_EN_PLANTA = "RECIBIDO_EN_PLANTA"

#: La hora local decide qué día se recibió: recibir a las 20:00 del viernes en
#: Costa Rica ya es sábado en UTC, y la ventana de Calidad empezaría mal.
ZONA_CR = dt.timezone(dt.timedelta(hours=-6), "America/Costa_Rica")


class IntervencionRechazada(Exception):
    """El pedido no admite esta intervención en su estado actual (409)."""


class FechaInvalida(ValueError):
    """La fecha no se puede aceptar: futura, o sin zona horaria (422)."""


class RecepcionIncompleta(Exception):
    """Lo recibido no llega al mínimo de RN-10: no avanza, se ofrece cerrar a la fuerza."""

    def __init__(self, recibida: Decimal, pedida: Decimal, minimo: Decimal) -> None:
        self.recibida = recibida
        self.pedida = pedida
        self.minimo = minimo
        super().__init__(
            f"Se recibió {recibida} de {pedida}: por debajo del mínimo conforme ({minimo}). "
            "El pedido no avanza. Si no va a llegar el resto, puede registrar un cierre forzado."
        )


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


def _validar_fecha(fecha: dt.datetime, ahora: dt.datetime, que: str) -> None:
    if fecha.tzinfo is None:
        raise FechaInvalida(f"La {que} debe indicar la zona horaria (por ejemplo, -06:00).")
    if fecha > ahora:
        raise FechaInvalida(f"La {que} no puede ser futura: {fecha.isoformat()}.")


def _validar_cantidad(cantidad: Decimal) -> Decimal:
    if cantidad < 0:
        raise FechaInvalida("La cantidad recibida no puede ser negativa.")
    return cantidad


async def _en_aduana(sesion: AsyncSession, id_pedido: int) -> PedidoTransito:
    """El pedido, si está en el paso previo a la recepción."""
    pedido = await _pedido(sesion, id_pedido)
    if pedido.etapa_viaje == RECIBIDO_EN_PLANTA:
        raise IntervencionRechazada(
            "El pedido ya se recibió en planta; ahora lo cierra la liberación de Calidad."
        )
    if pedido.etapa_viaje != EN_PROCESO_ADUANAL:
        raise IntervencionRechazada(
            f"La carga no puede entrar a planta sin pasar aduana (etapa {pedido.etapa_viaje}). "
            "Páselo primero a proceso aduanal."
        )
    return pedido


async def minimo_conforme(sesion: AsyncSession, pedida: Decimal) -> Decimal:
    """Lo mínimo que hay que recibir para que la recepción sea conforme (RN-10)."""
    tolerancia = await parametros.obtener_decimal(sesion, "tolerancia_recepcion_pct")
    return (pedida * (Decimal(100) - tolerancia) / Decimal(100)).quantize(Decimal("0.001"))


async def registrar_recepcion(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    fecha: dt.datetime,
    cantidad: Decimal,
    motivo: str,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Registra la entrada a planta. **No cierra el pedido. No hace commit.**

    Por debajo de la tolerancia lanza `RecepcionIncompleta` sin tocar nada:
    el pedido no avanza y quien llama ofrece el cierre forzado.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    _validar_fecha(fecha, ahora, "recepción")
    cantidad = _validar_cantidad(cantidad)
    pedido = await _en_aduana(sesion, id_pedido)
    minimo = await minimo_conforme(sesion, pedido.cantidad_pedida)
    if cantidad < minimo:
        raise RecepcionIncompleta(cantidad, pedido.cantidad_pedida, minimo)

    pedido.fecha_recepcion_planta = fecha
    pedido.cantidad_recibida = cantidad
    pedido.etapa_viaje = RECIBIDO_EN_PLANTA
    (
        pedido.fecha_liberacion_estimada_desde,
        pedido.fecha_liberacion_estimada_hasta,
    ) = await estimar_liberacion(sesion, fecha)
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo="RECEPCION_PLANTA",
        campo="cantidad_recibida",
        anterior=None,
        nuevo=(
            f"{auditoria.como_texto(cantidad)} {pedido.unidad_medida} "
            f"el {auditoria.como_texto(fecha)}"
        ),
        motivo=motivo,
        instante=ahora,
    )
    await sesion.flush()
    logger.info("Pedido %s: recibido en planta (%s).", pedido.tracking_interno, cantidad)
    return pedido


async def cerrar_forzado(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    fecha: dt.datetime,
    cantidad: Decimal,
    motivo: str,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Cierra un pedido con una recepción parcial (RN-10, RN-13). **No hace commit.**

    Deja dos asientos en la bitácora: la recepción, con la cantidad, y el
    cierre, con el motivo. El cumplimiento se congela como veredicto: dice si el
    proveedor cumplió (`wireframes.md` §1.11).
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    _validar_fecha(fecha, ahora, "recepción")
    cantidad = _validar_cantidad(cantidad)
    pedido = await _en_aduana(sesion, id_pedido)

    pedido.fecha_recepcion_planta = fecha
    pedido.cantidad_recibida = cantidad
    pedido.motivo_cierre = "CIERRE_FORZADO"
    pedido.estado_calculado = estado.derivar_estado_calculado(
        pedido.etapa_viaje, pedido.estado_cumplimiento, pedido.motivo_cierre
    )
    for tipo, campo, nuevo in (
        (
            "RECEPCION_PLANTA",
            "cantidad_recibida",
            f"{auditoria.como_texto(cantidad)} {pedido.unidad_medida}",
        ),
        ("CIERRE_FORZADO", "motivo_cierre", "CIERRE_FORZADO"),
    ):
        auditoria.registrar(
            sesion,
            id_pedido=pedido.id,
            id_usuario=id_usuario,
            tipo=tipo,
            campo=campo,
            anterior=None,
            nuevo=nuevo,
            motivo=motivo,
            instante=ahora,
        )
    await sesion.flush()
    logger.info("Pedido %s: cierre forzado con %s recibido.", pedido.tracking_interno, cantidad)
    return pedido


async def estimar_liberacion(
    sesion: AsyncSession, recibido: dt.datetime
) -> tuple[dt.date, dt.date]:
    """La ventana de Calidad de RN-19: el rango, en días hábiles desde la recepción."""
    minimo = await parametros.obtener_entero(sesion, "ventana_calidad_habiles_min")
    maximo = await parametros.obtener_entero(sesion, "ventana_calidad_habiles_max")
    dia = recibido.astimezone(ZONA_CR).date()
    return (
        dias_habiles.sumar_dias_habiles(dia, minimo),
        dias_habiles.sumar_dias_habiles(dia, max(minimo, maximo)),
    )


async def liberar_calidad(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    fecha: dt.datetime,
    cantidad: Decimal,
    motivo: str,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Registra una liberación de Calidad; con el total, cierra. **No hace commit.**

    Una liberación parcial suma a `cantidad_liberada` y deja la línea activa.
    El cumplimiento no se recalcula al cerrar: queda como veredicto, igual que
    en el cierre forzado.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    _validar_fecha(fecha, ahora, "liberación")
    if cantidad <= 0:
        raise FechaInvalida("La cantidad liberada debe ser mayor que cero.")
    pedido = await _pedido(sesion, id_pedido)
    if pedido.etapa_viaje != RECIBIDO_EN_PLANTA or pedido.fecha_recepcion_planta is None:
        raise IntervencionRechazada(
            f"Calidad solo libera lo que ya se recibió en planta (etapa {pedido.etapa_viaje}). "
            "Registre primero la recepción."
        )
    if fecha < pedido.fecha_recepcion_planta:
        raise FechaInvalida(
            "La liberación no puede ser anterior a la recepción en planta "
            f"({auditoria.como_texto(pedido.fecha_recepcion_planta)})."
        )
    recibida = pedido.cantidad_recibida or Decimal(0)
    anterior = pedido.cantidad_liberada or Decimal(0)
    liberada = anterior + cantidad
    if liberada > recibida:
        raise FechaInvalida(
            f"No se puede liberar más de lo recibido: hay {anterior} liberado de "
            f"{recibida} recibido, y {cantidad} lo excede."
        )

    pedido.cantidad_liberada = liberada
    completa = liberada == recibida
    if completa:
        pedido.fecha_liberacion_calidad = fecha
        pedido.motivo_cierre = "RECEPCION_CONFORME"
        pedido.estado_calculado = estado.derivar_estado_calculado(
            pedido.etapa_viaje, pedido.estado_cumplimiento, pedido.motivo_cierre
        )
    de_lo_recibido = f"de {auditoria.como_texto(recibida)} {pedido.unidad_medida}"
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo="LIBERACION_CALIDAD",
        campo="cantidad_liberada",
        anterior=f"{auditoria.como_texto(anterior)} {de_lo_recibido}",
        nuevo=(
            f"{auditoria.como_texto(liberada)} {de_lo_recibido} "
            f"el {auditoria.como_texto(fecha)}"
        ),
        motivo=motivo,
        instante=ahora,
    )
    await sesion.flush()
    logger.info(
        "Pedido %s: Calidad liberó %s de %s%s.",
        pedido.tracking_interno,
        liberada,
        recibida,
        "; cerrado" if completa else "",
    )
    return pedido


__all__ = [
    "RecepcionIncompleta",
    "ZONA_CR",
    "estimar_liberacion",
    "liberar_calidad",
    "cerrar_forzado",
    "minimo_conforme",
    "registrar_recepcion",
    "ConfirmacionRequerida",
    "FechaInvalida",
    "IntervencionRechazada",
    "confirmar_desembarco",
    "pasar_a_aduanal",
]
