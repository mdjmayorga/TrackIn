"""Las intervenciones manuales sobre un pedido — `US-14` (y las que siguen).

Cada intervención hace tres cosas en la misma transacción, o ninguna:

1. **Cambia el pedido** —una fecha, una etapa—, validando antes todo lo que
   pueda rechazarla para no dejarlo a medias.
2. **Recalcula** fecha proyectada y estado (`US-12`): el cambio es un insumo.
3. **La audita** (`US-15`), con el autor de la sesión (`US-42`) y el motivo.

`US-40`: el ajuste manual de la fecha proyectada
-------------------------------------------------

RN-01 suma a la fecha proyectada un ajuste manual opcional: días que Logística
conoce y el sistema no —un feriado en el puerto, una inspección anunciada—. Se
guarda en `ajuste_manual_dias`, con signo, y **reemplaza** al anterior: no se
acumula. Se recalcula en el acto y la auditoría conserva el valor anterior y el
nuevo. Poner 0 es quitar el ajuste.

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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services import asociacion, auditoria, dias_habiles, estado, parametros, recalculo
from app.services.referencia import ResultadoReferencia, validar_referencia

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
    motivo: str | None,
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


#: El motivo que queda en la bitácora cuando el paso a aduana se registra sin uno.
MOTIVO_ADUANA_POR_OMISION = "Paso a proceso aduanal registrado sin motivo."


async def pasar_a_aduanal(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    motivo: str | None,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Pasa el pedido de «En destino» a «En proceso aduanal». **No hace commit.**

    **El motivo es opcional** (pedido del 27/10/2026): el paso a aduana es el
    trámite normal de todo pedido que llega, y escribir por qué en cada uno no
    aportaba nada. La bitácora lo registra igual, con quién y cuándo.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.motivo_opcional(motivo, por_omision=MOTIVO_ADUANA_POR_OMISION)
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
    motivo: str | None,
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
    motivo: str | None,
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
    motivo: str | None,
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


async def ajustar_fecha(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    dias: int,
    motivo: str | None,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """Fija el ajuste manual de RN-01 y recalcula. **No hace commit.**"""
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    pedido = await _pedido(sesion, id_pedido)
    anterior = pedido.ajuste_manual_dias
    if dias == anterior:
        raise IntervencionRechazada(
            f"El pedido ya tiene un ajuste de {anterior} d: no hay nada que cambiar."
        )

    pedido.ajuste_manual_dias = dias
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo="AJUSTE_MANUAL",
        campo="ajuste_manual_dias",
        anterior=anterior,
        nuevo=dias,
        motivo=motivo,
        instante=ahora,
    )
    await sesion.flush()
    logger.info("Pedido %s: ajuste manual %s → %s d.", pedido.tracking_interno, anterior, dias)
    return pedido


#: Las etapas en que la llegada todavía no se conoce: después, una ETA no aporta.
_SIN_LLEGADA = frozenset({"SIN_TRACKING", "EN_ORIGEN", "EN_TRANSITO"})


async def registrar_eta(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    eta: dt.date | None,
    motivo: str | None,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> PedidoTransito:
    """`US-67`: la ETA a Costa Rica, a mano, y recalcula. **No hace commit.**

    Para cuando la fuente no la da —la guía termina en un transbordo—. Reemplaza
    a la anterior; `None` la quita. Si la fuente vuelve a dar una ETA a uno de
    nuestros destinos, esa manda (RN-14).
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    pedido = await _pedido(sesion, id_pedido)
    if pedido.etapa_viaje not in _SIN_LLEGADA:
        raise IntervencionRechazada(
            "El pedido ya llegó a destino: la fecha base es la llegada, no una ETA."
        )
    anterior = pedido.eta_manual
    if eta == anterior:
        raise IntervencionRechazada("El pedido ya tiene esa ETA: no hay nada que cambiar.")

    pedido.eta_manual = eta
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo="ETA_MANUAL",
        campo="eta_manual",
        anterior=anterior,
        nuevo=eta,
        motivo=motivo,
        instante=ahora,
    )
    await sesion.flush()
    logger.info("Pedido %s: ETA manual %s → %s.", pedido.tracking_interno, anterior, eta)
    return pedido


class ReferenciaInvalida(ValueError):
    """La referencia no pasa la validación de `TASK-30`: formato o dígito de control."""


async def asociar_identificador(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    tipo: str,
    numero: str,
    motivo: str | None,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> ResultadoReferencia:
    """Asocia la referencia de embarque a un pedido sin ella (`US-20`, §4.7). **No hace commit.**

    Es la entrada manual para lo que la carga hace desde las columnas de
    referencia del Z-tracking: el mismo servicio (`asociacion`), con usuario y
    motivo para RF-14. Solo para pedidos **sin** identificador: cambiar el de
    un pedido que ya lo tiene es un transbordo (`US-30`), que conserva el tramo
    anterior; reemplazarlo aquí lo borraría del historial.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    motivo = auditoria.validar_motivo(motivo)
    pedido = await _pedido(sesion, id_pedido)
    if pedido.id_elemento_rastreado is not None:
        raise IntervencionRechazada(
            "El pedido ya tiene identificador de rastreo. Cambiarlo es un transbordo "
            "(US-30), que conserva el tramo anterior."
        )

    resultado = await asociacion.asociar_referencia(
        sesion, pedido, tipo, numero, id_usuario=id_usuario, motivo=motivo
    )
    if not resultado.valida:
        raise ReferenciaInvalida(resultado.motivo)

    # Sale de `SIN_TRACKING`: el estado y la fecha se rehacen con el vínculo.
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    await sesion.flush()
    logger.info(
        "Pedido %s: referencia %s:%s asociada a mano.",
        pedido.tracking_interno,
        resultado.tipo,
        resultado.numero,
    )
    return resultado


async def _cambiar_elemento(
    sesion: AsyncSession,
    pedido: PedidoTransito,
    actual: ElementoRastreado,
    tipo: str,
    numero: str,
    *,
    tipo_intervencion: str,
    motivo: str,
    id_usuario: int,
    ahora: dt.datetime,
) -> ResultadoReferencia:
    """Cierra el tramo vigente y abre uno con otra referencia, y lo audita.

    Lo comparten la guía madre (`US-30`) y la corrección de una referencia: en
    los dos casos el historial del elemento anterior queda en su tramo
    (`pedido_elemento_rastreado`), como pedía RF-26. Quien llama ya validó la
    referencia nueva.
    """
    tramos = list(
        await sesion.scalars(
            select(PedidoElementoRastreado)
            .where(PedidoElementoRastreado.id_pedido == pedido.id)
            .order_by(PedidoElementoRastreado.tramo)
        )
    )
    vigente = next((t for t in tramos if t.fecha_hasta is None), None)
    if vigente is None:
        # El elemento se asoció sin tramo (la carga y la asociación no lo abren):
        # se crea ahora para que su historial quede como el tramo anterior.
        vigente = PedidoElementoRastreado(
            id_pedido=pedido.id,
            id_elemento_rastreado=actual.id,
            tramo=(tramos[-1].tramo if tramos else 0) + 1,
            fecha_desde=pedido.creado_en or ahora,
        )
        sesion.add(vigente)
    vigente.fecha_hasta = ahora
    await sesion.flush()

    anterior = f"{actual.tipo_tracking_externo}:{actual.tracking_externo}"
    # Sin usuario: el registro de esta intervención es el de abajo.
    resultado = await asociacion.asociar_referencia(sesion, pedido, tipo, numero)
    if not resultado.valida:
        raise ReferenciaInvalida(resultado.motivo)
    # El FK cambió, pero la relación del pedido puede seguir en memoria con el
    # elemento anterior (si ya se había cargado): se vuelve a leer.
    await sesion.flush()
    await sesion.refresh(pedido, attribute_names=["elemento_rastreado"])

    sesion.add(
        PedidoElementoRastreado(
            id_pedido=pedido.id,
            id_elemento_rastreado=pedido.id_elemento_rastreado,
            tramo=vigente.tramo + 1,
            fecha_desde=ahora,
            motivo=motivo[:200],
        )
    )
    auditoria.registrar(
        sesion,
        id_pedido=pedido.id,
        id_usuario=id_usuario,
        tipo=tipo_intervencion,
        campo="id_elemento_rastreado",
        anterior=anterior,
        nuevo=f"{resultado.tipo}:{resultado.numero}",
        motivo=motivo,
        instante=ahora,
    )
    return resultado


#: El motivo de una corrección de referencia sin motivo escrito.
MOTIVO_CORRECCION_POR_OMISION = "Corrección de la referencia de embarque."


async def corregir_referencia(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    tipo: str,
    numero: str,
    motivo: str | None,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> ResultadoReferencia:
    """Corrige la referencia de un pedido que ya tiene una (29/10/2026). **No hace commit.**

    Para los errores de transcripción: un BL escrito con «BL» delante, o con un
    dígito de menos, no lo encuentra ShipsGo y el pedido se queda sin posición.
    Hasta ahora una referencia asociada no se podía cambiar. El tramo de la
    equivocada se cierra —su historial se conserva— y se abre uno con la buena;
    queda en la bitácora como `ASOCIACION_TRACKING`, con la anterior y la nueva.
    El motivo es opcional. Si la buena no está en ShipsGo, queda pendiente de alta.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    pedido = await _pedido(sesion, id_pedido)
    actual = (
        await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
        if pedido.id_elemento_rastreado is not None
        else None
    )
    if actual is None:
        raise IntervencionRechazada(
            "El pedido no tiene referencia: asóciela en lugar de corregirla."
        )
    # Se valida antes de tocar los tramos: una referencia mal escrita no cierra nada.
    validacion = validar_referencia(tipo, numero, pedido.via_transporte)
    if not validacion.valida:
        raise ReferenciaInvalida(validacion.motivo)
    assert validacion.tipo is not None and validacion.numero is not None
    if (
        validacion.tipo == actual.tipo_tracking_externo
        and validacion.numero == actual.tracking_externo
    ):
        raise IntervencionRechazada("El pedido ya tiene esa referencia.")
    motivo = auditoria.motivo_opcional(motivo, por_omision=MOTIVO_CORRECCION_POR_OMISION)

    resultado = await _cambiar_elemento(
        sesion,
        pedido,
        actual,
        validacion.tipo,
        validacion.numero,
        tipo_intervencion="ASOCIACION_TRACKING",
        motivo=motivo,
        id_usuario=id_usuario,
        ahora=ahora,
    )
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    await sesion.flush()
    logger.info(
        "Pedido %s: referencia corregida de %s:%s a %s:%s.",
        pedido.tracking_interno,
        actual.tipo_tracking_externo,
        actual.tracking_externo,
        resultado.tipo,
        resultado.numero,
    )
    return resultado


#: El motivo en la bitácora cuando se sigue por la guía madre sin escribir uno.
MOTIVO_GUIA_MADRE_POR_OMISION = "Se sigue por la guía madre que resolvió TICA."
MOTIVO_GUIA_MADRE_A_MANO = "Guía madre indicada a mano."
MOTIVO_GUIA_MADRE_CORREGIDA = "Corrección de la guía madre."


async def guia_hija_de_origen(sesion: AsyncSession, id_pedido: int) -> ElementoRastreado | None:
    """La guía hija de la que pasó el pedido a su guía madre, si lo hizo (`US-30`)."""
    hija: ElementoRastreado | None = await sesion.scalar(
        select(ElementoRastreado)
        .join(
            PedidoElementoRastreado,
            PedidoElementoRastreado.id_elemento_rastreado == ElementoRastreado.id,
        )
        .where(
            PedidoElementoRastreado.id_pedido == id_pedido,
            PedidoElementoRastreado.fecha_hasta.is_not(None),
            ElementoRastreado.tipo_tracking_externo == "HAWB",
        )
        .order_by(PedidoElementoRastreado.tramo.desc())
        .limit(1)
    )
    return hija


def _misma_guia(a: str | None, b: str | None) -> bool:
    limpia = [(x or "").replace("-", "").replace(" ", "").upper() for x in (a, b)]
    return bool(limpia[0]) and limpia[0] == limpia[1]


async def seguir_guia_madre(
    sesion: AsyncSession,
    id_pedido: int,
    *,
    numero: str | None = None,
    motivo: str | None,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> ResultadoReferencia:
    """Asocia al pedido la guía madre de su guía hija, o la corrige (`US-30`).

    **La excepción manual del transbordo** (agregada el 21/10/2026). Una HAWB no
    la sigue ninguna fuente comercial; la MAWB que la ampara, sí. Es el mismo
    mecanismo que un transbordo: se cierra el tramo vigente —su historial se
    conserva en `pedido_elemento_rastreado`— y se abre otro con la madre.

    Tres casos (ampliado el 29/10/2026):

    - **Guía hija, madre resuelta por TICA** (`US-49`): sin `numero`, se usa esa.
    - **Guía hija, madre escrita a mano** —TICA todavía no la resolvió, o la
      resolvió mal y el agente dio la correcta—: `numero`.
    - **Ya se sigue por una guía madre que vino de una hija, y era la
      equivocada:** `numero` con la correcta. Corrige sin perder el tramo.

    El motivo es opcional, como el paso a aduana. **No hace commit.** La guía
    madre queda pendiente de alta en ShipsGo (`US-55`): eso cuesta un crédito y
    lo decide Compras.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    pedido = await _pedido(sesion, id_pedido)
    actual = (
        await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
        if pedido.id_elemento_rastreado is not None
        else None
    )
    numero = (numero or "").strip() or None

    if actual is not None and actual.tipo_tracking_externo == "HAWB":
        destino = numero or actual.guia_madre
        if destino is None:
            raise IntervencionRechazada(
                "TICA todavía no resolvió la guía madre de esta guía hija (aparece cerca del "
                "arribo). Si la conoce, escríbala."
            )
        por_omision = MOTIVO_GUIA_MADRE_A_MANO if numero else MOTIVO_GUIA_MADRE_POR_OMISION
    elif (
        actual is not None
        and actual.tipo_tracking_externo == "MAWB"
        and await guia_hija_de_origen(sesion, pedido.id) is not None
    ):
        if numero is None:
            raise IntervencionRechazada("Escriba la guía madre correcta.")
        if _misma_guia(numero, actual.tracking_externo):
            raise IntervencionRechazada("El pedido ya se sigue por esa guía madre.")
        destino = numero
        por_omision = MOTIVO_GUIA_MADRE_CORREGIDA
    else:
        raise IntervencionRechazada(
            "Solo un pedido que se sigue por una guía hija (HAWB), o por la guía madre a la "
            "que pasó desde una."
        )

    # Se valida antes de tocar los tramos: una guía mal escrita no cierra nada.
    validacion = validar_referencia("MAWB", destino, pedido.via_transporte)
    if not validacion.valida:
        raise ReferenciaInvalida(validacion.motivo)
    motivo = auditoria.motivo_opcional(motivo, por_omision=por_omision)

    resultado = await _cambiar_elemento(
        sesion,
        pedido,
        actual,
        "MAWB",
        destino,
        tipo_intervencion="TRANSBORDO",
        motivo=motivo,
        id_usuario=id_usuario,
        ahora=ahora,
    )
    await recalculo.recalcular(sesion, pedido, instante=ahora)
    await sesion.flush()
    logger.info(
        "Pedido %s: de %s:%s a la guía madre %s.",
        pedido.tracking_interno,
        actual.tipo_tracking_externo,
        actual.tracking_externo,
        resultado.numero,
    )
    return resultado


__all__ = [
    "MOTIVO_CORRECCION_POR_OMISION",
    "corregir_referencia",
    "MOTIVO_GUIA_MADRE_A_MANO",
    "MOTIVO_GUIA_MADRE_CORREGIDA",
    "MOTIVO_GUIA_MADRE_POR_OMISION",
    "guia_hija_de_origen",
    "seguir_guia_madre",
    "RecepcionIncompleta",
    "ReferenciaInvalida",
    "ajustar_fecha",
    "asociar_identificador",
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
