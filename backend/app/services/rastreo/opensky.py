"""Lectura de posiciones ADS-B de OpenSky — `US-05` / RF-07.

Traduce el vector de estado de `/states/all` a los conceptos de TrackIn. **No
habla por red y no toca la base**: el cliente vive en `opensky_cliente.py`.

Qué papel juega OpenSky después de `TASK-28`
---------------------------------------------

Cambió, y conviene tenerlo presente al leer esto. La historia se escribió
cuando la posición de la aeronave iba a ser el rastreo aéreo; hoy **el estado
del envío lo dan los hitos CIMP de ShipsGo Air** (`US-46`), que dicen dónde está
la carga y no dónde está el avión. OpenSky pasa a ser lo que AIS es en marítimo:
**respaldo del mapa**, no fuente del semáforo. Por eso `US-05` y `US-06` bajaron
de `Must` a `Should` el 22/09.

La trampa que cuesta un `TypeError`
------------------------------------

Cuando no hay aeronaves, la API devuelve **`states: null`, no una lista vacía**.
Iterar el resultado sin comprobarlo revienta. Y no es un caso excepcional: pasa
con un `icao24` inexistente **y** con un *bounding box* sin tráfico, que es lo
normal de madrugada. `parsear_estados` normaliza `null → []` en el borde, para
que nadie aguas abajo tenga que acordarse.

Lo que el vector no dice
-------------------------

Medido por TG-11 con datos reales, no hipotéticos:

- **La altitud viene `null` en tierra**, en el 100 % de los casos. Es correcto
  por diseño y el modelo tiene que admitirlo.
- **El `callsign` puede llegar nulo y aparecer minutos después**: `0ae105`
  reportó `null` y `TIAGO` tres minutos más tarde. **El `icao24` es el
  identificador estable**; el callsign no es confiable de inmediato.
- **El `squawk` vino nulo en las 14 aeronaves** de la muestra. Descartado como
  vía de identificación.
- **La API deja de listar una aeronave sin decir por qué.** Salió del área,
  aterrizó o se perdió la señal son tres cosas distintas y llegan iguales. De
  ahí `antiguedad_s`: lo honesto es decir «última posición hace N minutos», no
  afirmar «en ruta».
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Final

logger = logging.getLogger(__name__)

#: Posición de cada campo en el vector de estado de `/states/all`.
#: La API entrega arreglos posicionales, no objetos: un índice mal puesto
#: cambia la latitud por la longitud sin que nada falle.
INDICE: Final[dict[str, int]] = {
    "icao24": 0,
    "callsign": 1,
    "pais_origen": 2,
    "instante_posicion": 3,
    "ultimo_contacto": 4,
    "longitud": 5,
    "latitud": 6,
    "altitud_baro": 7,
    "en_tierra": 8,
    "velocidad": 9,
    "rumbo": 10,
    "razon_ascenso": 11,
    "sensores": 12,
    "altitud_geo": 13,
    "squawk": 14,
    "spi": 15,
    "origen_posicion": 16,
}

#: Metros por segundo a nudos. OpenSky entrega m/s; `historial_tracking` guarda
#: nudos, como AIS, para que las dos fuentes sean comparables en la misma
#: columna.
_NUDOS_POR_MS: Final = 1.943844


@dataclass(frozen=True, slots=True)
class PosicionAerea:
    """Una aeronave en un instante, tal como la reporta OpenSky."""

    icao24: str
    #: Puede ser `None`: llega tarde y no es confiable de inmediato.
    callsign: str | None
    instante: dt.datetime
    latitud: float
    longitud: float
    #: `None` en tierra, en el 100 % de los casos medidos.
    altitud_m: float | None
    en_tierra: bool
    velocidad_nudos: float | None
    rumbo_grados: float | None
    razon_ascenso_ms: float | None
    #: Segundos entre la hora del servidor y el último contacto. `None` si el
    #: payload no trae la hora del servidor.
    antiguedad_s: float | None
    payload: dict[str, Any]

    @property
    def aterrizando(self) -> bool:
        """Si la lectura sugiere aterrizaje **y no** pérdida de señal.

        TG-11 midió el caso contrario y es el que importa: `LRS1018`, bajando a
        -4,88 m/s, con 207 s de antigüedad. Se pierde la línea de vista con el
        receptor justo cuando se quiere confirmar el aterrizaje. Afirmar
        «aterrizó» con esa lectura sería inventar.
        """
        return self.en_tierra


def _campo(vector: list[Any], nombre: str) -> Any:
    indice = INDICE[nombre]
    return vector[indice] if len(vector) > indice else None


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        return float(valor)
    return None


def parsear_estado(
    vector: list[Any], hora_servidor: int | float | None = None
) -> PosicionAerea | None:
    """Un vector de estado a `PosicionAerea`, o `None` si no es utilizable.

    Se descarta **solo** lo que no se puede situar: sin `icao24` no hay a qué
    atribuir la lectura, y sin coordenadas no hay posición. Todo lo demás
    —altitud, velocidad, rumbo, callsign— puede faltar y la lectura sirve
    igual, que es exactamente lo que ocurre con una aeronave en tierra.
    """
    if not isinstance(vector, list):
        return None

    icao24 = _texto(_campo(vector, "icao24"))
    latitud = _numero(_campo(vector, "latitud"))
    longitud = _numero(_campo(vector, "longitud"))
    if icao24 is None or latitud is None or longitud is None:
        return None

    ultimo_contacto = _numero(_campo(vector, "ultimo_contacto"))
    instante_posicion = _numero(_campo(vector, "instante_posicion"))
    marca = instante_posicion or ultimo_contacto
    if marca is None:
        return None
    instante = dt.datetime.fromtimestamp(marca, tz=dt.UTC)

    antiguedad = None
    if hora_servidor is not None and ultimo_contacto is not None:
        antiguedad = float(hora_servidor) - ultimo_contacto

    # La barométrica es la de referencia; la geométrica sirve de respaldo. En
    # tierra las dos vienen nulas y eso es correcto por diseño.
    altitud = _numero(_campo(vector, "altitud_baro"))
    if altitud is None:
        altitud = _numero(_campo(vector, "altitud_geo"))

    velocidad_ms = _numero(_campo(vector, "velocidad"))

    return PosicionAerea(
        icao24=icao24.lower(),
        callsign=_texto(_campo(vector, "callsign")),
        instante=instante,
        latitud=latitud,
        longitud=longitud,
        altitud_m=altitud,
        en_tierra=bool(_campo(vector, "en_tierra")),
        velocidad_nudos=(
            round(velocidad_ms * _NUDOS_POR_MS, 2) if velocidad_ms is not None else None
        ),
        rumbo_grados=_numero(_campo(vector, "rumbo")),
        razon_ascenso_ms=_numero(_campo(vector, "razon_ascenso")),
        antiguedad_s=antiguedad,
        payload={"vector": vector, "time": hora_servidor},
    )


def parsear_estados(cuerpo: dict[str, Any] | None) -> list[PosicionAerea]:
    """Todas las aeronaves de una respuesta de `/states/all`.

    **Normaliza `states: null` a lista vacía.** Es la trampa que TG-11 documentó
    y se resuelve aquí, en el borde, para que nadie aguas abajo tenga que
    acordarse: un *bounding box* sin tráfico de madrugada es normal, no un error.
    """
    if not isinstance(cuerpo, dict):
        return []

    vectores = cuerpo.get("states")
    if vectores is None:
        # No es un fallo: es el caso corriente cuando no hay tráfico.
        return []
    if not isinstance(vectores, list):
        logger.warning("OpenSky: 'states' no es una lista (%s); se descarta.", type(vectores))
        return []

    hora = cuerpo.get("time")
    posiciones: list[PosicionAerea] = []
    for vector in vectores:
        posicion = parsear_estado(vector, hora)
        if posicion is not None:
            posiciones.append(posicion)
    return posiciones


def por_callsign(posiciones: list[PosicionAerea], callsign: str) -> PosicionAerea | None:
    """La aeronave que lleva ese callsign, ignorando espacios y mayúsculas.

    OpenSky rellena el callsign con espacios a la derecha (`"AVA072  "`), así
    que comparar sin normalizar no encuentra nada.
    """
    objetivo = callsign.strip().upper()
    for posicion in posiciones:
        if posicion.callsign and posicion.callsign.strip().upper() == objetivo:
            return posicion
    return None


def por_icao24(posiciones: list[PosicionAerea], icao24: str) -> PosicionAerea | None:
    objetivo = icao24.strip().lower()
    for posicion in posiciones:
        if posicion.icao24 == objetivo:
            return posicion
    return None


__all__ = [
    "INDICE",
    "PosicionAerea",
    "parsear_estado",
    "parsear_estados",
    "por_callsign",
    "por_icao24",
]
