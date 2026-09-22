"""El semáforo: cumplimiento y estado único — `US-10` / RF-11, RN-07 a RN-13.

El estado **son dos dimensiones, no una** (§1.4 del modelo, aprobado el 25/08).
Un pedido en tránsito que llegará tarde es a la vez `EN_TRANSITO` (RN-04) y
`RETRASADO` (RN-09), y colapsarlo en una columna obliga a tirar información que
alguien necesita: Logística pregunta **dónde está** la carga y Compras pregunta
**si llega a tiempo**.

| Dimensión | Quién la produce |
|---|---|
| `etapa_viaje` | El rastreo: RN-02 a RN-06 |
| `estado_cumplimiento` | Este módulo, comparando la proyectada con la comprometida |
| `estado_calculado` | Este módulo, derivando las dos anteriores |

Los tres solapamientos del articulado, ya resueltos
----------------------------------------------------

Al implementar esto aparecen tres reglas que se pisan. Quedaron decididas el
26/08 y aquí solo se aplican:

1. **RN-08 prevalece sobre RN-07.** RN-07 dice «anterior o igual» sin calificar
   y colisiona con RN-08 en la ventana previa. Gana la más específica:
   `A_TIEMPO` exige margen **estrictamente mayor** que el umbral; dentro del
   umbral es `EN_RIESGO`.
2. **El umbral son días, no horas.** RN-11 lo escribe en horas, pero las dos
   fechas son `DATE` sin hora: comparar 48 h contra fechas sin hora es comparar
   una precisión que el dato no tiene. Son **2 días** por defecto, en
   `parametros_sistema.umbral_riesgo_dias` para poder cambiarlo sin desplegar.
3. ~~`EN_DESTINO` dura 30 minutos y luego pasa a `EN_PROCESO_ADUANAL`.~~
   **Anulada el 04/09.** Planeación confirmó que el paso a proceso aduanal es
   **manual por proceso**, no por falta de datos. No hay transición por tiempo,
   y por eso este módulo no mira el reloj en ninguna parte.

Por qué el riesgo manda sobre la etapa
---------------------------------------

Al derivar `estado_calculado`, `RETRASADO` y `EN_RIESGO` ganan a la etapa. Es la
información por la que existe el sistema: quien abre el dashboard quiere ver
primero lo que exige atención, no dónde está cada caja.

El único que gana al riesgo es el cierre (RN-13): un pedido cerrado ya no está
en riesgo de nada.
"""

from __future__ import annotations

import datetime as dt
from typing import Final

#: Dominio de `estado_cumplimiento` (RN-07 a RN-09).
A_TIEMPO: Final = "A_TIEMPO"
EN_RIESGO: Final = "EN_RIESGO"
RETRASADO: Final = "RETRASADO"

#: Etapa sin rastreo (RN-02) y estados terminales (RN-13).
SIN_TRACKING: Final = "SIN_TRACKING"
CERRADO: Final = "CERRADO"
CANCELADO: Final = "CANCELADO"

#: Qué estado terminal corresponde a cada motivo de cierre (RN-13).
_TERMINAL_POR_MOTIVO: Final[dict[str, str]] = {
    "RECEPCION_CONFORME": CERRADO,
    "CIERRE_FORZADO": CERRADO,
    "CANCELACION": CANCELADO,
}


def clasificar_cumplimiento(
    fecha_proyectada: dt.date | None,
    fecha_comprometida: dt.date | None,
    umbral_dias: int,
) -> str | None:
    """Compara la proyectada con la comprometida — RN-07 a RN-09.

    Devuelve `None` cuando **no se puede afirmar nada**: sin fecha proyectada no
    hay con qué comparar, y ningún valor del dominio expresa «no sé». El modelo
    lo contempla con `estado_cumplimiento` anulable, y `US-24` lo pinta en gris.

    El margen son días enteros: positivo es holgura, negativo es atraso.

        margen > umbral   → A_TIEMPO
        0 ≤ margen ≤ umbral → EN_RIESGO   (RN-08 gana a RN-07)
        margen < 0        → RETRASADO
    """
    if fecha_proyectada is None or fecha_comprometida is None:
        return None

    margen = (fecha_comprometida - fecha_proyectada).days
    if margen < 0:
        return RETRASADO
    if margen <= umbral_dias:
        return EN_RIESGO
    return A_TIEMPO


def derivar_estado_calculado(
    etapa_viaje: str,
    estado_cumplimiento: str | None,
    motivo_cierre: str | None = None,
) -> str:
    """El estado único que exige RF-11, derivado de las dos dimensiones.

    Precedencia de §1.4, en este orden exacto:

    1. Cerrado o cancelado (RN-13). Gana a todo: ya no hay nada que vigilar.
    2. `SIN_TRACKING`. No hay dato con que evaluar cumplimiento, así que la
       etapa es lo único que se puede decir.
    3. `RETRASADO` o `EN_RIESGO`. **El riesgo manda sobre la etapa.**
    4. La etapa.
    """
    if motivo_cierre is not None:
        # El `CHECK` de la tabla exige que motivo y estado terminal vayan
        # juntos; un motivo desconocido se trata como cierre, no se inventa.
        return _TERMINAL_POR_MOTIVO.get(motivo_cierre, CERRADO)

    if etapa_viaje == SIN_TRACKING:
        return SIN_TRACKING

    if estado_cumplimiento in (RETRASADO, EN_RIESGO):
        return estado_cumplimiento

    return etapa_viaje


__all__ = [
    "A_TIEMPO",
    "CANCELADO",
    "CERRADO",
    "EN_RIESGO",
    "RETRASADO",
    "SIN_TRACKING",
    "clasificar_cumplimiento",
    "derivar_estado_calculado",
]
