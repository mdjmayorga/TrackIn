"""Determinación del arribo a destino — `US-11` / RN-05.

Reespecificada el 22/09/2026 al cerrar `TASK-28`
-------------------------------------------------

La historia original decía *«asumir el arribo cuando el buque entra en el radio
del puerto»*, y descansaba entera sobre dos supuestos que el spike midió falsos:

| Supuesto | Qué se midió |
|---|---|
| El AIS gratuito ve las naves en puerto | **No hay cobertura en ningún destino de Gutis** — ni Caribe ni Pacífico |
| La fuente entrega la velocidad, para descartar al que pasa de largo | **ShipsGo no la entrega**, y sin AIS no hay de dónde sacarla |

Así que la geocerca deja de ser el mecanismo y pasa a ser la verificación. **El
arribo lo dicen los hitos**, que son explícitos: `DISC`/`ARRV` en marítimo,
`RCF`/`DLV` en aéreo, y solo cuentan **en el puerto de destino** — los tres
embarques medidos traen arribos ocurridos en puertos de transbordo.

Los tres orígenes que RN-05 exige distinguir
---------------------------------------------

| Origen | Dónde se guarda | Quién lo pone |
|---|---|---|
| Confirmado a mano | `pedidos_transito.ata_confirmada` | Una persona (`US-14`) |
| Reportado por la fuente | `elementos_rastreados.ata_api` | El hito de ShipsGo |
| **Inferido** por geocerca | `pedidos_transito.ata_inferida` | Este módulo |

Solo el tercero se marca como inferido, y es deliberado: un hito `DISC` de la
naviera no es una deducción nuestra, es un dato. Confundirlos haría que el
usuario desconfiara de lo que no debe.

Por qué la geocerca no vale en aéreo
-------------------------------------

Cincuenta kilómetros alrededor de un aeropuerto capturan tráfico en sobrevuelo
—decisión del 25/08—. Un avión que pasa por encima de San José rumbo a Panamá
entraría en el radio sin haber aterrizado. En la vía aérea manda el hito, y si
algún día OpenSky es la única fuente, su indicador `on_ground`.

Qué hace al cerrar un arribo
-----------------------------

Marca el elemento `activo = false` cuando **todos** sus pedidos arribaron
(decisión B7 del 01/09): la nave zarpa hacia otro puerto y su posición deja de
representar la carga. Seguir consultándola es pagar por un dato que ya no
significa nada.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.pedido_transito import PedidoTransito
from app.services import parametros

logger = logging.getLogger(__name__)

ETAPA_EN_DESTINO = "EN_DESTINO"

#: Parámetro global del radio. `maestro_destinos.radio_geocerca_km` lo pisa.
CLAVE_RADIO = "radio_geocerca_km"

#: De dónde salió el arribo (RN-05).
ORIGEN_CONFIRMADO = "CONFIRMADO"
ORIGEN_FUENTE = "FUENTE"
ORIGEN_GEOCERCA = "GEOCERCA"

#: Motivos por los que no se dio por arribado.
SIN_ARRIBO = "sin_senal_de_arribo"
SIN_ELEMENTO = "sin_elemento_rastreado"
YA_ARRIBADO = "ya_estaba_en_destino"


@dataclass(frozen=True, slots=True)
class ResultadoArribo:
    """Si el pedido arribó, por qué vía se supo y a qué distancia estaba."""

    arribado: bool
    origen: str | None
    motivo: str
    instante: dt.datetime | None = None
    #: Metros al destino, cuando había posición con que medirlo.
    distancia_m: float | None = None
    #: `True` solo si lo dedujo la geocerca. Un hito no es una deducción.
    inferido: bool = False


async def _radio_metros(sesion: AsyncSession, destino: MaestroDestino) -> float:
    """El radio del destino si lo define, y si no el global.

    Moín y Limón están a 5,5 km y tienen radio propio de 2 km: con los 50 km
    globales sus geocercas se solaparían y un buque en uno contaría como
    arribado al otro.
    """
    if destino.radio_geocerca_km is not None:
        return float(destino.radio_geocerca_km) * 1000.0
    global_km = await parametros.obtener_entero(sesion, CLAVE_RADIO)
    return float(global_km) * 1000.0


async def _distancia_al_destino(
    sesion: AsyncSession, elemento: ElementoRastreado, destino: MaestroDestino
) -> float | None:
    """Metros entre la última posición conocida y el destino, vía PostGIS.

    Se calcula en la base y no en Python: `ST_Distance` sobre `geography`
    devuelve metros sobre el elipsoide, y reimplementar Haversine a mano sería
    menos exacto y más fácil de equivocar.
    """
    if elemento.posicion_actual is None:
        return None

    # **Se vacía la sesión antes de medir.** La distancia se calcula en la base
    # y la posición puede venir recién asignada en memoria —`colector_shipsgo`
    # la escribe después de su propio *flush*—, así que sin esto la subconsulta
    # leería el valor viejo. Y el fallo sería **mudo**: `ST_Distance(NULL, …)`
    # devuelve `NULL`, que aquí se lee como «no hay posición», que es un caso
    # legítimo. La geocerca simplemente no dispararía nunca.
    await sesion.flush()

    # Dos subconsultas escalares y no un `WHERE` sobre las dos tablas: esto
    # último es un producto cartesiano —SQLAlchemy lo avisa— que hoy funciona
    # porque cada filtro fija una fila, y el día que falte uno multiplicaría
    # las tablas en silencio. Así cada punto se resuelve por su clave.
    punto_elemento = (
        select(ElementoRastreado.posicion_actual)
        .where(ElementoRastreado.id == elemento.id)
        .scalar_subquery()
    )
    punto_destino = (
        select(MaestroDestino.ubicacion).where(MaestroDestino.id == destino.id).scalar_subquery()
    )
    distancia: Any = await sesion.scalar(select(func.ST_Distance(punto_elemento, punto_destino)))
    return float(distancia) if distancia is not None else None


async def evaluar(
    sesion: AsyncSession,
    pedido: PedidoTransito,
    instante: dt.datetime | None = None,
) -> ResultadoArribo:
    """Decide si el pedido llegó a destino y lo registra. **No hace commit.**

    El orden de las señales es el de RN-05: lo confirmado manda sobre lo
    reportado, y lo reportado sobre lo deducido.
    """
    ahora = instante or dt.datetime.now(dt.UTC)

    if pedido.ata_confirmada is not None:
        # Ya lo confirmó una persona (`US-14`). No hay nada que deducir.
        return ResultadoArribo(True, ORIGEN_CONFIRMADO, YA_ARRIBADO, pedido.ata_confirmada)

    if pedido.id_elemento_rastreado is None:
        return ResultadoArribo(False, None, SIN_ELEMENTO)

    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    destino = await sesion.get(MaestroDestino, pedido.id_destino)
    if elemento is None or destino is None:
        return ResultadoArribo(False, None, SIN_ELEMENTO)

    # --- Señal primaria: el hito de la fuente ------------------------------
    # `colector_shipsgo` ya dejó `ata_api` poblada solo si hubo `DISC`/`ARRV`
    # —o `RCF`/`DLV` en aéreo— **en el puerto de destino**. Los arribos a
    # puertos de transbordo no llegan hasta acá.
    if elemento.ata_api is not None:
        await _marcar_en_destino(sesion, pedido, elemento)
        logger.info("Pedido %s: arribo confirmado por la fuente (%s).", pedido, elemento.ata_api)
        return ResultadoArribo(True, ORIGEN_FUENTE, "hito_de_arribo", elemento.ata_api)

    # --- Señal secundaria: la geocerca -------------------------------------
    if destino.via_transporte == "AEREO":
        # 50 km alrededor de un aeropuerto capturan tráfico en sobrevuelo: un
        # avión de paso hacia Panamá entraría sin haber aterrizado.
        return ResultadoArribo(False, None, SIN_ARRIBO)

    distancia = await _distancia_al_destino(sesion, elemento, destino)
    if distancia is None:
        # Sin posición no hay geocerca que evaluar. Es lo normal: ShipsGo no
        # garantiza la posición y el AIS no cubre ningún puerto de Gutis.
        return ResultadoArribo(False, None, SIN_ARRIBO)

    radio = await _radio_metros(sesion, destino)
    if distancia > radio:
        return ResultadoArribo(False, None, SIN_ARRIBO, distancia_m=distancia)

    # Arribo **inferido**: es una deducción nuestra y se marca como tal.
    pedido.ata_inferida = ahora
    await _marcar_en_destino(sesion, pedido, elemento)
    logger.info(
        "Pedido %s: arribo inferido por geocerca — %.0f m de %s (radio %.0f m).",
        pedido,
        distancia,
        destino.codigo,
        radio,
    )
    return ResultadoArribo(
        True, ORIGEN_GEOCERCA, "dentro_de_la_geocerca", ahora, distancia, inferido=True
    )


async def _marcar_en_destino(
    sesion: AsyncSession, pedido: PedidoTransito, elemento: ElementoRastreado
) -> None:
    """Mueve la etapa y, si procede, apaga el elemento.

    **No toca `estado_calculado`**: eso lo deriva `US-10` a partir de las dos
    dimensiones, y escribirlo aquí lo dejaría incoherente con el cumplimiento.
    """
    if pedido.etapa_viaje != ETAPA_EN_DESTINO:
        pedido.etapa_viaje = ETAPA_EN_DESTINO
    await sesion.flush()
    await _apagar_si_todos_arribaron(sesion, elemento)


async def _apagar_si_todos_arribaron(sesion: AsyncSession, elemento: ElementoRastreado) -> bool:
    """Decisión B7 del 01/09: la nave que ya no lleva carga nuestra se apaga.

    Zarpa hacia otro puerto y su posición deja de representar el envío; seguir
    consultándola es pagar por un dato que ya no significa nada.

    Se exige que **todos** sus pedidos hayan llegado: un contenedor puede
    amparar varias líneas, y apagar el elemento con una sola arribada dejaría
    ciegas a las demás.
    """
    if not elemento.activo:
        return False

    pendientes = await sesion.scalar(
        select(func.count())
        .select_from(PedidoTransito)
        .where(
            PedidoTransito.id_elemento_rastreado == elemento.id,
            PedidoTransito.etapa_viaje != ETAPA_EN_DESTINO,
            PedidoTransito.motivo_cierre.is_(None),
        )
    )
    if pendientes:
        return False

    elemento.activo = False
    logger.info(
        "Elemento %s desactivado: todos sus pedidos arribaron (decisión B7).",
        elemento.tracking_externo,
    )
    return True


@dataclass(slots=True)
class ResumenArribos:
    """Qué movió un barrido de arribos."""

    evaluados: int = 0
    arribados: int = 0
    por_fuente: int = 0
    por_geocerca: int = 0
    elementos_apagados: int = 0


async def evaluar_todos(
    sesion: AsyncSession, instante: dt.datetime | None = None
) -> ResumenArribos:
    """Barre los pedidos vivos con rastreo. **No hace commit.**

    Salta los que ya están en destino o cerrados: no hay arribo que detectar
    en algo que ya llegó.
    """
    resumen = ResumenArribos()
    activos_antes = await _elementos_activos(sesion)

    pedidos = await sesion.scalars(
        select(PedidoTransito).where(
            PedidoTransito.motivo_cierre.is_(None),
            PedidoTransito.id_elemento_rastreado.is_not(None),
            PedidoTransito.etapa_viaje != ETAPA_EN_DESTINO,
        )
    )
    for pedido in pedidos:
        resultado = await evaluar(sesion, pedido, instante=instante)
        resumen.evaluados += 1
        if not resultado.arribado:
            continue
        resumen.arribados += 1
        if resultado.origen == ORIGEN_FUENTE:
            resumen.por_fuente += 1
        elif resultado.origen == ORIGEN_GEOCERCA:
            resumen.por_geocerca += 1

    await sesion.flush()
    resumen.elementos_apagados = activos_antes - await _elementos_activos(sesion)
    logger.info(
        "Arribos: %d evaluados, %d arribados (%d por hito, %d por geocerca), %d elementos apagados.",
        resumen.evaluados,
        resumen.arribados,
        resumen.por_fuente,
        resumen.por_geocerca,
        resumen.elementos_apagados,
    )
    return resumen


async def _elementos_activos(sesion: AsyncSession) -> int:
    total = await sesion.scalar(
        select(func.count())
        .select_from(ElementoRastreado)
        .where(ElementoRastreado.activo.is_(True))
    )
    return int(total or 0)


__all__ = [
    "CLAVE_RADIO",
    "ETAPA_EN_DESTINO",
    "ORIGEN_CONFIRMADO",
    "ORIGEN_FUENTE",
    "ORIGEN_GEOCERCA",
    "SIN_ARRIBO",
    "SIN_ELEMENTO",
    "ResultadoArribo",
    "ResumenArribos",
    "evaluar",
    "evaluar_todos",
]
