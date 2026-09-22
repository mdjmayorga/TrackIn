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
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.pedido_transito import PedidoTransito
from app.services import estado as estado_mod
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


async def _eta_de_la_fuente(sesion: AsyncSession, pedido: PedidoTransito) -> dt.datetime | None:
    """La ETA del elemento rastreado, si el pedido tiene uno.

    Un pedido `SIN_TRACKING` no lo tiene —es la definición de RN-02—, que es
    exactamente el caso de las líneas que hoy entran desde el archivo.
    """
    if pedido.id_elemento_rastreado is None:
        return None
    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    return elemento.eta_api if elemento is not None else None


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

    resultado = proyeccion.calcular(
        ata_confirmada=pedido.ata_confirmada,
        ata_inferida=pedido.ata_inferida,
        eta_fuente=await _eta_de_la_fuente(sesion, pedido),
        eta_declarada=pedido.eta_declarada,
        lead_time_dias=lead_time,
        ajuste_manual_dias=pedido.ajuste_manual_dias,
    )

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

    def __post_init__(self) -> None:
        if self.por_estado is None:
            self.por_estado = {}
        if self.por_motivo_sin_fecha is None:
            self.por_motivo_sin_fecha = {}


async def recalcular_todos(
    sesion: AsyncSession, umbral_dias: int | None = None
) -> ResumenRecalculo:
    """Recalcula los pedidos vivos. **No hace commit**: es de quien llama.

    Barre solo los no cerrados: un terminal de RN-13 no cambia y recorrerlo
    sería gastar trabajo en confirmar que nada pasa.
    """
    if umbral_dias is None:
        umbral_dias = await parametros.obtener_entero(sesion, CLAVE_UMBRAL)

    resumen = ResumenRecalculo()
    assert resumen.por_estado is not None
    assert resumen.por_motivo_sin_fecha is not None

    pedidos = await sesion.scalars(
        select(PedidoTransito).where(PedidoTransito.motivo_cierre.is_(None))
    )
    for pedido in pedidos:
        resultado = await recalcular(sesion, pedido, umbral_dias=umbral_dias)
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

    await sesion.flush()
    logger.info(
        "Recálculo masivo: %d evaluados, %d con fecha, %d sin fecha, %d cambiaron.",
        resumen.evaluados,
        resumen.con_fecha,
        resumen.sin_fecha,
        resumen.cambiados,
    )
    return resumen


__all__ = [
    "CLAVE_UMBRAL",
    "ResultadoRecalculo",
    "ResumenRecalculo",
    "recalcular",
    "recalcular_todos",
]
