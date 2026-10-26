"""Altas en ShipsGo desde TrackIn, una o en bloque — `US-55`.

Reunión con Compras del 29/09/2026: hay presupuesto para los créditos, y las
altas **las autorizan los usuarios de Compras** (y el Administrador). Con la
carga semanal del Z-tracking (22/10/2026), cada martes entran unas 20 a 25
referencias nuevas a la vez: por eso el alta es **en bloque**, no solo de a una.

Qué está pendiente
-------------------

Una referencia está pendiente cuando la tiene un pedido activo, es de las que
ShipsGo sigue —BL, contenedor, booking o MAWB— y **no** está en la cuenta de
ShipsGo. Eso se sabe listando la cuenta (`indice_shipsgo`), que es gratis. Se
agrupan por referencia porque ShipsGo cobra **por embarque**, no por línea: un BL
que llevan tres OC cuesta un solo crédito.

Para una MAWB, el catálogo de aerolíneas —también gratis— dice de antemano si la
guía resolverá (`US-46`). Una sin cobertura se muestra pero no se ofrece: darla de
alta costaría un crédito y devolvería vacío.

Las guardas antes de gastar
----------------------------

Cada alta pasa por `registro_embarque.registrar`, que valida la referencia, su
tipo según la vía del pedido y el catálogo, y la audita con el costo (RF-14). Esta
capa agrega lo que tiene sentido para un bloque: solo se da de alta lo que está
pendiente, quien autoriza confirma **cuántos créditos** se van a gastar, y el tope
diario (`altas_maximas_dia`) se advierte antes, no después.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services.rastreo import registro_embarque
from app.services.rastreo.indice_shipsgo import clave_referencia
from app.services.rastreo.shipsgo_aerolineas import CatalogoAerolineas
from app.services.rastreo.shipsgo_cliente import ClienteShipsGo, ErrorShipsGo

logger = logging.getLogger(__name__)

#: Los tipos que ShipsGo da de alta (`referencia._FUENTE_POR_TIPO`).
TIPOS_SHIPSGO: Final = frozenset({"BL", "CONTENEDOR", "BOOKING", "MAWB"})


@dataclass(frozen=True, slots=True)
class LineaPendiente:
    id_pedido: int
    oc_numero: str
    posicion_oc: int


@dataclass(slots=True)
class Pendiente:
    """Una referencia que tienen pedidos activos y que no está en ShipsGo."""

    tipo: str
    numero: str
    via: str
    lineas: list[LineaPendiente] = field(default_factory=list)
    #: Solo para MAWB: si el catálogo de aerolíneas la cubre. `None` si no aplica
    #: (marítimo) o si el catálogo no se pudo leer, que no es lo mismo que «no».
    cubierta: bool | None = None
    aerolinea: str | None = None

    @property
    def ofrecible(self) -> bool:
        """Se puede dar de alta: todo menos una MAWB que el catálogo no cubre."""
        return self.cubierta is not False


async def pendientes(
    sesion: AsyncSession,
    indice: dict[str, tuple[int, bool]],
    catalogo: CatalogoAerolineas | None = None,
) -> list[Pendiente]:
    """Las referencias de pedidos activos que todavía no están en la cuenta."""
    filas = await sesion.execute(
        select(PedidoTransito, ElementoRastreado)
        .join(ElementoRastreado, ElementoRastreado.id == PedidoTransito.id_elemento_rastreado)
        .where(
            PedidoTransito.motivo_cierre.is_(None),
            PedidoTransito.ausente_desde.is_(None),
            ElementoRastreado.activo.is_(True),
            ElementoRastreado.tipo_tracking_externo.in_(TIPOS_SHIPSGO),
        )
        .order_by(PedidoTransito.oc_numero, PedidoTransito.posicion_oc)
    )
    por_elemento: dict[int, Pendiente] = {}
    for pedido, elemento in filas.tuples():
        if clave_referencia(elemento.tracking_externo) in indice:
            continue
        pendiente = por_elemento.get(elemento.id)
        if pendiente is None:
            pendiente = Pendiente(
                tipo=elemento.tipo_tracking_externo,
                numero=elemento.tracking_externo,
                via=elemento.via_transporte,
            )
            if pendiente.tipo == "MAWB" and catalogo:
                aerolinea = catalogo.resolver(pendiente.numero)
                pendiente.cubierta = aerolinea is not None
                pendiente.aerolinea = aerolinea.nombre if aerolinea else None
            por_elemento[elemento.id] = pendiente
        pendiente.lineas.append(LineaPendiente(pedido.id, pedido.oc_numero, pedido.posicion_oc))
    return list(por_elemento.values())


@dataclass(frozen=True, slots=True)
class ResultadoAltaReferencia:
    tipo: str
    numero: str
    registrado: bool
    motivo: str
    consumio_credito: bool = False


async def dar_de_alta(
    sesion: AsyncSession,
    cliente: ClienteShipsGo,
    elegidas: Sequence[Pendiente],
    *,
    id_usuario: int,
    catalogo: CatalogoAerolineas | None = None,
) -> list[ResultadoAltaReferencia]:
    """Da de alta cada referencia elegida. **No hace commit.**

    Una que falla —ShipsGo caído, referencia rechazada— no detiene las demás: es
    una línea para revisar, como en la carga (RN-17). La auditoría queda en el
    primer pedido de cada referencia, que es por donde se dio de alta.
    """
    resultados: list[ResultadoAltaReferencia] = []
    for pendiente in elegidas:
        pedido = await sesion.get(PedidoTransito, pendiente.lineas[0].id_pedido)
        assert pedido is not None
        try:
            hecho = await registro_embarque.registrar(
                sesion,
                cliente,
                pedido,
                pendiente.tipo,
                pendiente.numero,
                id_usuario=id_usuario,
                catalogo=catalogo,
            )
        except ErrorShipsGo as exc:
            logger.warning("ShipsGo: falló el alta de %s — %s", pendiente.numero, exc)
            resultados.append(
                ResultadoAltaReferencia(pendiente.tipo, pendiente.numero, False, exc.motivo)
            )
            continue
        resultados.append(
            ResultadoAltaReferencia(
                pendiente.tipo,
                pendiente.numero,
                hecho.registrado,
                hecho.motivo,
                hecho.consumio_credito,
            )
        )
    return resultados


__all__ = [
    "TIPOS_SHIPSGO",
    "LineaPendiente",
    "Pendiente",
    "ResultadoAltaReferencia",
    "dar_de_alta",
    "pendientes",
]
