"""Validación de la referencia de embarque y su capacidad de rastreo — RF-03.

`US-01`, reformulada el 04/09/2026: la referencia **llega en el archivo** de
Logística, conforme al contrato de `TASK-30`, y la asociación manual queda como
excepción para las líneas que no la traen.

Dos preguntas distintas que conviene no mezclar:

1. **¿La referencia está bien escrita?** Es una cuestión de formato y se
   responde sola, sin red. Un contenedor son cuatro letras y siete dígitos; un
   MAWB, once dígitos con prefijo de aerolínea.
2. **¿Alguien puede seguirla hoy?** Depende de qué fuentes estén contratadas y
   conectadas, y eso cambia con el tiempo.

El tercer criterio de `US-01` exige justamente distinguirlas: un identificador
de un tipo que ninguna API sigue **se acepta igual**, y el sistema advierte que
ese pedido no será rastreable automáticamente. Guardar el dato siempre vale la
pena: mañana puede haber fuente, y mientras tanto le sirve a quien lo consulta a
mano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.models.enums import TIPOS_TRACKING

#: Formato esperado por tipo. `None` = no hay patrón fijo que validar.
_PATRONES: Final[dict[str, re.Pattern[str] | None]] = {
    # Identidad de la nave, según los estándares de la OMI y la UIT.
    "MMSI": re.compile(r"^\d{9}$"),
    "IMO": re.compile(r"^(IMO)?\d{7}$"),
    # ISO 6346: cuatro letras de propietario más siete dígitos.
    "CONTENEDOR": re.compile(r"^[A-Z]{4}\d{7}$"),
    # Guía aérea madre: prefijo de tres dígitos de la aerolínea más ocho.
    "MAWB": re.compile(r"^\d{3}-?\d{8}$"),
    # El resto no tiene formato universal: cada naviera y aerolínea usa el suyo.
    "BL": None,
    "BOOKING": None,
    "BUQUE": None,
    "VUELO": None,
}

#: Qué fuente seguiría cada tipo de referencia.
_FUENTE_POR_TIPO: Final[dict[str, str]] = {
    "CONTENEDOR": "vizion",
    "BL": "vizion",
    "BOOKING": "vizion",
    "MAWB": "portcast",
    "MMSI": "aisstream",
    "IMO": "aisstream",
    "VUELO": "opensky",
    "BUQUE": "ninguna",
}

#: Fuentes efectivamente conectadas hoy. Vizion y Portcast están **aprobadas
#: pero no contratadas**: el spike `TASK-28` sigue a la espera de credenciales.
#: Mientras eso no cambie, sus referencias se guardan pero no se siguen.
_FUENTES_DISPONIBLES: Final[frozenset[str]] = frozenset({"aisstream", "opensky"})


@dataclass(frozen=True, slots=True)
class ResultadoReferencia:
    """Veredicto sobre una referencia de embarque."""

    valida: bool
    tipo: str | None
    numero: str | None
    rastreable: bool
    motivo: str

    def __bool__(self) -> bool:
        return self.valida


def normalizar_referencia(numero: str | None) -> str | None:
    """Mayúsculas y sin espacios ni separadores sobrantes."""
    if numero is None:
        return None
    limpio = re.sub(r"\s+", "", str(numero)).upper()
    return limpio or None


def validar_referencia(tipo: str | None, numero: str | None) -> ResultadoReferencia:
    """Valida el par tipo/número y dice si hoy se puede seguir.

    Una referencia **válida pero no rastreable** no es un error: se guarda, y el
    motivo explica por qué el pedido seguirá en `SIN_TRACKING` (RN-02).
    """
    tipo_norm = (tipo or "").strip().upper() or None
    num_norm = normalizar_referencia(numero)

    if tipo_norm is None or num_norm is None:
        return ResultadoReferencia(
            valida=False,
            tipo=tipo_norm,
            numero=num_norm,
            rastreable=False,
            motivo="Falta el tipo o el número de referencia.",
        )

    if tipo_norm not in TIPOS_TRACKING:
        return ResultadoReferencia(
            valida=False,
            tipo=tipo_norm,
            numero=num_norm,
            rastreable=False,
            motivo=(
                f"Tipo de referencia desconocido: {tipo_norm!r}. "
                f"Admitidos: {', '.join(sorted(TIPOS_TRACKING))}."
            ),
        )

    patron = _PATRONES.get(tipo_norm)
    if patron is not None and not patron.match(num_norm):
        pista = ""
        if tipo_norm == "MAWB":
            # El error más frecuente en la vía aérea, según el contrato de
            # TASK-30: el agente de carga entrega la guía hija.
            pista = " Puede ser un HAWB del agente de carga; hace falta el MAWB."
        return ResultadoReferencia(
            valida=False,
            tipo=tipo_norm,
            numero=num_norm,
            rastreable=False,
            motivo=f"{num_norm!r} no tiene el formato de un {tipo_norm}.{pista}",
        )

    fuente = _FUENTE_POR_TIPO.get(tipo_norm, "ninguna")
    if fuente == "ninguna":
        return ResultadoReferencia(
            valida=True,
            tipo=tipo_norm,
            numero=num_norm,
            rastreable=False,
            motivo=(
                f"Se acepta, pero ninguna fuente sigue un {tipo_norm}: el pedido "
                "no será rastreable automáticamente hasta que se resuelva a un "
                "MMSI o un IMO."
            ),
        )

    if fuente not in _FUENTES_DISPONIBLES:
        return ResultadoReferencia(
            valida=True,
            tipo=tipo_norm,
            numero=num_norm,
            rastreable=False,
            motivo=(
                f"Se acepta, pero la fuente que la sigue ({fuente}) todavía no "
                "está contratada. El pedido queda sin rastreo automático hasta "
                "que cierre TASK-28."
            ),
        )

    return ResultadoReferencia(
        valida=True,
        tipo=tipo_norm,
        numero=num_norm,
        rastreable=True,
        motivo=f"Rastreable automáticamente vía {fuente}.",
    )


def fuente_de(tipo: str | None) -> str | None:
    """Fuente que seguiría ese tipo de referencia, con independencia de si está
    contratada. Sirve para explicar en la interfaz qué falta para rastrear."""
    if not tipo:
        return None
    return _FUENTE_POR_TIPO.get(tipo.strip().upper())


__all__ = [
    "ResultadoReferencia",
    "fuente_de",
    "normalizar_referencia",
    "validar_referencia",
]
