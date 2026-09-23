"""Fecha proyectada de disponibilidad — `US-09` / RF-10, RN-01, RN-14.

*«Fecha proyectada = ETA o ATA + lead time del destino + un ajuste manual
opcional»*. Suena a una suma y lo es; lo que tiene sustancia es **de dónde sale
la fecha base** y **cuándo no hay que producir ninguna**.

El núcleo es una función pura
------------------------------

`calcular` no toca la base ni la red: recibe las cuatro fechas candidatas y los
dos enteros, y devuelve el resultado **con su desglose**. Es deliberado. RF-05
pide *«el desglose del cálculo que produjo la fecha proyectada»*, y una regla de
negocio que solo se puede ejercitar levantando PostgreSQL es una regla que no se
prueba lo suficiente.

La precedencia de la fecha base
--------------------------------

RN-14 la fija: **lo ocurrido manda sobre lo estimado**.

| Orden | Fuente | Por qué va ahí |
|---|---|---|
| 1 | `ata_confirmada` | Una persona confirmó el arribo. Es un hecho, y además está auditado por RF-14 |
| 2 | `ata_inferida` | El sistema dedujo el arribo por hito o geocerca (RN-05). Sigue siendo un hecho, pero deducido |
| 3 | `eta_fuente` | La ETA de la fuente de rastreo — `elementos_rastreados.eta_api` |
| 4 | `eta_estimada` | La que calcula `US-08` desde posición y velocidad |
| 5 | `eta_declarada` | La que viene en el archivo. Es la más débil: la escribe una persona a mano y no se actualiza sola |

**Por qué la estimada va por debajo de la de la fuente**, contra lo que dice el
criterio literal de `US-08`: ese criterio se escribió cuando «la fuente» era AIS,
donde la ETA la teclea la tripulación. La de ShipsGo es la predicción de la
naviera sobre su propia operación, transbordos incluidos, y ganarle con una
división de distancia entre velocidad sería peor información con más aire de
certeza. El razonamiento completo está en `eta_estimada`.

Que la declarada vaya última no es desconfianza gratuita. Es exactamente el
campo que este sistema existe para reemplazar: el propósito de TrackIn es dejar
de depender de una columna que alguien mantiene a mano.

Cuándo **no** hay fecha proyectada
-----------------------------------

Dos casos, y los dos se señalan en vez de inventar un valor:

- **Ninguna fecha base.** Es lo normal hoy: un pedido `SIN_TRACKING` no tiene
  ETA de ninguna fuente, y la del archivo casi nunca viene.
- **Destino sin lead time.** Tercer criterio de `US-09`. Sin el tramo
  puerto→planta no se puede proyectar nada, y ese tramo **sigue sin dato**: la
  reunión del 04/09 lo dejó como el primer pendiente del correo a Planeación, y
  los valores del maestro son provisionales.

`None` con un motivo es más honesto que una fecha inventada: `US-10` traduce esa
ausencia a `estado_cumplimiento = NULL`, que es lo que dice «no se puede
afirmar si llega a tiempo» (§1.4 del modelo).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

#: De dónde salió la fecha base, en orden de precedencia (RN-14).
ORIGEN_ATA_CONFIRMADA: Final = "ATA_CONFIRMADA"
ORIGEN_ATA_INFERIDA: Final = "ATA_INFERIDA"
ORIGEN_ETA_FUENTE: Final = "ETA_FUENTE"
#: Calculada por `US-08` desde posición y velocidad. Solo existe con AIS.
ORIGEN_ETA_ESTIMADA: Final = "ETA_ESTIMADA"
ORIGEN_ETA_DECLARADA: Final = "ETA_DECLARADA"

#: Precedencia de RN-14, de mayor a menor. El orden **es** la regla.
PRECEDENCIA: Final[tuple[str, ...]] = (
    ORIGEN_ATA_CONFIRMADA,
    ORIGEN_ATA_INFERIDA,
    ORIGEN_ETA_FUENTE,
    ORIGEN_ETA_ESTIMADA,
    ORIGEN_ETA_DECLARADA,
)

#: Por qué no se pudo proyectar.
SIN_FECHA_BASE = "sin_fecha_base"
SIN_LEAD_TIME = "sin_lead_time"


@dataclass(frozen=True, slots=True)
class Proyeccion:
    """La fecha proyectada y **cómo se obtuvo**.

    Lleva el desglose porque RF-05 lo exige y porque una fecha sin explicación
    no se puede discutir con quien la recibe: Compras necesita poder decir «esta
    fecha sale de una ETA de hace seis días» para saber cuánto confiar en ella.
    """

    fecha: dt.date | None
    #: `None` cuando no hubo fecha base.
    origen: str | None
    #: La fecha base usada, antes de sumarle nada.
    base: dt.date | None
    lead_time_dias: int | None
    ajuste_manual_dias: int
    #: Vacío cuando sí hay fecha; el porqué cuando no.
    motivo: str = ""

    def __bool__(self) -> bool:
        return self.fecha is not None

    @property
    def desglose(self) -> str:
        """El cálculo en una línea, para el detalle del pedido (RF-05)."""
        if self.fecha is None:
            return f"Sin fecha proyectada: {self.motivo}"
        partes = f"{self.base} ({self.origen}) + {self.lead_time_dias} d de lead time"
        if self.ajuste_manual_dias:
            partes += f" + {self.ajuste_manual_dias} d de ajuste manual"
        return f"{partes} = {self.fecha}"


def _a_fecha(valor: dt.date | dt.datetime | None) -> dt.date | None:
    """Las ATA y la ETA de la fuente son `TIMESTAMPTZ`; la proyectada es `DATE`.

    El corte se hace acá y no en el modelo porque la hora **sí** importa para
    auditar cuándo se supo algo, pero no para una fecha de disponibilidad: nadie
    planifica materiales con precisión de minutos.
    """
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    return valor


def calcular(
    *,
    ata_confirmada: dt.date | dt.datetime | None = None,
    ata_inferida: dt.date | dt.datetime | None = None,
    eta_fuente: dt.date | dt.datetime | None = None,
    eta_estimada: dt.date | dt.datetime | None = None,
    eta_declarada: dt.date | dt.datetime | None = None,
    lead_time_dias: int | None,
    ajuste_manual_dias: int = 0,
) -> Proyeccion:
    """Aplica RN-01 con la precedencia de RN-14.

    Todo por palabra clave a propósito: son cuatro fechas del mismo tipo y
    confundir dos posicionales sería un error silencioso que ninguna prueba
    de tipos atraparía.
    """
    candidatas: dict[str, dt.date | None] = {
        ORIGEN_ATA_CONFIRMADA: _a_fecha(ata_confirmada),
        ORIGEN_ATA_INFERIDA: _a_fecha(ata_inferida),
        ORIGEN_ETA_FUENTE: _a_fecha(eta_fuente),
        ORIGEN_ETA_ESTIMADA: _a_fecha(eta_estimada),
        ORIGEN_ETA_DECLARADA: _a_fecha(eta_declarada),
    }

    origen: str | None = None
    base: dt.date | None = None
    for candidato in PRECEDENCIA:
        if candidatas[candidato] is not None:
            origen, base = candidato, candidatas[candidato]
            break

    if base is None:
        return Proyeccion(
            fecha=None,
            origen=None,
            base=None,
            lead_time_dias=lead_time_dias,
            ajuste_manual_dias=ajuste_manual_dias,
            motivo=(
                "el pedido no tiene ATA confirmada ni inferida, ni ETA de la fuente "
                "de rastreo, ni estimada, ni declarada en el archivo"
            ),
        )

    if lead_time_dias is None:
        # Tercer criterio de `US-09`. No se proyecta con un lead time supuesto:
        # el tramo puerto→planta sigue pendiente con Planeación (04/09/2026).
        return Proyeccion(
            fecha=None,
            origen=origen,
            base=base,
            lead_time_dias=None,
            ajuste_manual_dias=ajuste_manual_dias,
            motivo="el destino no tiene lead time definido",
        )

    fecha = base + dt.timedelta(days=lead_time_dias + ajuste_manual_dias)
    return Proyeccion(
        fecha=fecha,
        origen=origen,
        base=base,
        lead_time_dias=lead_time_dias,
        ajuste_manual_dias=ajuste_manual_dias,
    )


__all__ = [
    "ORIGEN_ATA_CONFIRMADA",
    "ORIGEN_ATA_INFERIDA",
    "ORIGEN_ETA_DECLARADA",
    "ORIGEN_ETA_ESTIMADA",
    "ORIGEN_ETA_FUENTE",
    "PRECEDENCIA",
    "SIN_FECHA_BASE",
    "SIN_LEAD_TIME",
    "Proyeccion",
    "calcular",
]
