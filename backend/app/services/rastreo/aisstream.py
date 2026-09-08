"""Lectura de los mensajes de AISStream — RF-06 (`US-02`).

Módulo **puro**: traduce el JSON crudo de AISStream a los objetos que el resto
del sistema entiende, y no toca ni la red ni la base. Todo lo que hay acá está
probado contra los **161 mensajes reales** de
`scripts/spikes/aisstream/output/02_caribbean_raw_personal.jsonl`, que es la
mitigación documentada del riesgo **R1**: la cuenta no entrega datos desde el
19/08/2026 y no hay captura nueva posible.

Cinco cosas que el dataset real obligó a corregir respecto del criterio
original, y conviene no perderlas porque ninguna es evidente leyendo la
documentación de AISStream:

1. **Los tipos con posición son dos, no uno.** `PositionReport` (76 mensajes)
   y `StandardClassBPositionReport` (39). Los estáticos también son dos:
   `ShipStaticData` (19) y `StaticDataReport` (20). El criterio nombraba solo
   el primero de cada par y dejaba fuera 59 de 161 mensajes.
2. **Los mensajes estáticos no traen posición en el cuerpo** —40 de 161—, solo
   en `MetaData`. Leerla del cuerpo la pierde en uno de cada cuatro mensajes.
3. **Los centinelas de AIS no son datos.** `TrueHeading = 511` aparece en 44 de
   115 posiciones y `Cog = 360` en 11. El segundo además **viola el `CHECK`**
   de `historial_tracking` (`rumbo < 360`): guardarlo no daría un dato falso,
   daría un `IntegrityError`.
4. **`time_utc` viene en formato Go, no ISO**: `2026-08-18 20:18:15.331999764
   +0000 UTC`. `datetime.fromisoformat` lanza `ValueError`, y la fracción trae
   9, 8 o 6 dígitos donde Python admite 6 como máximo.
5. **La ETA de AIS no lleva año** y casi nunca se declara: 11 de 19
   `ShipStaticData` la traen en ceros. Ver `resolver_eta`.

**Class B no se filtra por tipo.** Es equipo de embarcación menor, así que un
buque de carga nunca lo emite, pero descartarlo por el tipo sería filtrar por un
supuesto. Lo que rige es la regla que ya existe: se persiste lo que corresponde
a un `ElementoRastreado` activo, y Class B no coincide por sí solo.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Any, Final

logger = logging.getLogger(__name__)

#: Endpoint de la suscripción. Documentado en `docs/api-references.md`.
URL_STREAM: Final[str] = "wss://stream.aisstream.io/v0/stream"

#: Tipos que traen una posición navegable. Class A y Class B.
TIPOS_CON_POSICION: Final[frozenset[str]] = frozenset(
    {"PositionReport", "StandardClassBPositionReport"}
)

#: Tipos que traen identidad del buque. `StaticDataReport` es el de Class B y
#: trae bastante menos: nombre y poco más, sin IMO ni destino ni ETA.
TIPOS_ESTATICOS: Final[frozenset[str]] = frozenset({"ShipStaticData", "StaticDataReport"})

# --- Centinelas de AIS -----------------------------------------------------
# El estándar reserva un valor de cada campo para «no disponible». AISStream los
# entrega ya escalados a unidades reales, así que hay que comparar contra el
# valor escalado y no contra el crudo del estándar.

#: Rumbo verdadero no disponible. Va en grados enteros, sin escalar.
CENTINELA_RUMBO: Final[int] = 511
#: Curso sobre el fondo no disponible: 3600 décimas de grado ⇒ 360.0°.
CENTINELA_CURSO: Final[float] = 360.0
#: Velocidad no disponible: 1023 décimas de nudo ⇒ 102.3 nudos.
CENTINELA_VELOCIDAD: Final[float] = 102.3

#: Estado de navegación de AIS (mensaje 1/2/3, campo `NavigationalStatus`).
#: Se guarda el texto y no el número porque `historial_tracking.estado_api` es
#: la columna que se lee al auditar, y un `5` no le dice nada a nadie.
ESTADOS_NAVEGACION: Final[dict[int, str]] = {
    0: "EN_NAVEGACION_A_MOTOR",
    1: "FONDEADO",
    2: "SIN_GOBIERNO",
    3: "MANIOBRA_RESTRINGIDA",
    4: "RESTRINGIDO_POR_CALADO",
    5: "AMARRADO",
    6: "VARADO",
    7: "PESCANDO",
    8: "EN_NAVEGACION_A_VELA",
    9: "RESERVADO_HC",
    10: "RESERVADO_WIG",
    11: "REMOLQUE_A_POPA",
    12: "REMOLQUE_A_PROA",
    13: "RESERVADO",
    14: "AIS_SART",
    15: "NO_DEFINIDO",
}

#: `2026-08-18 20:18:15.331999764 +0000 UTC` — formato de Go, no ISO 8601.
_PATRON_INSTANTE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<fecha>\d{4}-\d{2}-\d{2})[ T]"
    r"(?P<hora>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraccion>\d+))?"
    r"(?:\s*(?P<offset>[+-]\d{2}:?\d{2}|Z))?"
    r"(?:\s+[A-Za-z]+)?$"
)


class MensajeIlegible(ValueError):
    """El mensaje no tiene la forma que AISStream documenta.

    Es un error de la fuente, no del sistema: se registra y se descarta el
    mensaje. Un frame corrupto no puede tumbar la suscripción entera.
    """


@dataclass(frozen=True, slots=True)
class PosicionAIS:
    """Una lectura de posición, ya normalizada y lista para `US-04`."""

    mmsi: str
    instante: dt.datetime
    latitud: float
    longitud: float
    #: `None` cuando la fuente mandó el centinela. Nunca el centinela.
    velocidad_nudos: float | None
    rumbo_grados: float | None
    estado_navegacion: str | None
    nombre: str | None
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EstaticoAIS:
    """Identidad del buque. **No lleva posición**: no debe tocar el trayecto."""

    mmsi: str
    instante: dt.datetime
    imo: str | None
    nombre: str | None
    destino: str | None
    #: `None` si el buque no la declaró, que es el caso de 11 de cada 19.
    eta: dt.datetime | None
    payload: dict[str, Any]


def parsear_instante(bruto: str) -> dt.datetime:
    """Convierte el `time_utc` de AISStream a un `datetime` con zona horaria.

    No sirve `fromisoformat`: el formato es el de Go —espacio en vez de `T`,
    sufijo `UTC` textual— y la fracción trae hasta 9 dígitos, tres más de los
    que admite `datetime`. La fracción se **trunca**, no se redondea: son
    nanosegundos de una marca de recepción, y redondear hacia arriba podría
    empujar la lectura al segundo siguiente sin ganar nada.
    """
    coincidencia = _PATRON_INSTANTE.match(bruto.strip())
    if coincidencia is None:
        raise MensajeIlegible(f"Instante {bruto!r} sin el formato de AISStream.")

    partes = coincidencia.groupdict()
    microsegundos = (partes["fraccion"] or "").ljust(6, "0")[:6]

    offset = partes["offset"]
    if offset in (None, "Z"):
        # AISStream siempre reporta UTC; si algún día dejara de hacerlo, el
        # grupo `offset` lo captura y esta rama no se usa.
        zona = dt.UTC
    else:
        signo = -1 if offset[0] == "-" else 1
        digitos = offset[1:].replace(":", "")
        zona = dt.timezone(signo * dt.timedelta(hours=int(digitos[:2]), minutes=int(digitos[2:])))

    return dt.datetime.strptime(
        f"{partes['fecha']} {partes['hora']}.{microsegundos}", "%Y-%m-%d %H:%M:%S.%f"
    ).replace(tzinfo=zona)


def _texto(bruto: Any) -> str | None:
    """Limpia un campo de texto de AIS.

    Los nombres vienen rellenos a ancho fijo —`'MARISOL             '`— y el
    destino también. Sin recortar, el mismo buque entra dos veces según por qué
    tipo de mensaje llegó.
    """
    if not isinstance(bruto, str):
        return None
    limpio = bruto.strip().strip("@").strip()
    return limpio or None


def _sin_centinela(valor: Any, centinela: float, *, maximo: float | None = None) -> float | None:
    """Devuelve el valor, o `None` si es el centinela o está fuera de rango."""
    if not isinstance(valor, int | float) or isinstance(valor, bool):
        return None
    numero = float(valor)
    if numero >= centinela:
        return None
    if numero < 0 or (maximo is not None and numero > maximo):
        return None
    return numero


def resolver_eta(eta: dict[str, Any] | None, *, referencia: dt.datetime) -> dt.datetime | None:
    """Resuelve la ETA de AIS, que **no lleva año**, contra un instante conocido.

    El estándar solo transmite mes, día, hora y minuto, y usa el cero como «no
    declarado». Once de los diecinueve `ShipStaticData` del dataset la traen
    entera en ceros, así que la respuesta más común es `None`.

    Cuando sí viene, el año se elige como el que deja la ETA **más cerca** del
    mensaje, probando el anterior, el mismo y el siguiente. Suponer «la próxima
    ocurrencia» sería peor: el dataset trae una ETA del 18/08 a las 14:20 en un
    mensaje del 18/08 a las 20:18 —ya vencida por seis horas—, y esa regla la
    habría empujado un año entero al futuro.

    Aun así, es un dato informativo: el Plan A del 04/09 dejó la ETA marítima en
    manos de Vizion, y el spike ya había medido que solo el 12 % de los buques
    la declara.
    """
    if not isinstance(eta, dict):
        return None

    mes, dia = eta.get("Month"), eta.get("Day")
    hora, minuto = eta.get("Hour"), eta.get("Minute")

    # El cero es «no disponible» en mes y día; 24 y 60 lo son en hora y minuto.
    if not (isinstance(mes, int) and isinstance(dia, int) and 1 <= mes <= 12 and 1 <= dia <= 31):
        return None
    if not (isinstance(hora, int) and isinstance(minuto, int)):
        return None
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        return None

    candidatos: list[dt.datetime] = []
    for anio in (referencia.year - 1, referencia.year, referencia.year + 1):
        try:
            candidatos.append(
                dt.datetime(anio, mes, dia, hora, minuto, tzinfo=referencia.tzinfo or dt.UTC)
            )
        except ValueError:
            # 29 de febrero en un año no bisiesto. Los otros dos candidatos
            # siguen sirviendo.
            continue

    if not candidatos:
        return None
    return min(candidatos, key=lambda momento: abs(momento - referencia))


def _coordenadas(cuerpo: dict[str, Any], meta: dict[str, Any]) -> tuple[float, float] | None:
    """Latitud y longitud, del cuerpo si están y si no de `MetaData`.

    Los mensajes estáticos —40 de los 161 del dataset— no las traen en el
    cuerpo. `MetaData` sí las lleva siempre, porque es lo que el receptor sabía
    del buque al momento de recibir el mensaje.
    """
    for origen, clave_lat, clave_lon in (
        (cuerpo, "Latitude", "Longitude"),
        (meta, "latitude", "longitude"),
    ):
        latitud, longitud = origen.get(clave_lat), origen.get(clave_lon)
        if (
            isinstance(latitud, int | float)
            and isinstance(longitud, int | float)
            and -90 <= latitud <= 90
            and -180 <= longitud <= 180
        ):
            return float(latitud), float(longitud)
    return None


def _mmsi(meta: dict[str, Any], cuerpo: dict[str, Any]) -> str | None:
    """MMSI como texto, que es como lo guarda `elementos_rastreados`.

    `MetaData.MMSI` y `Message.*.UserID` son el mismo número. Se prefiere el
    primero porque está en todos los tipos, incluido `UnknownMessage`.
    """
    for bruto in (meta.get("MMSI"), meta.get("MMSI_String"), cuerpo.get("UserID")):
        if isinstance(bruto, int) and not isinstance(bruto, bool):
            return str(bruto)
        if isinstance(bruto, str) and bruto.strip().isdigit():
            return bruto.strip()
    return None


def _nombre_estatico(tipo: str, cuerpo: dict[str, Any], meta: dict[str, Any]) -> str | None:
    """Nombre del buque según el tipo de mensaje estático.

    `ShipStaticData` lo trae en `Name`. `StaticDataReport` lo parte en dos: la
    parte A lleva el nombre y la B las dimensiones, y en el dataset **la parte B
    siempre viene con `Valid: false`**, así que solo se lee la A.
    """
    if tipo == "ShipStaticData":
        return _texto(cuerpo.get("Name")) or _texto(meta.get("ShipName"))

    parte_a = cuerpo.get("ReportA")
    if isinstance(parte_a, dict) and parte_a.get("Valid"):
        nombre = _texto(parte_a.get("Name"))
        if nombre:
            return nombre
    return _texto(meta.get("ShipName"))


def parsear(mensaje: dict[str, Any]) -> PosicionAIS | EstaticoAIS | None:
    """Traduce un mensaje crudo, o devuelve `None` si no interesa.

    `None` **no es un error**: los mensajes de estación base, de ayudas a la
    navegación y los que AISStream no supo decodificar son tráfico legítimo del
    stream que a TrackIn no le sirve. Llegan 7 de cada 161.
    """
    tipo = mensaje.get("MessageType")
    if not isinstance(tipo, str):
        raise MensajeIlegible("El mensaje no declara `MessageType`.")
    if tipo not in TIPOS_CON_POSICION and tipo not in TIPOS_ESTATICOS:
        return None

    contenedor = mensaje.get("Message")
    meta = mensaje.get("MetaData")
    if not isinstance(contenedor, dict) or not isinstance(meta, dict):
        raise MensajeIlegible(f"Mensaje {tipo} sin `Message` o sin `MetaData`.")

    cuerpo = contenedor.get(tipo)
    if not isinstance(cuerpo, dict):
        raise MensajeIlegible(f"Mensaje {tipo} sin cuerpo del tipo declarado.")

    # AISStream marca con `Valid: false` lo que decodificó a medias. Guardarlo
    # sería meter ruido en una bitácora que existe para auditar.
    if cuerpo.get("Valid") is False:
        logger.debug("AIS: mensaje %s descartado por `Valid: false`.", tipo)
        return None

    mmsi = _mmsi(meta, cuerpo)
    if mmsi is None:
        raise MensajeIlegible(f"Mensaje {tipo} sin MMSI identificable.")

    instante_bruto = meta.get("time_utc")
    if not isinstance(instante_bruto, str):
        raise MensajeIlegible(f"Mensaje {tipo} sin `MetaData.time_utc`.")
    instante = parsear_instante(instante_bruto)

    if tipo in TIPOS_ESTATICOS:
        return EstaticoAIS(
            mmsi=mmsi,
            instante=instante,
            imo=str(cuerpo["ImoNumber"]) if isinstance(cuerpo.get("ImoNumber"), int) else None,
            nombre=_nombre_estatico(tipo, cuerpo, meta),
            destino=_texto(cuerpo.get("Destination")),
            eta=resolver_eta(cuerpo.get("Eta"), referencia=instante),
            payload=mensaje,
        )

    coordenadas = _coordenadas(cuerpo, meta)
    if coordenadas is None:
        raise MensajeIlegible(f"Mensaje {tipo} sin coordenadas utilizables.")
    latitud, longitud = coordenadas

    # El curso sobre el fondo describe hacia dónde **se mueve** el buque; el
    # rumbo verdadero, hacia dónde apunta. Para dibujar un trayecto sirve el
    # primero, y el segundo queda de respaldo.
    rumbo = _sin_centinela(cuerpo.get("Cog"), CENTINELA_CURSO)
    if rumbo is None:
        rumbo = _sin_centinela(cuerpo.get("TrueHeading"), CENTINELA_RUMBO, maximo=359.0)

    estado = cuerpo.get("NavigationalStatus")

    return PosicionAIS(
        mmsi=mmsi,
        instante=instante,
        latitud=latitud,
        longitud=longitud,
        velocidad_nudos=_sin_centinela(cuerpo.get("Sog"), CENTINELA_VELOCIDAD),
        rumbo_grados=rumbo,
        estado_navegacion=(ESTADOS_NAVEGACION.get(estado) if isinstance(estado, int) else None),
        nombre=_texto(meta.get("ShipName")),
        payload=mensaje,
    )


def suscripcion(
    api_key: str,
    *,
    cajas: list[list[list[float]]],
    mmsis: list[str] | None = None,
) -> dict[str, Any]:
    """Arma el mensaje de suscripción, validándolo antes de mandarlo.

    La validación no es celo: el spike (Fase 5) midió que **una clave inválida y
    una suscripción malformada producen exactamente el mismo cierre**, sin
    código ni motivo. Si la nuestra nunca puede ir malformada, un cierre
    inmediato solo puede ser la credencial, y `clasificar_cierre` puede
    afirmarlo en vez de suponerlo.
    """
    if not api_key or not api_key.strip():
        raise ValueError("AISStream exige una API key no vacía.")
    if not cajas:
        raise ValueError("La suscripción exige al menos un bounding box.")

    for caja in cajas:
        if len(caja) != 2 or any(len(esquina) != 2 for esquina in caja):
            raise ValueError(f"Bounding box {caja!r}: se esperan dos esquinas [lat, lon].")
        for latitud, longitud in caja:
            if not (-90 <= latitud <= 90 and -180 <= longitud <= 180):
                raise ValueError(f"Bounding box {caja!r} fuera de rango.")

    peticion: dict[str, Any] = {"APIKey": api_key.strip(), "BoundingBoxes": cajas}
    if mmsis:
        # Filtrar por MMSI nunca se probó: `TASK-27`, que iba a medirlo, se
        # canceló con el Plan A. Se admite porque el protocolo lo documenta,
        # pero el camino ejercitado es el de los bounding boxes.
        peticion["FiltersShipMMSI"] = [str(m) for m in mmsis]
    return peticion


#: Una sola conexión con todos los bounding boxes, según la recomendación 4 del
#: spike: el plan admite varias, pero una deja menos estado que reconciliar tras
#: una caída.
def clasificar_cierre(*, segundos_conectado: float, umbral_credencial: float = 5.0) -> str:
    """Motivo normalizado del cierre, para `app.services.resiliencia`.

    Se clasifica **por el momento** y no por el código, porque no hay código: el
    servidor cierra sin *close frame*. Lo único que distingue una credencial
    rechazada de un corte de red es que la primera ocurre de inmediato —el spike
    midió 747 ms— y la segunda después de haber estado recibiendo.

    Devuelve un motivo del vocabulario de `resiliencia.MOTIVOS_PERMANENTES`
    cuando corresponde, de modo que la política decide sin saber de WebSockets.
    """
    if segundos_conectado < umbral_credencial:
        return "credencial_invalida"
    return "conexion_perdida"


__all__ = [
    "CENTINELA_CURSO",
    "CENTINELA_RUMBO",
    "CENTINELA_VELOCIDAD",
    "ESTADOS_NAVEGACION",
    "TIPOS_CON_POSICION",
    "TIPOS_ESTATICOS",
    "URL_STREAM",
    "EstaticoAIS",
    "MensajeIlegible",
    "PosicionAIS",
    "clasificar_cierre",
    "parsear",
    "parsear_instante",
    "resolver_eta",
    "suscripcion",
]
