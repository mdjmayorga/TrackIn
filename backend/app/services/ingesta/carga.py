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
una línea ya presente se **actualiza** en vez de duplicarse. Correr el cargador
dos veces seguidas es seguro, que es lo que uno quiere antes de una
demostración.

Qué se actualiza y qué no — `US-31`
------------------------------------

El primer criterio de `US-31` pide que *«los pedidos nuevos se insertan y los
existentes se actualizan por OC y posición»*. Actualizar **todo** sería
incorrecto: la mitad de las columnas de `pedidos_transito` no vienen del
archivo, las calcula el sistema o las escribe una persona.

Se actualiza lo que el archivo manda, porque es su fuente de verdad: cantidad,
fecha comprometida, incoterm, temperatura, país, fabricante, vía y destino.

**No se toca** lo que el archivo no sabe:

- `etapa_viaje`, `estado_cumplimiento`, `estado_calculado` y
  `fecha_proyectada_disponible`, que son del motor de cálculo (`US-09`,
  `US-10`).
- `ata_confirmada`, `fecha_recepcion_planta`, `cantidad_recibida`,
  `motivo_cierre` y `ajuste_manual_dias`, que son intervenciones humanas
  auditadas por RF-14. Un archivo no puede deshacer lo que una persona
  confirmó.
- `id_elemento_rastreado`, que gestiona la asociación de referencias.
- `lead_time_destino_dias`, que es una **instantánea** del valor usado y se
  reescribe solo si el destino cambia.

Un pedido **cerrado** (`motivo_cierre` no nulo) se deja intacto y se cuenta
aparte: si volvió a aparecer en el archivo, eso es precisamente lo que hay que
revisar a mano, no algo que el cargador deba resolver solo.

Ausencias — el segundo criterio
--------------------------------

Lo que estaba en la base y **no** vino en el archivo se marca `ausente_desde` y
**no se borra**. Un pedido que desaparece casi nunca dejó de existir: es una
línea cerrada en SAP, un archivo exportado con otro filtro o una hoja recortada.
Borrarlo destruiría su historial de tracking, que es inmutable por RNF-13.

La marca es reversible: si la línea vuelve a aparecer, `ausente_desde` se limpia
y se anota en el log, porque una línea que va y viene es un síntoma del archivo,
no del pedido.
"""

from __future__ import annotations

import datetime as dt
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

#: La línea **sí** entró; lo que no sirve es su referencia de embarque. No es
#: un rechazo de la línea sino de su rastreo: el pedido queda `SIN_TRACKING`
#: (RN-02) hasta que alguien corrija el número (`US-32`).
RECHAZO_REFERENCIA_INVALIDA = "referencia_invalida"


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
    """Qué pasó con el lote. Pensado para imprimirse tal cual.

    El tercer criterio de `US-31` pide informar **recibidos, insertados,
    actualizados y rechazados**; los cuatro están acá con esos nombres o con su
    equivalente directo (`leidas` son los recibidos, `cargados` los insertados).
    """

    #: Insertados: no estaban por su clave natural.
    cargados: int = 0
    #: Ya estaban y el archivo traía datos distintos: se actualizaron.
    actualizados: int = 0
    #: Ya estaban y el archivo no cambiaba nada. No es un error: es la
    #: idempotencia, y distinguirlo de `actualizados` es lo que permite ver de
    #: un vistazo si una carga movió algo o no.
    sin_cambios: int = 0
    #: Volvieron a aparecer tras haber estado ausentes.
    reaparecidos: int = 0
    #: Cerrados (RN-13) que volvieron a venir en el archivo. Se dejan intactos
    #: y se cuentan aparte: eso se revisa a mano, no lo resuelve el cargador.
    cerrados_omitidos: int = 0
    #: Estaban en la base y no vinieron: marcados `ausente_desde`, nunca
    #: borrados (segundo criterio de `US-31`).
    ausentes: list[tuple[str, int]] = field(default_factory=list)
    rechazadas: list[LineaRechazada] = field(default_factory=list)
    #: Líneas que **sí** entraron pero cuya referencia no sirve. Van aparte de
    #: `rechazadas` porque el pedido está en la base: lo que falta es su rastreo.
    referencias_invalidas: list[LineaRechazada] = field(default_factory=list)
    #: De los cargados, cuántos quedaron con rastreo automático posible hoy.
    rastreables: int = 0
    #: Cargados con referencia válida pero que **ninguna API sigue todavía**.
    sin_rastreo_hoy: int = 0

    @property
    def leidas(self) -> int:
        """Recibidas del archivo, cualquiera que haya sido su destino."""
        return (
            self.cargados
            + self.actualizados
            + self.sin_cambios
            + self.cerrados_omitidos
            + len(self.rechazadas)
        )

    @property
    def omitidos(self) -> int:
        """Las que no movieron nada. Se conserva el nombre anterior a `US-31`."""
        return self.sin_cambios + self.cerrados_omitidos

    @property
    def sin_tracking(self) -> int:
        """Cargados que ni siquiera traen referencia (RN-02)."""
        return self.cargados - self.rastreables - self.sin_rastreo_hoy

    def resumen(self) -> str:
        """Una línea con los cuatro números que pide el tercer criterio."""
        return (
            f"{self.leidas} recibidas · {self.cargados} insertadas · "
            f"{self.actualizados} actualizadas · {len(self.rechazadas)} rechazadas · "
            f"{len(self.ausentes)} ausentes"
        )


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


@dataclass(frozen=True, slots=True)
class _Resuelto:
    """Lo que hay que resolver contra la base antes de insertar o actualizar."""

    via: str
    destino: MaestroDestino
    id_pais: int | None
    id_proveedor: int
    id_material: int
    detalle: str


async def _resolver(sesion: AsyncSession, crudo: PedidoCrudo) -> tuple[_Resuelto | None, str, str]:
    """Normaliza y resuelve los maestros. Devuelve el porqué si no se puede."""
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
    return (
        _Resuelto(
            via=via,
            destino=destino,
            id_pais=pais.id if pais else None,
            id_proveedor=proveedor.id,
            id_material=material.id,
            detalle=detalle,
        ),
        "",
        detalle,
    )


def _campos_del_archivo(crudo: PedidoCrudo, resuelto: _Resuelto) -> dict[str, object]:
    """Lo que el archivo es dueño de escribir, ya normalizado.

    Deliberadamente **no** incluye estado, etapa, fechas calculadas ni nada
    confirmado a mano: ver el encabezado del módulo.
    """
    return {
        "id_proveedor": resuelto.id_proveedor,
        "id_material": resuelto.id_material,
        "id_destino": resuelto.destino.id,
        "id_pais_origen": resuelto.id_pais,
        "via_transporte": resuelto.via,
        "cantidad_pedida": Decimal(str(crudo.cantidad)),
        "unidad_medida": crudo.unidad_medida,
        "fecha_entrega_pedido": crudo.fecha_entrega_pedido,
        "incoterm": normalizacion.normalizar_incoterm(crudo.incoterm),
        "temperatura": normalizacion.normalizar_temperatura(crudo.temperatura),
        "tipo_proveedor": normalizacion.normalizar_texto(crudo.tipo_proveedor),
        "fabricante": crudo.fabricante,
    }


async def cargar_pedido(
    sesion: AsyncSession, crudo: PedidoCrudo, instante: dt.datetime | None = None
) -> tuple[PedidoTransito | None, str, str]:
    """Persiste una línea. Devuelve el pedido, qué pasó y por qué.

    El segundo elemento es `"cargado"`, `"actualizado"`, `"sin_cambios"`,
    `"cerrado_omitido"` o un motivo de rechazo; el tercero lo explica en
    castellano. Van juntos porque el motivo solo se conoce acá: reconstruirlo
    después obligaría a repetir el trabajo.
    """
    ahora = instante or dt.datetime.now(dt.UTC)

    ya_esta = await sesion.scalar(
        select(PedidoTransito).where(
            PedidoTransito.oc_numero == crudo.oc_numero,
            PedidoTransito.posicion_oc == crudo.posicion_oc,
        )
    )

    if ya_esta is not None and ya_esta.motivo_cierre is not None:
        # RN-13: está cerrado. Que reaparezca en el archivo es justo lo que hay
        # que mirar a mano; el cargador no reabre nada por su cuenta.
        return (
            ya_esta,
            "cerrado_omitido",
            f"el pedido está cerrado ({ya_esta.motivo_cierre}) y volvió a venir en el archivo",
        )

    resuelto, motivo, detalle = await _resolver(sesion, crudo)
    if resuelto is None:
        return None, motivo, detalle

    if ya_esta is not None:
        actualizado = _actualizar(ya_esta, crudo, resuelto, ahora)
        # Se vacía igual que en el alta: sin esto el `UPDATE` queda pendiente y
        # quien llame vería el valor viejo hasta el siguiente *autoflush*.
        await sesion.flush()
        return actualizado

    pedido = PedidoTransito(
        oc_numero=crudo.oc_numero,
        posicion_oc=crudo.posicion_oc,
        tracking_interno=generar_tracking_interno(crudo.oc_numero, crudo.posicion_oc),
        # Desnormalizado a propósito (§1 del modelo): guarda el valor **usado**,
        # para que editar el maestro no reescriba un desglose ya calculado.
        lead_time_destino_dias=resuelto.destino.lead_time_dias,
        etapa_viaje=ETAPA_INICIAL,
        estado_calculado=ETAPA_INICIAL,
        fecha_ultima_carga=ahora,
        **_campos_del_archivo(crudo, resuelto),
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido, "cargado", detalle


def _actualizar(
    pedido: PedidoTransito, crudo: PedidoCrudo, resuelto: _Resuelto, ahora: dt.datetime
) -> tuple[PedidoTransito, str, str]:
    """Aplica lo que el archivo cambió, y solo eso."""
    cambios: list[str] = []
    for campo, nuevo in _campos_del_archivo(crudo, resuelto).items():
        if getattr(pedido, campo) != nuevo:
            cambios.append(campo)
            setattr(pedido, campo, nuevo)

    # La instantánea del lead time se reescribe solo si cambió el destino: es
    # el valor **usado** en el cálculo, no un espejo del maestro.
    if "id_destino" in cambios:
        pedido.lead_time_destino_dias = resuelto.destino.lead_time_dias

    reaparecio = pedido.ausente_desde is not None
    if reaparecio:
        logger.info(
            "Pedido %s: vuelve a figurar en el archivo tras estar ausente desde %s.",
            crudo,
            pedido.ausente_desde,
        )
        pedido.ausente_desde = None

    pedido.fecha_ultima_carga = ahora

    if reaparecio:
        return pedido, "reaparecido", "volvió a figurar en el archivo"
    if not cambios:
        return pedido, "sin_cambios", "ya estaba cargada y el archivo no la cambia"
    return pedido, "actualizado", f"cambió {', '.join(cambios)}"


async def marcar_ausentes(
    sesion: AsyncSession, presentes: set[tuple[str, int]], instante: dt.datetime | None = None
) -> list[tuple[str, int]]:
    """Señala lo que estaba en la base y no vino en el archivo. **No borra.**

    Segundo criterio de `US-31`. Solo mira pedidos que **alguna carga trajo**
    (`fecha_ultima_carga IS NOT NULL`) y que siguen vivos (`motivo_cierre IS
    NULL`): un pedido cerrado ya no se espera en el archivo, y uno que nunca
    vino de una carga no es de la incumbencia de esta fuente.

    Asume que el archivo es el **universo completo** de pedidos vivos, que es
    cierto mientras se cargue desde una sola fuente — y `INGESTA_ADAPTADOR`
    obliga a elegir exactamente una.

    Devuelve las claves recién marcadas; las que ya estaban marcadas no se
    tocan, para no reescribir la fecha desde la que faltan.
    """
    ahora = instante or dt.datetime.now(dt.UTC)

    candidatos = await sesion.scalars(
        select(PedidoTransito).where(
            PedidoTransito.motivo_cierre.is_(None),
            PedidoTransito.fecha_ultima_carga.is_not(None),
            PedidoTransito.ausente_desde.is_(None),
        )
    )

    marcados: list[tuple[str, int]] = []
    for pedido in candidatos:
        clave = (pedido.oc_numero, pedido.posicion_oc)
        if clave in presentes:
            continue
        pedido.ausente_desde = ahora
        marcados.append(clave)

    if marcados:
        await sesion.flush()
        logger.warning(
            "Carga: %d pedidos dejaron de figurar en el archivo y quedan para revisión manual.",
            len(marcados),
        )
    return marcados


async def cargar(
    sesion: AsyncSession, fuente: FuentePedidos, señalar_ausentes: bool = True
) -> ResultadoCarga:
    """Carga todo lo que entregue la fuente. **No hace commit**: es de quien llama.

    Dejar el commit afuera es lo que permite ensayar la carga entera dentro de
    una transacción que se revierte, que es como la ejercitan las pruebas.

    `señalar_ausentes` permite desactivar el segundo criterio de `US-31` cuando
    la fuente **no** es el universo completo —una carga parcial o de prueba—,
    porque marcar media base como ausente sería peor que no marcar nada.

    Todas las líneas del lote comparten el mismo instante: una carga es un acto,
    y que dos líneas del mismo archivo difieran en milisegundos solo complica
    leer después qué entró junto.
    """
    ahora = dt.datetime.now(dt.UTC)
    resultado = ResultadoCarga()
    presentes: set[tuple[str, int]] = set()

    for crudo in await fuente.obtener_pedidos():
        pedido, estado, detalle = await cargar_pedido(sesion, crudo, instante=ahora)

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

        # Una línea cerrada sí estaba en el archivo: cuenta como presente, o la
        # marcaríamos ausente en la misma corrida que la vio.
        presentes.add(crudo.clave)

        if estado == "cerrado_omitido":
            resultado.cerrados_omitidos += 1
            logger.warning("Carga: línea %s — %s", crudo, detalle)
            continue
        if estado == "sin_cambios":
            resultado.sin_cambios += 1
            continue
        if estado == "actualizado":
            resultado.actualizados += 1
            continue
        if estado == "reaparecido":
            resultado.reaparecidos += 1
            resultado.actualizados += 1
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
            else:
                # Hasta `US-32` este caso no se contaba en ninguna parte: el
                # pedido entraba y la referencia mala desaparecía del informe.
                # Con el dígito verificador en marcha el silencio importa, y es
                # justo lo que pide el sexto criterio.
                resultado.referencias_invalidas.append(
                    LineaRechazada(
                        oc_numero=crudo.oc_numero,
                        posicion_oc=crudo.posicion_oc,
                        motivo=RECHAZO_REFERENCIA_INVALIDA,
                        detalle=veredicto.motivo,
                    )
                )
                logger.warning("Carga: referencia de %s inválida — %s", crudo, veredicto.motivo)

    if señalar_ausentes:
        resultado.ausentes = await marcar_ausentes(sesion, presentes, instante=ahora)

    logger.info("Carga desde %s: %s", fuente.nombre, resultado.resumen())
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
    "marcar_ausentes",
    "resolver_destino",
]
