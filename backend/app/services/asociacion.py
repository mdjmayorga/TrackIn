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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services.referencia import ResultadoReferencia, validar_referencia

logger = logging.getLogger(__name__)

#: Etapa a la que pasa un pedido al quedar asociado. `EN_ORIGEN` es la primera
#: del ciclo (RN-03): hay nave o guía, pero todavía no ha zarpado. El motor de
#: `US-10` la moverá cuando lleguen posiciones.
ETAPA_AL_ASOCIAR = "EN_ORIGEN"


async def obtener_o_crear_elemento(
    sesion: AsyncSession,
    tipo: str,
    numero: str,
    via_transporte: str,
) -> ElementoRastreado:
    """Devuelve el elemento activo con esa referencia, o lo crea.

    La unicidad es *mientras esté activo* (§4.3 del modelo): un MMSI puede
    reutilizarse años después, pero no puede haber dos filas activas con el
    mismo identificador.
    """
    existente = await sesion.scalar(
        select(ElementoRastreado).where(
            ElementoRastreado.tipo_tracking_externo == tipo,
            ElementoRastreado.tracking_externo == numero,
            ElementoRastreado.activo.is_(True),
        )
    )
    if existente is not None:
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
    resultado = validar_referencia(tipo, numero)
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

    # RF-14: toda intervención manual queda registrada. Con login (US-42) el
    # usuario vendrá de la sesión; hasta entonces puede no haberlo.
    if id_usuario is not None:
        sesion.add(
            AuditoriaIntervencion(
                id_pedido=pedido.id,
                id_usuario=id_usuario,
                tipo_intervencion="ASOCIACION_TRACKING",
                campo_afectado="id_elemento_rastreado",
                valor_anterior=str(anterior) if anterior is not None else None,
                valor_nuevo=f"{resultado.tipo}:{resultado.numero}",
                motivo=motivo,
            )
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
