"""ETA estimada desde posición y velocidad — `US-08` / RN-16.

Para qué sirve hoy, que no es para lo que se escribió
------------------------------------------------------

La historia nació para *«no depender del campo de texto libre que declara la
tripulación»*: en AIS la ETA la teclea alguien a bordo y suele estar vieja o
mal. Ese sigue siendo un motivo válido, pero ya no es el principal.

Hoy **ShipsGo entrega la ETA ya calculada** por la naviera
(`date_of_discharge_predicted`), y una predicción del transportista es mejor que
una división de distancia entre velocidad. Por eso `US-08` se mantuvo `Could`.

Lo que sí resuelve, y es concreto: la fase 3 de `TASK-28` midió que **en uno de
los dos embarques la ETA de ShipsGo vino vacía**. Con dos casos no alcanza para
saber si es transitorio o depende del carrier, pero basta para justificar un
respaldo. Esto es ese respaldo.

De dónde sale la velocidad
---------------------------

**Solo de AIS.** ShipsGo no entrega velocidad ni rumbo —medido y confirmado—,
así que este cálculo únicamente funciona para naves seguidas por MMSI vía
AISStream. Y AIS no cubre **ningún puerto de Gutis**, lo que acota aún más el
alcance: sirve en mar abierto, en la parte del trayecto donde sí hay cobertura,
y deja de servir justo al acercarse a destino.

Dicho de otro modo: esto no sustituye a ShipsGo, lo tapa cuando falla y solo a
veces. Conviene tenerlo presente antes de confiar en una fecha que salga de aquí.

Dónde entra en la precedencia de RN-14 — y por qué no donde dice el criterio
-----------------------------------------------------------------------------

El cuarto criterio de la historia dice que *«la calculada es la que alimenta
RN-01»*, por encima de la declarada por la fuente. **Eso se escribió cuando «la
fuente» era AIS**, es decir texto libre de la tripulación.

Con ShipsGo la premisa cambió: su ETA es la predicción de la naviera sobre su
propia operación, con transbordos y escalas incluidos. Ganarle con una división
de distancia entre velocidad sería peor información presentada con más
seguridad. Así que la estimada entra **por debajo de la ETA de la fuente y por
encima de la declarada en el archivo**:

    ATA confirmada > ATA inferida > ETA de la fuente > **ETA estimada** > ETA del archivo

Es un cambio consciente sobre el criterio literal, por un supuesto que el spike
tumbó. Si Logística prefiere el orden original, es cambiar una tupla.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.pedido_transito import PedidoTransito
from app.services import parametros

logger = logging.getLogger(__name__)

CLAVE_VELOCIDAD_MINIMA = "velocidad_minima_eta_nudos"

#: Metros en una milla náutica. Un nudo es una milla náutica por hora.
METROS_POR_MILLA_NAUTICA = 1852.0

#: Por qué no se pudo estimar.
SIN_POSICION = "sin_posicion_conocida"
SIN_VELOCIDAD = "sin_velocidad_conocida"
SIN_DESTINO = "sin_destino"
DEMASIADO_LENTO = "velocidad_bajo_el_minimo"


@dataclass(frozen=True, slots=True)
class EtaEstimada:
    """La ETA calculada y **todo lo que se usó para calcularla**.

    El cuarto criterio pide poder auditarlo: *«expone la distancia, la velocidad
    y la hora usadas»*. Una fecha sin sus insumos no se puede discutir, y esta
    en particular hay que poder discutirla: sale de una recta entre dos puntos
    y un barco no navega en línea recta.
    """

    eta: dt.datetime | None
    #: Metros al destino, en el elipsoide, según PostGIS.
    distancia_m: float | None
    velocidad_nudos: float | None
    #: Instante de la lectura de posición que se usó como origen.
    desde: dt.datetime | None
    horas: float | None = None
    motivo: str = ""

    def __bool__(self) -> bool:
        return self.eta is not None

    @property
    def desglose(self) -> str:
        """El cálculo en una línea, para el detalle del pedido (RF-05)."""
        if self.eta is None:
            return f"ETA no estimable: {self.motivo}"
        millas = (self.distancia_m or 0) / METROS_POR_MILLA_NAUTICA
        return (
            f"{millas:.0f} mn a {self.velocidad_nudos} nudos = {self.horas:.1f} h "
            f"desde {self.desde} → {self.eta}"
        )


def calcular(
    *,
    distancia_m: float | None,
    velocidad_nudos: float | Decimal | None,
    desde: dt.datetime | None,
    velocidad_minima_nudos: float | Decimal,
) -> EtaEstimada:
    """Distancia entre velocidad. Función pura: ni base ni red.

    **La distancia es en línea recta**, y un barco no navega así: rodea costas,
    cruza canales y espera turno en fondeaderos. El resultado es un piso
    optimista, no una predicción. Por eso el desglose viaja con la fecha.
    """
    if desde is None:
        return EtaEstimada(None, distancia_m, None, None, motivo=SIN_POSICION)
    if distancia_m is None:
        return EtaEstimada(None, None, None, desde, motivo=SIN_POSICION)
    if velocidad_nudos is None:
        return EtaEstimada(None, distancia_m, None, desde, motivo=SIN_VELOCIDAD)

    velocidad = float(velocidad_nudos)
    minima = float(velocidad_minima_nudos)

    if velocidad < minima:
        # Segundo criterio: **no se estima**. Una nave fondeada o maniobrando a
        # 0,3 nudos daría una ETA de meses, que es peor que no dar ninguna:
        # una fecha absurda en la grilla se lee como un error del sistema y
        # hace desconfiar del resto.
        return EtaEstimada(None, distancia_m, velocidad, desde, motivo=DEMASIADO_LENTO)

    millas = distancia_m / METROS_POR_MILLA_NAUTICA
    horas = millas / velocidad
    return EtaEstimada(
        eta=desde + dt.timedelta(hours=horas),
        distancia_m=distancia_m,
        velocidad_nudos=velocidad,
        desde=desde,
        horas=horas,
    )


async def _distancia_al_destino(
    sesion: AsyncSession, elemento: ElementoRastreado, destino: MaestroDestino
) -> float | None:
    """Metros al destino sobre el elipsoide, vía PostGIS.

    Se vacía la sesión antes de medir por la misma razón que en `arribo`: la
    posición puede venir recién asignada en memoria, y `ST_Distance(NULL, …)`
    devuelve `NULL`, que aquí se leería como «sin posición» — un caso legítimo.
    El fallo sería mudo.
    """
    if elemento.posicion_actual is None:
        return None
    await sesion.flush()

    punto_elemento = (
        select(ElementoRastreado.posicion_actual)
        .where(ElementoRastreado.id == elemento.id)
        .scalar_subquery()
    )
    punto_destino = (
        select(MaestroDestino.ubicacion).where(MaestroDestino.id == destino.id).scalar_subquery()
    )
    distancia = await sesion.scalar(select(func.ST_Distance(punto_elemento, punto_destino)))
    return float(distancia) if distancia is not None else None


async def estimar(
    sesion: AsyncSession,
    pedido: PedidoTransito,
    velocidad_minima: float | Decimal | None = None,
) -> EtaEstimada:
    """La ETA estimada del pedido. **No persiste nada.**

    Devuelve el resultado con su motivo cuando no se puede estimar, en vez de
    lanzar: «ETA no estimable» es una respuesta legítima y frecuente, no un
    error.
    """
    if pedido.id_elemento_rastreado is None:
        return EtaEstimada(None, None, None, None, motivo=SIN_POSICION)

    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    destino = await sesion.get(MaestroDestino, pedido.id_destino)
    if elemento is None or destino is None:
        return EtaEstimada(None, None, None, None, motivo=SIN_DESTINO)

    if velocidad_minima is None:
        velocidad_minima = await parametros.obtener_decimal(sesion, CLAVE_VELOCIDAD_MINIMA)

    distancia = await _distancia_al_destino(sesion, elemento, destino)
    resultado = calcular(
        distancia_m=distancia,
        velocidad_nudos=elemento.velocidad_actual,
        desde=elemento.ultima_actualizacion_api,
        velocidad_minima_nudos=velocidad_minima,
    )

    if resultado.eta is None:
        logger.debug("Pedido %s: ETA no estimable — %s", pedido, resultado.motivo)
    else:
        logger.info("Pedido %s: ETA estimada — %s", pedido, resultado.desglose)
    return resultado


__all__ = [
    "CLAVE_VELOCIDAD_MINIMA",
    "DEMASIADO_LENTO",
    "METROS_POR_MILLA_NAUTICA",
    "SIN_DESTINO",
    "SIN_POSICION",
    "SIN_VELOCIDAD",
    "EtaEstimada",
    "calcular",
    "estimar",
]
