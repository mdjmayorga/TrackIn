"""Persistencia de una consulta a TICA — `US-49` / RN-05, RNF-13.

Toma lo que `tica_cliente.rastrear` encontró para una guía hija y lo escribe en
el elemento rastreado. Es el único módulo de TICA que toca la base.

Qué se guarda y dónde
----------------------

| Dato | Destino | Por qué |
|---|---|---|
| Fecha de arribo del manifiesto | `elementos_rastreados.ata_api` | Es una llegada **reportada por una fuente**, no deducida (RN-05) |
| Guía madre | `elementos_rastreados.guia_madre` | El número que ShipsGo sí rastrea |
| Manifiesto | `elementos_rastreados.manifiesto_aduana` | Para ubicar el envío en la aduana |
| Aerolínea de la madre | `elementos_rastreados.nombre` | El detalle (`US-44`) la muestra |
| Filas crudas | `elementos_rastreados.payload_aduana` | RNF-13; `historial_tracking` exige coordenadas |

La llegada va a `ata_api` y no a `ata_inferida` a propósito: el manifiesto de
carga es un documento oficial, no una deducción nuestra. `arribo.evaluar` ya la
toma como señal primaria y mueve el pedido a `EN_DESTINO`; este módulo **no**
cambia la etapa, por la misma razón que `colector_shipsgo` no lo hace.

Antes del arribo, no encontrarla es lo normal
----------------------------------------------

La guía aparece en TICA cuando se transmite el manifiesto, cerca de la llegada.
Una búsqueda vacía **no es un fallo** ni una respuesta definitiva: se anota la
consulta en `ultima_actualizacion_api` para que el planificador espere su
intervalo, y se vuelve a preguntar después.

Lo que no hace: gastar un crédito
----------------------------------

Si la guía madre es de una aerolínea que ShipsGo cubre, lo **señala** en el
resultado (`madre_rastreable_shipsgo`), pero no la da de alta. A esa altura la
carga ya llegó: pagar 2 USD por ver hitos de un envío terminado solo tiene
sentido si alguien lo decide. Medido con `ZIVHYD017`: su madre `574-34927513`
es de Allied Air, **inactiva** en el catálogo de ShipsGo — el alta habría
cobrado y devuelto vacío.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.services import parametros
from app.services.rastreo.shipsgo_aerolineas import CatalogoAerolineas
from app.services.rastreo.tica_cliente import ClienteTICA, ResultadoRastreo

logger = logging.getLogger(__name__)

TIPO_GUIA_HIJA: Final = "HAWB"
CLAVE_VENTANA = "ventana_tica_dias"

#: Costa Rica no cambia de hora: UTC-6 todo el año.
ZONA_CR: Final = dt.timezone(dt.timedelta(hours=-6), "America/Costa_Rica")

#: Motivos por los que una consulta no se aplica.
DESCARTE_NO_ES_HIJA = "no_es_guia_hija"
DESCARTE_SIN_MANIFIESTO = "sin_manifiesto_todavia"


@dataclass(frozen=True, slots=True)
class ResultadoAduana:
    """Qué se hizo con la consulta."""

    aplicada: bool
    motivo: str
    rastreo: ResultadoRastreo | None = None
    #: `True` si la madre es de una aerolínea activa en ShipsGo. Solo informa.
    madre_rastreable_shipsgo: bool = False


def llegada_a_instante(fecha: dt.date) -> dt.datetime:
    """El día del manifiesto, a medianoche en Costa Rica.

    TICA da la fecha y no la hora. La medianoche local es el comienzo del día
    en que la carga ya estaba en el país: poner mediodía inventaría una hora.
    """
    return dt.datetime.combine(fecha, dt.time(0, 0), tzinfo=ZONA_CR).astimezone(dt.UTC)


def _madre_en_shipsgo(rastreo: ResultadoRastreo, catalogo: CatalogoAerolineas | None) -> bool:
    if catalogo is None or rastreo.madre is None or rastreo.madre.prefijo is None:
        return False
    aerolinea = catalogo.por_prefijo.get(rastreo.madre.prefijo)
    return aerolinea is not None and aerolinea.activa


async def procesar(
    sesion: AsyncSession,
    elemento: ElementoRastreado,
    cliente: ClienteTICA,
    *,
    catalogo: CatalogoAerolineas | None = None,
    instante: dt.datetime | None = None,
) -> ResultadoAduana:
    """Consulta la guía hija en TICA y aplica lo encontrado. **No hace commit.**

    Los errores de TICA (`ErrorTICA`) se dejan subir: clasificarlos y degradar
    la fuente es de `US-03`, igual que con las demás fuentes.
    """
    if elemento.tipo_tracking_externo != TIPO_GUIA_HIJA:
        return ResultadoAduana(False, DESCARTE_NO_ES_HIJA)

    ahora = instante or dt.datetime.now(dt.UTC)
    hoy = ahora.astimezone(ZONA_CR).date()
    ventana = await parametros.obtener_entero(sesion, CLAVE_VENTANA)
    rastreo = await cliente.rastrear(
        elemento.tracking_externo, hoy - dt.timedelta(days=ventana), hoy
    )
    elemento.ultima_actualizacion_api = ahora

    ultimo = rastreo.ultimo
    if ultimo is None:
        logger.info(
            "TICA: %s todavía no aparece en ningún manifiesto; se vuelve a consultar luego.",
            elemento.tracking_externo,
        )
        return ResultadoAduana(False, DESCARTE_SIN_MANIFIESTO, rastreo)

    elemento.ata_api = llegada_a_instante(ultimo.fecha_arribo)
    elemento.manifiesto_aduana = ultimo.manifiesto[:30]
    elemento.payload_aduana = rastreo.payload
    if rastreo.madre is not None:
        elemento.guia_madre = rastreo.madre.numero[:25]
        if not elemento.nombre:
            elemento.nombre = rastreo.madre.transportista_nombre[:120]

    en_shipsgo = _madre_en_shipsgo(rastreo, catalogo)
    if rastreo.madre is not None:
        logger.info(
            "TICA: guía madre de %s es %s (%s); %s en ShipsGo.",
            elemento.tracking_externo,
            rastreo.madre.numero,
            rastreo.madre.transportista_nombre,
            "rastreable" if en_shipsgo else "no rastreable",
        )
    return ResultadoAduana(True, "aplicada", rastreo, madre_rastreable_shipsgo=en_shipsgo)


__all__ = [
    "DESCARTE_NO_ES_HIJA",
    "DESCARTE_SIN_MANIFIESTO",
    "TIPO_GUIA_HIJA",
    "ZONA_CR",
    "ResultadoAduana",
    "llegada_a_instante",
    "procesar",
]
