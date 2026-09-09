"""Carga de pedidos desde una fuente a la base — `TASK-03` / RF-01, RN-17.

Es la pieza que faltaba entre el puerto de ingesta y la base: `FuentePedidos`
sabe **leer** líneas y `historial`, `normalizacion`, `referencia` y `asociacion`
saben tratarlas, pero nadie las escribía. Sin esto la semilla existía solo en
código, que es lo mismo que no existir para una demostración.

Sirve para cualquier fuente, no solo para la semilla: `US-31` enchufará el
Z-tracking real en el mismo sitio, porque lo que se recibe es un
`FuentePedidos` y no una implementación concreta.

**Una línea mala no aborta la carga.** Es la regla de RN-17 y acá se aplica al
pie de la letra: lo que no se puede resolver se rechaza **con su motivo** y el
resto del lote entra. Un archivo real trae basura —la muestra del 03/09 tenía
países en la columna de la vía y erratas como `PEDIENTE`—, y un cargador que se
cae con la primera fila sucia es inútil contra el archivo de verdad.

Dos campos obligan a rechazar cuando no se resuelven, y conviene saber por qué
son ellos: `via_transporte` e `id_destino` son **`NOT NULL`** en
`pedidos_transito`. No es una decisión de este módulo, es el modelo diciendo que
un pedido sin vía ni destino no es un pedido en tránsito. Todo lo demás —país,
incoterm, temperatura, referencia— es anulable y la línea entra igual.

La carga es **idempotente**: la clave natural es `(oc_numero, posicion_oc)` y
una línea ya presente se omite en vez de duplicarse. Correr el cargador dos
veces seguidas es seguro, que es lo que uno quiere antes de una demostración.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services import normalizacion
from app.services.asociacion import asociar_referencia
from app.services.ingesta.base import FuentePedidos
from app.services.ingesta.dto import PedidoCrudo

logger = logging.getLogger(__name__)

#: Etapa inicial. `asociar_referencia` la mueve a `EN_ORIGEN` si la línea trae
#: una referencia válida; sin ella el pedido nace y se queda en `SIN_TRACKING`,
#: que es exactamente lo que describe RN-02.
ETAPA_INICIAL = "SIN_TRACKING"

#: Motivos de rechazo. Son los dos campos `NOT NULL` que no siempre se pueden
#: resolver desde un archivo sucio.
RECHAZO_SIN_VIA = "sin_via_transporte"
RECHAZO_SIN_DESTINO = "sin_destino_resoluble"


@dataclass(frozen=True, slots=True)
class LineaRechazada:
    """Una línea que no entró, y por qué. Se reporta, no se esconde."""

    oc_numero: str
    posicion_oc: int
    motivo: str
    detalle: str

    def __str__(self) -> str:
        return f"{self.oc_numero}-{self.posicion_oc}: {self.detalle}"


@dataclass(slots=True)
class ResultadoCarga:
    """Qué pasó con el lote. Pensado para imprimirse tal cual."""

    cargados: int = 0
    #: Ya estaban por su clave natural. No es un error: es la idempotencia.
    omitidos: int = 0
    rechazadas: list[LineaRechazada] = field(default_factory=list)
    #: De los cargados, cuántos quedaron con rastreo automático posible hoy.
    rastreables: int = 0
    #: Cargados con referencia válida pero que **ninguna API sigue todavía**.
    sin_rastreo_hoy: int = 0

    @property
    def leidas(self) -> int:
        return self.cargados + self.omitidos + len(self.rechazadas)

    @property
    def sin_tracking(self) -> int:
        """Cargados que ni siquiera traen referencia (RN-02)."""
        return self.cargados - self.rastreables - self.sin_rastreo_hoy


def generar_tracking_interno(oc_numero: str, posicion_oc: int) -> str:
    """Código interno que ve el usuario, derivado de la clave natural.

    Se deriva en vez de ser un correlativo para que sea **estable**: recargar
    la misma línea produce el mismo código, y así el identificador que alguien
    apuntó en un correo sigue sirviendo después de reconstruir la base.
    """
    return f"TRK-{oc_numero}-{posicion_oc:03d}"


async def _obtener_o_crear_proveedor(
    sesion: AsyncSession, codigo: str, nombre: str, pais: str | None
) -> Proveedor:
    """El proveedor del maestro, creándolo si la fuente lo trae por primera vez.

    El archivo es hoy la única fuente de maestros: no hay carga previa de
    proveedores ni de materiales, así que la ingesta los va descubriendo.
    """
    existente = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == codigo))
    if existente is not None:
        return existente

    proveedor = Proveedor(codigo=codigo, nombre=nombre[:120], pais=pais)
    sesion.add(proveedor)
    await sesion.flush()
    return proveedor


async def _obtener_o_crear_material(
    sesion: AsyncSession, codigo: str, descripcion: str, unidad: str
) -> Material:
    existente = await sesion.scalar(select(Material).where(Material.codigo == codigo))
    if existente is not None:
        return existente

    material = Material(codigo=codigo, descripcion=descripcion[:200], unidad_medida=unidad)
    sesion.add(material)
    await sesion.flush()
    return material


async def resolver_destino(
    sesion: AsyncSession, codigo: str | None, via: str | None
) -> tuple[MaestroDestino | None, str]:
    """Destino de la línea, por código o inferido de la vía.

    La inferencia no es un atajo: el DTO la contempla —*«`None` si la fuente no
    lo trae y hay que inferirlo de la vía de transporte»*— y solo se aplica
    cuando es **inequívoca**, es decir cuando esa vía tiene un único destino
    activo. Hoy solo `AEREO` lo cumple: hay un aeropuerto y tres puertos.

    Adivinar entre Caldera, Limón y Moín sería peor que rechazar la línea: son
    dos océanos distintos, y colocar un buque del Pacífico en el Caribe estropea
    la geocerca de arribo y el ETA sin que nada falle de forma visible.
    """
    if codigo:
        encontrado = await sesion.scalar(
            select(MaestroDestino).where(MaestroDestino.codigo == codigo)
        )
        if encontrado is not None:
            return encontrado, "codigo"
        return None, f"el destino {codigo!r} no está en el maestro"

    if via is None:
        return None, "la línea no trae destino y su vía tampoco se pudo resolver"

    candidatos = list(
        await sesion.scalars(
            select(MaestroDestino).where(
                MaestroDestino.via_transporte == via, MaestroDestino.activo.is_(True)
            )
        )
    )
    if len(candidatos) == 1:
        return candidatos[0], "inferido de la vía"
    if not candidatos:
        return None, f"sin destino y la vía {via} no tiene ninguno en el maestro"
    return (
        None,
        f"sin destino y la vía {via} tiene {len(candidatos)} posibles: no se adivina",
    )


async def cargar_pedido(
    sesion: AsyncSession, crudo: PedidoCrudo
) -> tuple[PedidoTransito | None, str, str]:
    """Persiste una línea. Devuelve el pedido, qué pasó y por qué.

    El segundo elemento es `"cargado"`, `"omitido"` o un motivo de rechazo; el
    tercero lo explica en castellano. Van juntos porque el motivo solo se
    conoce acá: reconstruirlo después obligaría a repetir el trabajo.
    """
    ya_esta = await sesion.scalar(
        select(PedidoTransito).where(
            PedidoTransito.oc_numero == crudo.oc_numero,
            PedidoTransito.posicion_oc == crudo.posicion_oc,
        )
    )
    if ya_esta is not None:
        return ya_esta, "omitido", "ya estaba cargada"

    # RN-17: se normaliza antes de decidir nada. `Terrestre` es TERRESTRE y
    # `PENDIENTE` no es una vía, es la ausencia de una.
    via = normalizacion.normalizar_via(crudo.via_transporte)
    if via is None:
        return (
            None,
            RECHAZO_SIN_VIA,
            f"la vía {crudo.via_transporte!r} no es una vía de transporte",
        )

    destino, detalle = await resolver_destino(sesion, crudo.destino_codigo, via)
    if destino is None:
        return None, RECHAZO_SIN_DESTINO, detalle

    # La vía del destino manda sobre la de la línea cuando difieren: el maestro
    # es dato verificado y la columna del archivo es texto libre.
    if destino.via_transporte != via:
        logger.info(
            "Pedido %s: la vía %s no coincide con la del destino %s (%s); manda el maestro.",
            crudo,
            via,
            destino.codigo,
            destino.via_transporte,
        )
        via = destino.via_transporte

    pais = await normalizacion.resolver_pais(sesion, crudo.pais_origen)
    proveedor = await _obtener_o_crear_proveedor(
        sesion, crudo.proveedor_codigo, crudo.proveedor_nombre, pais.codigo if pais else None
    )
    material = await _obtener_o_crear_material(
        sesion, crudo.material_codigo, crudo.material_descripcion, crudo.unidad_medida
    )

    pedido = PedidoTransito(
        oc_numero=crudo.oc_numero,
        posicion_oc=crudo.posicion_oc,
        tracking_interno=generar_tracking_interno(crudo.oc_numero, crudo.posicion_oc),
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        id_pais_origen=pais.id if pais else None,
        via_transporte=via,
        cantidad_pedida=Decimal(str(crudo.cantidad)),
        unidad_medida=crudo.unidad_medida,
        fecha_entrega_pedido=crudo.fecha_entrega_pedido,
        incoterm=normalizacion.normalizar_incoterm(crudo.incoterm),
        temperatura=normalizacion.normalizar_temperatura(crudo.temperatura),
        tipo_proveedor=normalizacion.normalizar_texto(crudo.tipo_proveedor),
        fabricante=crudo.fabricante,
        # Desnormalizado a propósito (§1 del modelo): guarda el valor **usado**,
        # para que editar el maestro no reescriba un desglose ya calculado.
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje=ETAPA_INICIAL,
        estado_calculado=ETAPA_INICIAL,
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido, "cargado", detalle


async def cargar(sesion: AsyncSession, fuente: FuentePedidos) -> ResultadoCarga:
    """Carga todo lo que entregue la fuente. **No hace commit**: es de quien llama.

    Dejar el commit afuera es lo que permite ensayar la carga entera dentro de
    una transacción que se revierte, que es como la ejercitan las pruebas.
    """
    resultado = ResultadoCarga()

    for crudo in await fuente.obtener_pedidos():
        pedido, estado, detalle = await cargar_pedido(sesion, crudo)

        if estado == "omitido":
            resultado.omitidos += 1
            continue

        if pedido is None:
            resultado.rechazadas.append(
                LineaRechazada(
                    oc_numero=crudo.oc_numero,
                    posicion_oc=crudo.posicion_oc,
                    motivo=estado,
                    detalle=detalle,
                )
            )
            logger.warning("Carga: línea %s rechazada — %s", crudo, detalle)
            continue

        resultado.cargados += 1

        if crudo.tipo_referencia and crudo.numero_referencia:
            veredicto = await asociar_referencia(
                sesion, pedido, crudo.tipo_referencia, crudo.numero_referencia
            )
            if veredicto.valida and veredicto.rastreable:
                resultado.rastreables += 1
            elif veredicto.valida:
                resultado.sin_rastreo_hoy += 1

    logger.info(
        "Carga desde %s: %d leídas, %d cargadas, %d omitidas, %d rechazadas.",
        fuente.nombre,
        resultado.leidas,
        resultado.cargados,
        resultado.omitidos,
        len(resultado.rechazadas),
    )
    return resultado


__all__ = [
    "ETAPA_INICIAL",
    "RECHAZO_SIN_DESTINO",
    "RECHAZO_SIN_VIA",
    "LineaRechazada",
    "ResultadoCarga",
    "cargar",
    "cargar_pedido",
    "generar_tracking_interno",
    "resolver_destino",
]
