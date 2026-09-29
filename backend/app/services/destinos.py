"""Cambios al maestro de destinos que mueven fechas — `US-12`.

El lead time de un destino es un sumando de RN-01: cambiarlo cambia la fecha
proyectada de cada pedido activo que va a ese destino. Por eso no se edita la
columna a secas: se edita **por aquí**, que guarda y recalcula en la misma
transacción. Si el recálculo se dejara para después, la grilla mostraría fechas
hechas con el valor viejo, que es justo lo que `US-12` prohíbe.

La pantalla del maestro es `US-13`. Ella añadirá lo que es de administración
—alta, baja con advertencia, duplicados—; lo que vive aquí es solo la regla
que la conecta con el cálculo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maestro_destino import MaestroDestino
from app.services import recalculo

logger = logging.getLogger(__name__)


class LeadTimeInvalido(ValueError):
    """El valor no es un número entero de días, o es negativo."""


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


__all__ = ["CambioLeadTime", "LeadTimeInvalido", "cambiar_lead_time", "validar_lead_time"]
