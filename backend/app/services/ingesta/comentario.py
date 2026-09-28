"""La referencia de embarque escrita a mano en «Comentario comprador» — `US-52`.

El contrato de `TASK-30` pidió columnas de referencia y WK38 las trajo vacías:
las pocas referencias que Logística tiene las escribe en el comentario, a mano
y mezcladas con otras cosas. Medido en el archivo del 28/09/2026:

| Comentario | Lo que es |
|---|---|
| `ETA CR 03 OCT _ BL COSU6508789000` | BL de COSCO |
| `… / AWB 02025244995 / ETA 11SEP` | Guía madre (MAWB) de Lufthansa Cargo |
| `AWB NO: ZIVHYD017 / ETA CR 8 SEP` | Guía **hija** (HAWB): dice «AWB» pero no tiene forma de guía madre |
| `Pendiente BL y ETA SEP 25` | Nada todavía: menciona el BL pero no trae número |
| `ETA 30 SEP / APROBAR GUIA` | Nada todavía |

La regla que separa lo útil del ruido: **una referencia tiene al menos un
dígito**. «Pendiente BL y…» nombra el documento, pero «Y» no es un número.

Lo que esto **no** hace es validar: clasifica por forma y entrega el par tipo /
número. El dígito verificador y la decisión de si se puede rastrear siguen
siendo de `services.referencia`, igual que para una referencia de columna.
"""

from __future__ import annotations

import re
from typing import Final

#: Un token de referencia: letras, dígitos y guiones, de 4 a 25 caracteres (lo
#: que admite el campo de TICA). Se exige al menos un dígito aparte.
_TOKEN: Final = r"([A-Z0-9][A-Z0-9-]{3,24})"

#: «NO:», «N°», «NRO.», «#»: el rótulo que algunos escriben entre el tipo y el
#: número. Opcional, y sin consumir el número.
_ROTULO: Final = r"(?:\s*(?:NO|N°|NRO|NUM)\.?)?\s*[:#]?\s*"

_BL: Final = re.compile(r"\b(?:B/L|BL)" + _ROTULO + _TOKEN)
_BOOKING: Final = re.compile(r"\bBOOKING" + _ROTULO + _TOKEN)
_HAWB: Final = re.compile(r"\bHAWB" + _ROTULO + _TOKEN)
_AWB: Final = re.compile(r"\b(?:MAWB|AWB|GU[IÍ]A)" + _ROTULO + _TOKEN)
#: ISO 6346: tres letras de propietario, la categoría (U, J o Z) y siete dígitos.
_CONTENEDOR: Final = re.compile(r"\b([A-Z]{3}[UJZ]\d{7})\b")
#: Guía madre: prefijo de aerolínea de tres dígitos y ocho de serie.
_FORMA_MAWB: Final = re.compile(r"^\d{3}-?\d{8}$")


def _con_digito(token: str) -> bool:
    return any(caracter.isdigit() for caracter in token)


def referencia_en_comentario(texto: str | None) -> tuple[str, str] | None:
    """El par `(tipo, número)` que el comentario nombra, o `None`.

    El orden de búsqueda es el de más a menos útil: un **BL** ampara todos los
    contenedores del embarque y cuesta un solo crédito, así que gana a un
    número de contenedor suelto en el mismo comentario.
    """
    if not texto:
        return None
    limpio = texto.upper()

    for patron, tipo in ((_BL, "BL"), (_BOOKING, "BOOKING"), (_HAWB, "HAWB")):
        for hallado in patron.finditer(limpio):
            if _con_digito(hallado.group(1)):
                return tipo, hallado.group(1)

    for hallado in _AWB.finditer(limpio):
        numero = hallado.group(1)
        if not _con_digito(numero):
            continue
        # «AWB» se escribe para las dos guías. Solo la madre tiene la forma de
        # once dígitos; lo demás es la guía hija del agente de carga.
        return ("MAWB" if _FORMA_MAWB.match(numero) else "HAWB"), numero

    contenedor = _CONTENEDOR.search(limpio)
    if contenedor:
        return "CONTENEDOR", contenedor.group(1)
    return None


__all__ = ["referencia_en_comentario"]
