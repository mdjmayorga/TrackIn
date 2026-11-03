"""Persistencia de una lectura de ShipsGo — `US-45` / RF-20, RF-21, RNF-13.

Toma lo que `shipsgo.interpretar` extrajo y lo escribe donde corresponde. Es el
único módulo de los tres que toca la base.

Qué se guarda y dónde
----------------------

| Dato | Destino | Por qué |
|---|---|---|
| Payload completo | `historial_tracking.payload_api` | RF-21 / RNF-13, y porque ShipsGo **archiva** lo entregado |
| Posición | `historial_tracking` + `elementos_rastreados.posicion_actual` | RF-20: el mapa lee la desnormalizada |
| Nave e IMO | `elementos_rastreados.nombre` / `.imo` | `US-45`; el mapa (`US-27`) y el detalle (`US-44`) los consumen |
| ETA | `elementos_rastreados.eta_api` | Tercer escalón de RN-14 (`US-09`). Solo si ShipsGo la calcula para uno de nuestros destinos |
| ATA | `elementos_rastreados.ata_api` | Solo si hay hito de arribo en **uno de nuestros destinos** |

El destino final lo sabe TrackIn, no ShipsGo
--------------------------------------------

Hasta el 02/11/2026 la ATA salía de la primera llegada al destino **que declara
ShipsGo** en la ruta, y si la ruta no traía destino, de **cualquier** llegada.
Con una ruta incompleta —una guía cuyo último tramo conocido termina en
Fráncfort— o sin destino, una llegada al puerto de transbordo daba el pedido por
arribado. Ahora cuenta solo una llegada a un destino activo del maestro
(Moín, Limón, Caldera, Juan Santamaría), con los códigos de ShipsGo traducidos
(`destino_shipsgo.EQUIVALENCIAS`). Del maestro y no del destino de cada pedido:
la carga corrige ese destino con el puerto que declara la naviera (`US-54`), y
una llegada a Moín de un pedido que decía Limón también es la llegada final.

El payload se guarda aunque no haya posición
---------------------------------------------

Es el punto que separa a esta fuente de AIS. Con AIS, sin posición no hay nada
que registrar. Con ShipsGo, la respuesta **sin** posición sigue trayendo hitos,
ETA y transbordo, y encima el embarque puede archivarse: si no se guarda, la
única copia de lo que la fuente dijo desaparece.

Por eso, cuando no hay coordenadas, se registra igual usando la posición previa
conocida del elemento —o ninguna— y el payload entero. `historial_tracking`
exige coordenadas, así que sin posición previa se anota solo en el elemento y
se deja constancia en el log: perder el payload sería peor, pero inventar una
posición sería mucho peor.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.services import historial, transbordos
from app.services.rastreo import shipsgo
from app.services.rastreo.destino_shipsgo import EQUIVALENCIAS
from app.services.rastreo.shipsgo_cliente import CAMPO_POR_TIPO

logger = logging.getLogger(__name__)

#: Motivos por los que una lectura no se aplica.
DESCARTE_SIN_MADURAR = "embarque_sin_madurar"
DESCARTE_SIN_DATOS = "lectura_sin_datos"


@dataclass(frozen=True, slots=True)
class ResultadoLectura:
    """Qué se hizo con la lectura."""

    aplicada: bool
    motivo: str
    lectura: shipsgo.LecturaEmbarque | None = None
    #: `True` si la posición llegó a `historial_tracking`.
    posicion_registrada: bool = False
    #: `True` si el payload quedó guardado, con o sin posición.
    payload_guardado: bool = False
    transbordo_detectado: bool = False


async def destinos_finales(sesion: AsyncSession, via: str) -> frozenset[str]:
    """Los códigos de los destinos activos del maestro para esa vía."""
    codigos = await sesion.scalars(
        select(MaestroDestino.codigo).where(
            MaestroDestino.activo.is_(True), MaestroDestino.via_transporte == via
        )
    )
    return frozenset(codigos)


def es_destino_final(puerto: str | None, destinos: frozenset[str]) -> bool:
    """Si un puerto o aeropuerto de ShipsGo es uno de nuestros destinos."""
    return puerto is not None and EQUIVALENCIAS.get(puerto, puerto) in destinos


def llegada_a_destino_final(
    lectura: shipsgo.LecturaEmbarque, destinos: frozenset[str]
) -> dt.datetime | None:
    """La primera llegada ocurrida en uno de nuestros destinos, o `None`.

    Una llegada a un puerto de transbordo no cuenta, aunque ShipsGo lo declare
    como destino de la ruta: el pedido sigue en tránsito.
    """
    for hito in lectura.hitos:
        if (
            hito.ocurrido
            and shipsgo.es_arribo(hito, lectura.via)
            and es_destino_final(hito.puerto, destinos)
        ):
            return hito.instante
    return None


#: Los hitos que van a la línea de tiempo (`US-29`): salidas, llegadas, descargas.
#: Lo previo a la salida —cargado al buque, recibido del expedidor— queda fuera
#: para que el primer hito sea la salida del origen (decisión del 02/11/2026).
EVENTOS_DE_LA_LINEA: Final[dict[str, frozenset[str]]] = {
    shipsgo.VIA_MARITIMA: frozenset({"DEPA", "ARRV", "DISC"}),
    shipsgo.VIA_AEREA: frozenset({"DEP", "ARR", "RCF", "DLV"}),
}


def hitos_del_viaje(
    lectura: shipsgo.LecturaEmbarque, destinos: frozenset[str]
) -> list[dict[str, Any]]:
    """Los hitos ocurridos, en orden y sin repetir, para `hitos_viaje`.

    Un BL con varios contenedores repite cada movimiento por contenedor: se
    queda uno por evento, lugar e instante. `destino_final` marca la llegada a
    uno de nuestros destinos, con la misma regla que la ATA.
    """
    eventos = EVENTOS_DE_LA_LINEA.get(lectura.via, frozenset())
    vistos: set[tuple[str, str | None, dt.datetime]] = set()
    hitos: list[dict[str, Any]] = []
    for hito in sorted(
        (h for h in lectura.hitos if h.ocurrido and h.instante and h.evento in eventos),
        key=lambda h: h.instante or dt.datetime.min.replace(tzinfo=dt.UTC),
    ):
        assert hito.instante is not None
        clave = (hito.evento, hito.puerto, hito.instante)
        if clave in vistos:
            continue
        vistos.add(clave)
        hitos.append(
            {
                "evento": hito.evento,
                "instante": hito.instante.isoformat(),
                "puerto": hito.puerto,
                "puerto_nombre": hito.puerto_nombre,
                "pais": hito.pais,
                "pais_nombre": hito.pais_nombre,
                "vehiculo": hito.buque,
                "destino_final": shipsgo.es_arribo(hito, lectura.via)
                and es_destino_final(hito.puerto, destinos),
            }
        )
    return hitos


async def procesar(
    sesion: AsyncSession,
    elemento: ElementoRastreado,
    shipment: dict[str, Any] | None,
    geojson: dict[str, Any] | None = None,
    instante: dt.datetime | None = None,
) -> ResultadoLectura:
    """Aplica una respuesta de ShipsGo al elemento rastreado.

    **No hace commit**: quien llama procesa un lote.
    """
    if not shipsgo.esta_maduro(shipment):
        # El tercer estado: dado de alta y todavía sin datos (~90 s). No es un
        # fallo ni una respuesta vacía definitiva.
        logger.info(
            "ShipsGo: el embarque de %s sigue madurando; se reintenta luego.",
            elemento.tracking_externo,
        )
        return ResultadoLectura(False, DESCARTE_SIN_MADURAR)

    lectura = shipsgo.interpretar(shipment, geojson)
    if not lectura.hitos and lectura.eta is None:
        return ResultadoLectura(False, DESCARTE_SIN_DATOS, lectura)

    ahora = instante or dt.datetime.now(dt.UTC)
    resultado_posicion = False

    # --- El elemento rastreado ---------------------------------------------
    if lectura.vehiculo_actual is not None:
        elemento.nombre = lectura.vehiculo_actual.nombre[:120]
        if lectura.vehiculo_actual.imo is not None:
            elemento.imo = lectura.vehiculo_actual.imo
    destinos = await destinos_finales(sesion, elemento.via_transporte)
    if es_destino_final(lectura.puerto_destino, destinos):
        elemento.eta_api = lectura.eta
    else:
        # ShipsGo calcula la ETA para el destino que declara. Si es un
        # transbordo —la guía `78469391954` declaraba París—, esa ETA no es la
        # llegada a Costa Rica, y como fecha de llegada sería falsa (02/11/2026).
        elemento.eta_api = None
    ata = llegada_a_destino_final(lectura, destinos)
    if ata is not None:
        elemento.ata_api = ata
    # `US-29`: la lista vigente, entera; reemplazarla es lo que evita duplicados.
    elemento.hitos_viaje = hitos_del_viaje(lectura, destinos)
    # El número con que ShipsGo tiene el embarque: lo pide su mapa embebido.
    campo = CAMPO_POR_TIPO.get(elemento.tipo_tracking_externo)
    registrado = (shipment or {}).get(campo) if campo else None
    if isinstance(registrado, str) and registrado.strip():
        elemento.referencia_fuente = registrado.strip()[:50]
    elemento.ultima_actualizacion_api = ahora
    if lectura.tramos_aereos:
        # `US-26`: el horario y el trazado de los vuelos, para estimar dónde va.
        elemento.trayecto_aereo = [t.como_dict() for t in lectura.tramos_aereos]
    if lectura.tramos_maritimos:
        # La ruta del barco en el mapa del panel (03/11/2026).
        elemento.trayecto_maritimo = [t.como_dict() for t in lectura.tramos_maritimos]

    # --- El historial -------------------------------------------------------
    if lectura.posicion is not None:
        longitud, latitud = lectura.posicion
        registro = await historial.registrar_posicion(
            sesion,
            id_elemento=elemento.id,
            fecha_registro=ahora,
            latitud=latitud,
            longitud=longitud,
            payload=shipment or {},
            # ShipsGo **no entrega** velocidad ni rumbo, y no hacen falta:
            # RN-16 los quería para estimar la ETA y ésta llega ya calculada.
            velocidad=None,
            rumbo=None,
            estado_api=lectura.estado_fuente,
            # Un arribo se guarda sí o sí: perderlo por el submuestreo sería
            # peor que una fila de más.
            forzar=lectura.arribado,
        )
        resultado_posicion = registro.guardada
        if registro.guardada:
            elemento.posicion_actual = historial.punto_wkt(longitud, latitud)
    else:
        # Medido en el BL de COSCO: `current: null` en todas las *features*.
        logger.info(
            "ShipsGo: %s sin posición; se conservan hitos y ETA. El mapa cae al respaldo AIS.",
            elemento.tracking_externo,
        )

    if lectura.hay_transbordo:
        nuevos = await transbordos.registrar(sesion, elemento, lectura.transbordos, instante=ahora)
        if nuevos:
            logger.info(
                "ShipsGo: %s con %d transbordo(s) nuevo(s) (%s).",
                elemento.tracking_externo,
                nuevos,
                " → ".join(n.nombre for n in lectura.vehiculos),
            )

    if lectura.archivado_en is not None:
        # ShipsGo archiva solo lo terminado. El payload guardado pasa a ser la
        # única copia, y el planificador tiene que sacarlo del ciclo (`US-07`).
        logger.warning(
            "ShipsGo: el embarque de %s quedó archivado (%s); puede dejar de ser consultable.",
            elemento.tracking_externo,
            lectura.archivado_en,
        )

    return ResultadoLectura(
        aplicada=True,
        motivo="aplicada",
        lectura=lectura,
        posicion_registrada=resultado_posicion,
        payload_guardado=resultado_posicion,
        transbordo_detectado=lectura.hay_transbordo,
    )


__all__ = [
    "DESCARTE_SIN_DATOS",
    "DESCARTE_SIN_MADURAR",
    "ResultadoLectura",
    "destinos_finales",
    "EVENTOS_DE_LA_LINEA",
    "es_destino_final",
    "hitos_del_viaje",
    "llegada_a_destino_final",
    "procesar",
]
