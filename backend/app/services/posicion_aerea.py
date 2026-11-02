"""Dónde está un embarque aéreo, estimado con el horario del vuelo — `US-26`.

ShipsGo no da la posición de un avión: la API aérea no trae `current` en el
trazado (medido en el MAWB de Lufthansa del spike `TASK-28`). Sí da, por tramo,
el vuelo, el trazado, la hora de salida y la de llegada. Con eso se **estima**:

| Momento | Dónde se dibuja | `situacion` |
|---|---|---|
| Antes de la primera salida | El aeropuerto de origen | `EN_TIERRA` |
| Entre la salida y la llegada de un tramo | Sobre el trazado, en la fracción del vuelo transcurrida | `EN_VUELO` |
| Entre dos tramos (transbordo) | El aeropuerto donde espera | `EN_TIERRA` |
| Después de la última llegada | El aeropuerto de destino | `FINALIZADO` |

**El destino final lo sabe TrackIn, no el trazado** (02/11/2026). ShipsGo a veces
entrega el trazado sin el último vuelo: la guía `020-05128546` llegó a SJO, pero
su trazado terminaba en Fráncfort y el mapa la dibujaba «concluida» ahí. Ahora:

- Si ya llegó a nuestro destino (`ata_api`, que solo cuenta llegadas a destinos
  del maestro), se dibuja en el aeropuerto de destino, `FINALIZADO`.
- Si el último tramo conocido termina en otro aeropuerto y no llegó, está en
  tierra ahí esperando el vuelo siguiente, `EN_TIERRA`: no «concluido».

Decisión del 06/10/2026: OpenSky salió por su licencia; el mapa aéreo muestra la
posición **estimada**, rotulada como tal. Por eso no se escribe en
`posicion_actual`: la geocerca (RN-05) la tomaría por real y podría dar por
arribado un vuelo que todavía no aterrizó.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Final, Literal

Situacion = Literal["EN_VUELO", "EN_TIERRA", "FINALIZADO"]

EN_VUELO: Final = "EN_VUELO"
EN_TIERRA: Final = "EN_TIERRA"
FINALIZADO: Final = "FINALIZADO"


@dataclass(frozen=True, slots=True)
class Estimacion:
    longitud: float
    latitud: float
    situacion: Situacion
    #: El vuelo del tramo en curso, o el último que voló.
    vuelo: str | None
    #: El aeropuerto donde está, si está en tierra.
    lugar: str | None
    #: El trazado del tramo en vuelo, `(longitud, latitud)`, para dibujarlo.
    ruta: list[tuple[float, float]] | None


def _instante(valor: Any) -> dt.datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        instante = dt.datetime.fromisoformat(valor)
    except ValueError:
        return None
    return instante if instante.tzinfo is not None else None


def _punto_en_ruta(ruta: list[tuple[float, float]], fraccion: float) -> tuple[float, float]:
    """El punto a esa fracción del recorrido, medido a lo largo del trazado.

    El trazado de ShipsGo ya es la ruta curva (30 puntos por tramo): basta con
    repartir la fracción entre sus segmentos según su largo. En distancias
    cortas el largo en grados alcanza; no hace falta geodesia para un punto que
    de todos modos es una estimación.
    """
    if len(ruta) == 1:
        return ruta[0]
    largos = [math.dist(a, b) for a, b in pairwise(ruta)]
    total = sum(largos)
    if total == 0:
        return ruta[0]
    objetivo = max(0.0, min(1.0, fraccion)) * total
    recorrido = 0.0
    for (a, b), largo in zip(pairwise(ruta), largos, strict=True):
        if recorrido + largo >= objetivo:
            t = (objetivo - recorrido) / largo if largo else 0.0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        recorrido += largo
    return ruta[-1]


def estimar(
    trayecto: list[dict[str, Any]] | None,
    ahora: dt.datetime,
    *,
    destinos_finales: frozenset[str] = frozenset(),
    llegada: tuple[float, float, str] | None = None,
) -> Estimacion | None:
    """La posición estimada en `ahora`, o `None` si el trayecto no alcanza.

    `trayecto` es lo que guarda el colector en `elementos_rastreados.trayecto_aereo`
    (`shipsgo.TramoAereo.como_dict`), en orden de vuelo. `destinos_finales` son los
    códigos de aeropuerto que cuentan como destino final; vacío, se confía en el
    trazado. `llegada` es `(longitud, latitud, aeropuerto)` del destino si ya llegó.
    """
    tramos = []
    for crudo in trayecto or []:
        ruta = [(float(p[0]), float(p[1])) for p in crudo.get("ruta") or [] if len(p) >= 2]
        salida = _instante(crudo.get("salida"))
        aterriza = _instante(crudo.get("llegada"))
        if ruta and salida and aterriza:
            tramos.append((crudo, ruta, salida, aterriza))
    if llegada is not None:
        vuelo = tramos[-1][0].get("vuelo") if tramos else None
        # Si el trazado no llega al destino, su último vuelo no es el que aterrizó.
        if not tramos or tramos[-1][0].get("destino") != llegada[2]:
            vuelo = None
        return Estimacion(llegada[0], llegada[1], FINALIZADO, vuelo, llegada[2], None)
    if not tramos:
        return None

    primero, ruta0, salida0, _ = tramos[0]
    if ahora < salida0:
        return Estimacion(*ruta0[0], EN_TIERRA, primero.get("vuelo"), primero.get("origen"), None)

    for indice, (tramo, ruta, salida, aterriza) in enumerate(tramos):
        if salida <= ahora < aterriza:
            fraccion = (ahora - salida) / (aterriza - salida)
            return Estimacion(
                *_punto_en_ruta(ruta, fraccion), EN_VUELO, tramo.get("vuelo"), None, ruta
            )
        siguiente = tramos[indice + 1] if indice + 1 < len(tramos) else None
        if siguiente is not None and aterriza <= ahora < siguiente[2]:
            # Transbordo: en tierra donde aterrizó, esperando el vuelo siguiente.
            return Estimacion(*ruta[-1], EN_TIERRA, tramo.get("vuelo"), tramo.get("destino"), None)

    ultimo, ruta_n, _, _ = tramos[-1]
    if destinos_finales and ultimo.get("destino") not in destinos_finales:
        # El trazado se corta en un transbordo: espera ahí el vuelo que falta.
        return Estimacion(*ruta_n[-1], EN_TIERRA, ultimo.get("vuelo"), ultimo.get("destino"), None)
    return Estimacion(*ruta_n[-1], FINALIZADO, ultimo.get("vuelo"), ultimo.get("destino"), None)


__all__ = ["EN_TIERRA", "EN_VUELO", "FINALIZADO", "Estimacion", "Situacion", "estimar"]
