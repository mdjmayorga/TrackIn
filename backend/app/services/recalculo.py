"""Recálculo de fecha proyectada y estado de un pedido — `US-09` + `US-10`.

La pieza que junta las dos reglas puras con la base: lee los insumos, llama a
`proyeccion.calcular` y a `estado`, y escribe el resultado **con su desglose**.

Por qué el cálculo no vive aquí
--------------------------------

`proyeccion` y `estado` no importan SQLAlchemy y no saben que existe una base.
Este módulo es el único que sí. La separación no es ceremonia: RN-01 y RN-07 a
RN-09 son el corazón funcional del sistema, y poder ejercitarlas con una tabla
de casos en vez de levantando PostgreSQL es lo que permite cubrir de verdad los
bordes —margen exacto en el umbral, ATA que gana a ETA, destino sin lead time—.

Qué escribe y qué no toca
--------------------------

Escribe las cinco columnas del cálculo: `eta_utilizada`,
`lead_time_destino_dias`, `fecha_proyectada_disponible`, `estado_cumplimiento`,
`estado_calculado` y la marca `fecha_ultimo_recalculo`.

**No toca `etapa_viaje`.** Es la otra dimensión del estado (§1.4) y la produce
el rastreo, no el cálculo: RN-02 a RN-06. Confundirlas sería colapsar otra vez
las dos preguntas que el modelo separó a propósito.

**Tampoco reabre un pedido cerrado.** Si `motivo_cierre` no es nulo el estado es
terminal por RN-13, y recalcularlo solo puede romper el `CHECK` que ata las dos
cosas.

La instantánea del lead time
-----------------------------

`lead_time_destino_dias` se refresca **en el recálculo** desde el maestro. Es lo
que exige RF-05: la columna guarda el valor *usado* en este cálculo, de modo que
el desglose siga cuadrando aunque alguien edite el maestro mañana. `US-12` es
quien decidirá cuándo disparar el recálculo; aquí solo se hace bien cuando toca.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.pedido_transito import PedidoTransito
from app.services import estado as estado_mod
from app.services import eta_estimada as eta_mod
from app.services import parametros, proyeccion

logger = logging.getLogger(__name__)

#: Parámetro que decide la ventana de `EN_RIESGO` (RN-07/RN-08).
CLAVE_UMBRAL = "umbral_riesgo_dias"


@dataclass(frozen=True, slots=True)
class ResultadoRecalculo:
    """Qué quedó, y con qué desglose. Es lo que `US-16` expondrá por la API."""

    fecha_proyectada: dt.date | None
    estado_cumplimiento: str | None
    estado_calculado: str
    proyeccion: proyeccion.Proyeccion
    #: `True` si alguna de las columnas calculadas cambió de valor.
    cambio: bool

    @property
    def desglose(self) -> str:
        return self.proyeccion.desglose


async def _fechas_de_la_fuente(
    sesion: AsyncSession, pedido: PedidoTransito
) -> tuple[dt.datetime | None, dt.datetime | None]:
    """La ETA y la ATA del elemento rastreado, si el pedido tiene uno.

    Un pedido `SIN_TRACKING` no lo tiene —es la definición de RN-02—, que es
    exactamente el caso de las líneas que hoy entran desde el archivo.
    """
    if pedido.id_elemento_rastreado is None:
        return None, None
    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    if elemento is None:
        return None, None
    return elemento.eta_api, elemento.ata_api


async def proyectar(
    sesion: AsyncSession, pedido: PedidoTransito, *, lead_time_dias: int | None
) -> proyeccion.Proyeccion:
    """RN-01 con los insumos actuales del pedido. **No persiste nada.**

    El lead time lo decide quien llama: `recalcular` pasa el vigente del
    maestro, y el detalle de `US-16` pasa la instantánea guardada, para saber si
    lo que muestra la grilla sigue cuadrando con sus insumos.
    """
    # `US-08` solo produce algo con AIS —ShipsGo no entrega velocidad— y solo
    # se consulta si hace falta: si la fuente ya dio su ETA, la estimada no
    # cambiaría el resultado y calcularla sería una consulta PostGIS de balde.
    eta_fuente, ata_fuente = await _fechas_de_la_fuente(sesion, pedido)
    estimada = None
    arribos = (pedido.ata_confirmada, ata_fuente, pedido.ata_inferida)
    if eta_fuente is None and all(fecha is None for fecha in arribos):
        estimada = (await eta_mod.estimar(sesion, pedido)).eta

    return proyeccion.calcular(
        ata_confirmada=pedido.ata_confirmada,
        ata_fuente=ata_fuente,
        ata_inferida=pedido.ata_inferida,
        eta_fuente=eta_fuente,
        eta_estimada=estimada,
        eta_declarada=pedido.eta_declarada,
        lead_time_dias=lead_time_dias,
        ajuste_manual_dias=pedido.ajuste_manual_dias,
    )


async def recalcular(
    sesion: AsyncSession,
    pedido: PedidoTransito,
    umbral_dias: int | None = None,
    instante: dt.datetime | None = None,
) -> ResultadoRecalculo:
    """Aplica RN-01 y el semáforo a un pedido, y persiste el resultado.

    `umbral_dias` se puede pasar para recalcular un lote entero sin releer el
    parámetro en cada línea; si no viene, se lee de `parametros_sistema`.
    """
    ahora = instante or dt.datetime.now(dt.UTC)

    if pedido.motivo_cierre is not None:
        # RN-13: terminal. Ni se proyecta ni se reevalúa el cumplimiento.
        sin_calculo = proyeccion.Proyeccion(
            fecha=pedido.fecha_proyectada_disponible,
            origen=None,
            base=None,
            lead_time_dias=pedido.lead_time_destino_dias,
            ajuste_manual_dias=pedido.ajuste_manual_dias,
            motivo=f"el pedido está cerrado ({pedido.motivo_cierre}); RN-13 no se recalcula",
        )
        return ResultadoRecalculo(
            fecha_proyectada=pedido.fecha_proyectada_disponible,
            estado_cumplimiento=pedido.estado_cumplimiento,
            estado_calculado=pedido.estado_calculado,
            proyeccion=sin_calculo,
            cambio=False,
        )

    if umbral_dias is None:
        umbral_dias = await parametros.obtener_entero(sesion, CLAVE_UMBRAL)

    destino = await sesion.get(MaestroDestino, pedido.id_destino)
    lead_time = destino.lead_time_dias if destino is not None else None

    resultado = await proyectar(sesion, pedido, lead_time_dias=lead_time)

    cumplimiento = estado_mod.clasificar_cumplimiento(
        resultado.fecha, pedido.fecha_entrega_pedido, umbral_dias
    )
    calculado = estado_mod.derivar_estado_calculado(
        pedido.etapa_viaje, cumplimiento, pedido.motivo_cierre
    )

    antes = (
        pedido.fecha_proyectada_disponible,
        pedido.estado_cumplimiento,
        pedido.estado_calculado,
    )
    cambio = antes != (resultado.fecha, cumplimiento, calculado)

    pedido.fecha_proyectada_disponible = resultado.fecha
    pedido.estado_cumplimiento = cumplimiento
    pedido.estado_calculado = calculado
    pedido.fecha_ultimo_recalculo = ahora
    if lead_time is not None:
        # La instantánea del valor **usado**, para que el desglose de RF-05
        # siga cuadrando aunque el maestro cambie después.
        pedido.lead_time_destino_dias = lead_time
    # `eta_utilizada` es `TIMESTAMPTZ` y la base es `DATE`: se guarda al
    # comienzo del día UTC, que es toda la precisión que el dato tiene.
    pedido.eta_utilizada = (
        dt.datetime.combine(resultado.base, dt.time.min, tzinfo=dt.UTC)
        if resultado.base is not None
        else None
    )

    if cambio:
        logger.info("Recálculo de %s: %s → %s", pedido.tracking_interno, antes, calculado)

    return ResultadoRecalculo(
        fecha_proyectada=resultado.fecha,
        estado_cumplimiento=cumplimiento,
        estado_calculado=calculado,
        proyeccion=resultado,
        cambio=cambio,
    )


@dataclass(slots=True)
class ResumenRecalculo:
    """Qué movió un recálculo masivo. Pensado para imprimirse tal cual."""

    evaluados: int = 0
    con_fecha: int = 0
    sin_fecha: int = 0
    cambiados: int = 0
    cerrados_omitidos: int = 0
    por_estado: dict[str, int] | None = None
    por_motivo_sin_fecha: dict[str, int] | None = None
    #: `tracking_interno` de los que fallaron. Quedan como estaban (RNF-14).
    fallidos: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.por_estado is None:
            self.por_estado = {}
        if self.por_motivo_sin_fecha is None:
            self.por_motivo_sin_fecha = {}

    def texto(self) -> str:
        texto = (
            f"{self.evaluados} evaluados, {self.con_fecha} con fecha, "
            f"{self.sin_fecha} sin fecha, {self.cambiados} cambiaron"
        )
        if self.fallidos:
            texto += f", {len(self.fallidos)} fallaron"
        return texto


async def recalcular_lote(
    sesion: AsyncSession,
    pedidos: Iterable[PedidoTransito],
    umbral_dias: int | None = None,
    instante: dt.datetime | None = None,
) -> ResumenRecalculo:
    """Recalcula cada pedido en su propio *savepoint*. **No hace commit.**

    Es el tercer criterio de `US-12` y RNF-14: si un pedido falla —un dato que
    rompe un `CHECK`, un destino borrado—, se deshace **solo ese** y el resto
    sigue. Sin el *savepoint*, el error dejaría la transacción entera abortada
    y perdería también lo que ya se había recalculado bien.

    Se vacía la sesión dentro de cada *savepoint* porque es en el `flush` donde
    la base rechaza la fila; fuera de él, el error saltaría en el pedido
    equivocado.
    """
    if umbral_dias is None:
        umbral_dias = await parametros.obtener_entero(sesion, CLAVE_UMBRAL)

    resumen = ResumenRecalculo()
    assert resumen.por_estado is not None
    assert resumen.por_motivo_sin_fecha is not None

    for pedido in pedidos:
        if pedido.motivo_cierre is not None:
            resumen.cerrados_omitidos += 1
            continue
        # Se toma antes: si el savepoint se revierte, el objeto queda expirado.
        nombre = pedido.tracking_interno
        try:
            async with sesion.begin_nested():
                resultado = await recalcular(
                    sesion, pedido, umbral_dias=umbral_dias, instante=instante
                )
                await sesion.flush()
        except Exception:
            logger.exception("Recálculo de %s falló; se sigue con los demás.", nombre)
            resumen.fallidos.append(nombre)
            continue

        resumen.evaluados += 1
        if resultado.fecha_proyectada is None:
            resumen.sin_fecha += 1
            motivo = resultado.proyeccion.motivo
            resumen.por_motivo_sin_fecha[motivo] = resumen.por_motivo_sin_fecha.get(motivo, 0) + 1
        else:
            resumen.con_fecha += 1
        if resultado.cambio:
            resumen.cambiados += 1
        clave = resultado.estado_calculado
        resumen.por_estado[clave] = resumen.por_estado.get(clave, 0) + 1

    logger.info("Recálculo: %s.", resumen.texto())
    return resumen


async def recalcular_todos(
    sesion: AsyncSession,
    umbral_dias: int | None = None,
    *,
    id_destino: int | None = None,
    ids: Collection[int] | None = None,
    instante: dt.datetime | None = None,
) -> ResumenRecalculo:
    """Recalcula los pedidos vivos, o los de un destino, o los de una lista.

    Barre solo los no cerrados: un terminal de RN-13 no cambia y recorrerlo
    sería gastar trabajo en confirmar que nada pasa. **No hace commit.**
    """
    consulta = select(PedidoTransito).where(PedidoTransito.motivo_cierre.is_(None))
    if id_destino is not None:
        consulta = consulta.where(PedidoTransito.id_destino == id_destino)
    if ids is not None:
        if not ids:
            return ResumenRecalculo()
        consulta = consulta.where(PedidoTransito.id.in_(ids))
    # Se materializa antes de recorrer: los savepoints emiten sentencias
    # propias y no pueden intercalarse con un cursor todavía abierto.
    pedidos = list(await sesion.scalars(consulta.order_by(PedidoTransito.id)))
    return await recalcular_lote(sesion, pedidos, umbral_dias=umbral_dias, instante=instante)


#: Los parámetros que entran en el cálculo. Si uno cambia, cambian fechas o
#: semáforos de pedidos que ninguna lectura nueva va a tocar (`US-17`).
PARAMETROS_DEL_CALCULO: tuple[str, ...] = (CLAVE_UMBRAL, eta_mod.CLAVE_VELOCIDAD_MINIMA)

FirmaCalculo = tuple[tuple[tuple[str, str], ...], tuple[tuple[int, int], ...]]


async def firma_del_calculo(sesion: AsyncSession) -> FirmaCalculo:
    """Los insumos globales de RN-01 y del semáforo, en una tupla comparable.

    Son los que no pertenecen a ningún pedido: los parámetros del cálculo y el
    lead time de cada destino. Si la firma cambia entre dos ciclos del worker,
    alguien los editó —por la aplicación, por una migración o con un `UPDATE`
    a mano— y hay que recalcular todo, porque el cambio no llega por ninguna
    lectura. Compararla cuesta dos consultas pequeñas.
    """
    valores = tuple(
        [(clave, str(await parametros.obtener(sesion, clave))) for clave in PARAMETROS_DEL_CALCULO]
    )
    lead_times = tuple(
        (id_destino, dias)
        for id_destino, dias in await sesion.execute(
            select(MaestroDestino.id, MaestroDestino.lead_time_dias).order_by(MaestroDestino.id)
        )
    )
    return valores, lead_times


async def recalcular_destino(sesion: AsyncSession, id_destino: int) -> ResumenRecalculo:
    """Segundo criterio de `US-12`: el lead time de un destino cambió.

    Toma el valor **vigente** del maestro, que es lo que hace `recalcular`, y
    con eso refresca la instantánea `lead_time_destino_dias` de cada pedido.
    """
    return await recalcular_todos(sesion, id_destino=id_destino)


__all__ = [
    "CLAVE_UMBRAL",
    "PARAMETROS_DEL_CALCULO",
    "FirmaCalculo",
    "ResultadoRecalculo",
    "ResumenRecalculo",
    "firma_del_calculo",
    "proyectar",
    "recalcular",
    "recalcular_destino",
    "recalcular_lote",
    "recalcular_todos",
]
