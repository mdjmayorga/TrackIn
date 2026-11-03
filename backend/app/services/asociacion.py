"""Asociación de una referencia de embarque a un pedido — RF-03.

`US-01`. Toma la referencia validada por `app.services.referencia` y la vincula
al pedido, creando o reutilizando el `ElementoRastreado` correspondiente.

Reutilizar importa: varias líneas de orden de compra viajan en el **mismo**
contenedor o bajo la misma guía aérea, y duplicar el elemento multiplicaría las
consultas a la fuente —que se cobran por envío rastreado— sin aportar nada.

El vínculo obliga a mover la etapa: el modelo garantiza por `CHECK` que un
pedido tiene elemento **si y solo si** su etapa no es `SIN_TRACKING` (RN-02).
Asociar sin cambiar la etapa haría fallar la base, y así debe ser.
"""

from __future__ import annotations

import logging

from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services import auditoria
from app.services.referencia import ResultadoReferencia, validar_referencia

logger = logging.getLogger(__name__)

#: Etapa a la que pasa un pedido al quedar asociado. `EN_ORIGEN` es la primera
#: del ciclo (RN-03): hay nave o guía, pero todavía no ha zarpado. El motor de
#: `US-10` la moverá cuando lleguen posiciones.
ETAPA_AL_ASOCIAR = "EN_ORIGEN"


#: Los identificadores de un **vehículo**, que se reciclan: un MMSI vuelve a
#: asignarse años después y el elemento viejo no debe revivir (§4.3 del modelo).
_RECICLABLES = frozenset({"MMSI", "ICAO24"})


async def obtener_o_crear_elemento(
    sesion: AsyncSession,
    tipo: str,
    numero: str,
    via_transporte: str,
) -> ElementoRastreado:
    """Devuelve el elemento con esa referencia, o lo crea.

    **Un BL, contenedor, booking o guía es un solo embarque**, aunque ya haya
    llegado (03/11/2026): se reutiliza el que exista, activo o no. La unicidad
    *mientras esté activo* de §4.3 del modelo se pensó para el MMSI, que una
    naviera recicla años después; estas referencias no se reciclan. Reutilizar
    solo el activo dejaba un BL repetido cada vez que se volvía a asociar uno ya
    llegado —al corregir `BLMAEU274029064` el 02/11—, y el mapa lo dibujaba dos
    veces.

    Si estaba inactivo se **reactiva**: el worker lo vuelve a leer (leer no
    cuesta créditos), aplica la llegada al pedido nuevo y lo apaga otra vez
    cuando todos sus pedidos arribaron (`arribo`, decisión B7).
    """
    existentes = (
        await sesion.scalars(
            select(ElementoRastreado).where(
                ElementoRastreado.tipo_tracking_externo == tipo,
                ElementoRastreado.tracking_externo == numero,
                # Un MMSI o un ICAO24 solo se reutiliza activo.
                ElementoRastreado.activo.is_(True) if tipo in _RECICLABLES else true(),
            )
            # El activo primero (hay a lo sumo uno); si no, el más reciente.
            .order_by(ElementoRastreado.activo.desc(), ElementoRastreado.id.desc())
        )
    ).all()
    if existentes:
        existente = existentes[0]
        if not existente.activo:
            existente.activo = True
            logger.info("Elemento %s %s reactivado: se asocia a otro pedido.", tipo, numero)
        return existente

    elemento = ElementoRastreado(
        tipo_tracking_externo=tipo,
        tracking_externo=numero,
        via_transporte=via_transporte,
    )
    sesion.add(elemento)
    await sesion.flush()  # asigna el id sin cerrar la transacción
    return elemento


async def asociar_referencia(
    sesion: AsyncSession,
    pedido: PedidoTransito,
    tipo: str | None,
    numero: str | None,
    *,
    id_usuario: int | None = None,
    motivo: str = "Asociación del identificador de rastreo",
) -> ResultadoReferencia:
    """Vincula la referencia al pedido. No hace commit: eso es de quien llama.

    Devuelve el veredicto de la validación. Si la referencia no es válida, el
    pedido **no se toca** y el motivo explica por qué.
    """
    # La vía del pedido decide qué tipos admite (21/10): vale para la carga y para
    # la asociación a mano, que pasan las dos por aquí.
    resultado = validar_referencia(tipo, numero, pedido.via_transporte)
    if not resultado.valida:
        logger.info("Pedido %s: referencia rechazada — %s", pedido, resultado.motivo)
        return resultado

    assert resultado.tipo is not None and resultado.numero is not None

    elemento = await obtener_o_crear_elemento(
        sesion, resultado.tipo, resultado.numero, pedido.via_transporte
    )

    anterior = pedido.id_elemento_rastreado
    pedido.id_elemento_rastreado = elemento.id
    # El CHECK de RN-02 exige que la etapa deje de ser SIN_TRACKING en cuanto
    # hay elemento asociado.
    if pedido.etapa_viaje == "SIN_TRACKING":
        pedido.etapa_viaje = ETAPA_AL_ASOCIAR
        if pedido.estado_calculado == "SIN_TRACKING":
            pedido.estado_calculado = ETAPA_AL_ASOCIAR

    # RF-14: toda intervención manual queda registrada (`US-15`). La carga del
    # archivo asocia sin usuario —no es una intervención manual—, y entonces
    # no hay nada que auditar.
    if id_usuario is not None:
        auditoria.registrar(
            sesion,
            id_pedido=pedido.id,
            id_usuario=id_usuario,
            tipo="ASOCIACION_TRACKING",
            campo="id_elemento_rastreado",
            anterior=anterior,
            nuevo=f"{resultado.tipo}:{resultado.numero}",
            motivo=motivo,
        )

    if not resultado.rastreable:
        logger.info(
            "Pedido %s: referencia %s guardada, sin rastreo automático — %s",
            pedido,
            resultado.numero,
            resultado.motivo,
        )
    return resultado


__all__ = ["ETAPA_AL_ASOCIAR", "asociar_referencia", "obtener_o_crear_elemento"]
