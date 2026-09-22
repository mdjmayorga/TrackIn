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
#:
#: Vizion y Portcast salieron el 14/09/2026: ninguno de los dos proveedores
#: respondió a la solicitud. `TASK-28` cerró con **ShipsGo para las dos vías**,
#: marítima (`/ocean/shipments`) y aérea (`/air/shipments`).
_FUENTE_POR_TIPO: Final[dict[str, str]] = {
    "CONTENEDOR": "shipsgo",
    "BL": "shipsgo",
    "BOOKING": "shipsgo",
    "MAWB": "shipsgo",
    "MMSI": "aisstream",
    "IMO": "aisstream",
    "VUELO": "opensky",
    "BUQUE": "ninguna",
}

#: Fuentes efectivamente conectadas hoy.
#:
#: ShipsGo está **validada pero sin créditos**: los dos trials de 3 altas se
#: agotaron el 14/09 y la compra se difiere al arranque de producción, porque
#: los créditos vencen un año después de comprarse. Hasta que se compren, sus
#: referencias se guardan y se validan, pero no se siguen — que es exactamente
#: la distinción que documenta el encabezado de este módulo.
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


#: Valor numérico de cada letra en ISO 6346. La serie salta los múltiplos de 11
#: —no existen valores 11, 22 ni 33—, que es la razón de que `L` valga 23 y no
#: 22. Copiar la tabla mal es el error clásico de esta implementación.
_VALOR_LETRA_ISO6346: Final[dict[str, int]] = dict(
    zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [v for v in range(10, 39) if v % 11 != 0],
        strict=True,
    )
)


def digito_control_contenedor(numero: str) -> int | None:
    """Dígito verificador de un contenedor ISO 6346, o `None` si no aplica.

    Cada uno de los diez primeros caracteres se multiplica por `2**posición`, se
    suman, y el resto de dividir entre 11 es el dígito; un resto de 10 se escribe
    como `0`.

    **Por qué importa más de lo que parece.** El spike `TASK-28` midió que
    ShipsGo **acepta y cobra cualquier cosa**: un `POST` con el contenedor
    inventado `XXXX0000000` devolvió `200 SUCCESS` y creó el embarque. A 2 USD
    el crédito, una referencia mal transcrita cuesta dinero y luego devuelve
    vacío, indistinguible de una sin cobertura. Esta comprobación es local,
    gratuita e instantánea, y es lo único que separa una errata de una factura.
    """
    if len(numero) != 11:
        return None
    cuerpo, _ = numero[:10], numero[10]
    total = 0
    for posicion, caracter in enumerate(cuerpo):
        if caracter.isdigit():
            valor = int(caracter)
        else:
            valor = _VALOR_LETRA_ISO6346.get(caracter, -1)
            if valor < 0:
                return None
        total += valor * (2**posicion)
    return (total % 11) % 10


def digito_control_mawb(numero: str) -> int | None:
    """Dígito verificador de una guía aérea madre, o `None` si no aplica.

    El MAWB son tres dígitos de prefijo de aerolínea más ocho de serie, y el
    último de la serie es el resto de dividir los siete anteriores entre 7.
    Misma economía que el contenedor: verificarlo acá cuesta cero y evita gastar
    un crédito de ShipsGo Air en un número mal copiado.
    """
    solo_digitos = numero.replace("-", "")
    if len(solo_digitos) != 11 or not solo_digitos.isdigit():
        return None
    return int(solo_digitos[3:10]) % 7


def _verificar_digito(tipo: str, numero: str) -> tuple[int | None, int | None]:
    """El dígito que corresponde y el que trae, para los tipos que lo llevan.

    Devuelve `(None, None)` para los tipos sin dígito verificador —`BL`,
    `BOOKING`, `MMSI`, `IMO`, `VUELO`, `BUQUE`—, donde no hay nada que
    comprobar sin salir a la red.
    """
    if tipo == "CONTENEDOR":
        return digito_control_contenedor(numero), int(numero[10])
    if tipo == "MAWB":
        solo_digitos = numero.replace("-", "")
        return digito_control_mawb(numero), int(solo_digitos[10])
    return None, None


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

    # El formato sí cuadra: queda comprobar el dígito verificador, que es lo que
    # distingue un número bien transcrito de uno plausible pero equivocado. Un
    # dígito malo **no aborta el lote** (RN-17): la línea entra, la referencia
    # queda registrada y el pedido se queda en `SIN_TRACKING` hasta que alguien
    # la corrija. Lo que no pasa es que se gaste un crédito en ella.
    esperado, declarado = _verificar_digito(tipo_norm, num_norm)
    if esperado is not None and declarado is not None and esperado != declarado:
        return ResultadoReferencia(
            valida=False,
            tipo=tipo_norm,
            numero=num_norm,
            rastreable=False,
            motivo=(
                f"{num_norm!r} tiene el formato de un {tipo_norm} pero su dígito "
                f"verificador no cuadra: declara {declarado} y le corresponde "
                f"{esperado}. Probablemente esté mal transcrito."
            ),
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
                f"Se acepta, pero la fuente que la sigue ({fuente}) no tiene "
                "créditos disponibles. El pedido queda sin rastreo automático "
                "hasta que se compren."
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
