"""Informe de validación de una carga — `US-32`, sexto criterio.

*«Dada la carga, cuando termina, entonces queda un informe de validación con
cada rechazo y su clave de origen»*.

**Por qué hace falta un módulo y no bastaba con lo que ya había.** Los rechazos
de una carga nacen en tres sitios distintos, con claves distintas, y hasta ahora
nadie los juntaba:

| Origen | Qué rechaza | Con qué clave |
|---|---|---|
| `ztracking.FuenteZTracking.ilegibles` | Filas que no llegaron a ser una línea | `hoja!fila` |
| `carga.ResultadoCarga.rechazadas` | Líneas que no se pudieron persistir | `OC-posición` |
| `carga.ResultadoCarga.referencias_invalidas` | Líneas que entraron con una referencia inservible | `OC-posición` |

Las claves son distintas **porque los problemas lo son**. Una fila sin orden de
compra no tiene `OC-posición` que mostrar —esa es justamente su falla—, así que
la única forma de que alguien la encuentre es decirle la hoja y el número de
fila. Forzar una sola clave perdería la mitad de la información útil.

Quien recibe este informe no es un programador: es quien corrige el archivo. Por
eso cada entrada lleva **dónde está el problema**, **qué pasa** y **qué le tocó
al pedido**, y por eso el informe agrupa por motivo: 290 líneas sin vía de
transporte son *un* problema del archivo repetido 290 veces, no 290 problemas.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.services.ingesta.carga import ResultadoCarga
from app.services.ingesta.ztracking import LineaIlegible

#: Qué le pasó al pedido, que es lo que decide si alguien tiene que actuar.
NO_ENTRO = "no_entro"
ENTRO_SIN_RASTREO = "entro_sin_rastreo"


@dataclass(frozen=True, slots=True)
class Incidencia:
    """Un problema de la carga, con dónde encontrarlo."""

    #: Dónde está en el origen: `PRODUCCION!57` o `4500016171-90`.
    clave: str
    #: De qué tipo es, para agrupar: `sin_via_transporte`, `sin_fecha_de_entrega`…
    motivo: str
    #: En castellano, para quien corrige el archivo.
    detalle: str
    #: `NO_ENTRO` o `ENTRO_SIN_RASTREO`.
    consecuencia: str

    def __str__(self) -> str:
        return f"{self.clave}: {self.detalle}"


@dataclass(slots=True)
class InformeValidacion:
    """Todo lo que no salió limpio en una carga, en un solo sitio."""

    fuente: str
    recibidas: int = 0
    insertadas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    ausentes: int = 0
    incidencias: list[Incidencia] = field(default_factory=list)

    @property
    def total_incidencias(self) -> int:
        return len(self.incidencias)

    @property
    def no_entraron(self) -> int:
        return sum(1 for i in self.incidencias if i.consecuencia == NO_ENTRO)

    @property
    def entraron_sin_rastreo(self) -> int:
        return sum(1 for i in self.incidencias if i.consecuencia == ENTRO_SIN_RASTREO)

    def por_motivo(self) -> dict[str, int]:
        """Cuántas veces se repite cada problema, de mayor a menor.

        Es la vista accionable: dice qué arreglar primero en el archivo.
        """
        return dict(Counter(i.motivo for i in self.incidencias).most_common())

    def incidencias_de(self, motivo: str) -> list[Incidencia]:
        return [i for i in self.incidencias if i.motivo == motivo]

    def como_dict(self) -> dict[str, Any]:
        """Para serializar el informe cuando lo consuma la API (`US-16`)."""
        return {
            "fuente": self.fuente,
            "recibidas": self.recibidas,
            "insertadas": self.insertadas,
            "actualizadas": self.actualizadas,
            "sin_cambios": self.sin_cambios,
            "ausentes": self.ausentes,
            "incidencias": [
                {
                    "clave": i.clave,
                    "motivo": i.motivo,
                    "detalle": i.detalle,
                    "consecuencia": i.consecuencia,
                }
                for i in self.incidencias
            ],
            "por_motivo": self.por_motivo(),
        }

    def como_texto(self, ejemplos: int = 10) -> str:
        """El informe que alguien lee, agrupado por motivo.

        Se limita a unos pocos ejemplos por motivo a propósito: contra el
        archivo real hay 290 líneas con el mismo problema, y volcarlas todas
        esconde los otros motivos en vez de mostrarlos. El recuento es lo
        accionable; los ejemplos solo sirven para ir a buscar la línea.
        """
        lineas = [
            f"Informe de validación — fuente {self.fuente}",
            (
                f"  {self.recibidas} recibidas · {self.insertadas} insertadas · "
                f"{self.actualizadas} actualizadas · {self.sin_cambios} sin cambios · "
                f"{self.ausentes} ausentes"
            ),
        ]
        if not self.incidencias:
            lineas.append("  Sin incidencias.")
            return "\n".join(lineas)

        lineas.append(
            f"  {self.total_incidencias} incidencias: "
            f"{self.no_entraron} no entraron, "
            f"{self.entraron_sin_rastreo} entraron sin rastreo"
        )
        for motivo, cuantas in self.por_motivo().items():
            lineas.append(f"\n  {motivo} — {cuantas}")
            muestra = self.incidencias_de(motivo)
            for incidencia in muestra[:ejemplos]:
                lineas.append(f"    · {incidencia}")
            if cuantas > ejemplos:
                lineas.append(f"    … y {cuantas - ejemplos} más")
        return "\n".join(lineas)


def construir_informe(
    fuente: str,
    resultado: ResultadoCarga,
    ilegibles: list[LineaIlegible] | None = None,
) -> InformeValidacion:
    """Junta los tres orígenes de rechazo en un informe único.

    `ilegibles` sale de la fuente cuando es un archivo; la semilla no tiene
    ninguna, y por eso el parámetro es opcional en vez de obligatorio.
    """
    incidencias: list[Incidencia] = []

    for fila in ilegibles or []:
        incidencias.append(
            Incidencia(
                clave=f"{fila.hoja}!{fila.fila}",
                motivo=fila.motivo,
                detalle=fila.detalle,
                consecuencia=NO_ENTRO,
            )
        )

    for linea in resultado.rechazadas:
        incidencias.append(
            Incidencia(
                clave=f"{linea.oc_numero}-{linea.posicion_oc}",
                motivo=linea.motivo,
                detalle=linea.detalle,
                consecuencia=NO_ENTRO,
            )
        )

    for linea in resultado.referencias_invalidas:
        incidencias.append(
            Incidencia(
                clave=f"{linea.oc_numero}-{linea.posicion_oc}",
                motivo=linea.motivo,
                detalle=linea.detalle,
                consecuencia=ENTRO_SIN_RASTREO,
            )
        )

    return InformeValidacion(
        fuente=fuente,
        # Las ilegibles no están en `recibidas`: la fuente nunca las entregó.
        # Sumarlas es lo que hace que el informe cuadre con el archivo y no con
        # lo que el lector consiguió leer.
        recibidas=resultado.leidas + len(ilegibles or []),
        insertadas=resultado.cargados,
        actualizadas=resultado.actualizados,
        sin_cambios=resultado.sin_cambios,
        ausentes=len(resultado.ausentes),
        incidencias=incidencias,
    )


__all__ = [
    "ENTRO_SIN_RASTREO",
    "NO_ENTRO",
    "Incidencia",
    "InformeValidacion",
    "construir_informe",
]
