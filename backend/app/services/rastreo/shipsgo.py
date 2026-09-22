"""Interpretación del payload marítimo de ShipsGo — `US-45` / RF-06, RF-20.

Traduce lo que devuelve ShipsGo a los conceptos de TrackIn. **No habla por red**
y no toca la base: recibe los dos diccionarios que entrega el proveedor y
devuelve una lectura. El cliente HTTP vive en `cliente.py` y la persistencia en
`colector_shipsgo.py`.

Cómo se verifica esta historia
-------------------------------

Contra los **payloads reales grabados** por `TASK-28` el 14/09/2026, en
`scripts/spikes/task28/output/`. No quedan créditos —los dos trials de 3 altas
se agotaron y la compra se difiere— así que la verificación en vivo espera. Los
cuatro embarques medidos cubren lo que hay que cubrir:

| Embarque | Qué aporta |
|---|---|
| `MRSU8507472` (Maersk) | Transbordo de 2 naves, **con** posición actual |
| `MRSU8132490` (Maersk) | Transbordo de **3** naves |
| `TGBU4872990` (COSCO) | Destino Caldera y **sin** posición: `current: null` |
| `020-50685434` (Lufthansa) | La vía aérea, que comparte la **forma** pero no el mapeo |

**El aéreo se lee a medias a propósito.** Este módulo extrae sus diez
movimientos sin problema —la forma del payload es la misma—, pero sus códigos
son **IATA CIMP** (`RCS`, `DEP`, `MAN`, `ARR`, `RCF`, `DLV`) y su ruta usa otras
claves, así que hoy la etapa sale `SIN_TRACKING`. Mapearlos es trabajo de
`US-46`, que reutilizará el resto de este módulo en vez de duplicarlo.

Los datos viven en dos endpoints
---------------------------------

Y es un hallazgo que costó encontrar: el `geojson` **no estaba documentado** en
la guía del proveedor. Sin él la conclusión habría sido que ShipsGo no entrega
posición, que es falso.

| Endpoint | Qué aporta |
|---|---|
| `GET /ocean/shipments/{id}` | ruta, puertos, ETA, hitos, buque por tramo |
| `GET /ocean/shipments/{id}/geojson` | **posición actual** y trayecto |

Lo que llega y lo que no
-------------------------

Llegan hitos con `ACT`/`EST` —la separación exacta que RN-14 necesita entre lo
ocurrido y lo estimado—, ETA, ETD/ATD, buque, IMO, puerto de destino
normalizado y el transbordo. **No llegan velocidad ni rumbo**, y no hacen falta:
RN-16 los quería para *estimar* la ETA y ShipsGo la entrega ya calculada.

La posición **no está garantizada**: el BL de COSCO vino con `current: null` en
todas sus *features*. Por eso los hitos son obligatorios y la posición opcional,
y por eso `US-02` —AIS como respaldo del mapa— recupera sentido justo para esos
casos.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any, Final

logger = logging.getLogger(__name__)

#: Códigos de evento de ShipsGo que interesan, y a qué etapa de RN-02..RN-06
#: los mapea TrackIn. Los que no están —`EMSH` (vacío al exportador), `GTIN`
#: (entrada a puerta)— son movimientos de patio: ocurren antes de que la carga
#: navegue y no mueven la etapa.
ETAPA_POR_EVENTO: Final[dict[str, str]] = {
    "LOAD": "EN_ORIGEN",  # cargado al buque en el puerto de salida
    "DEPA": "EN_TRANSITO",  # zarpó
    "ARRV": "EN_TRANSITO",  # arribó a **un** puerto: ver la nota de abajo
    "DISC": "EN_TRANSITO",  # descargado en **un** puerto
}

#: Los dos eventos que significan «llegó», pero **solo en el puerto de destino**.
#:
#: Es la trampa de los envíos con transbordo, y los tres marítimos medidos la
#: tienen: `MRSU8507472` trae un `ARRV ACT` en Cartagena y `MRSU8132490` dos, en
#: Cartagena y en Manzanillo. Mapear `ARRV` a `EN_DESTINO` sin mirar el puerto
#: daba por llegados a los tres mientras seguían navegando — y, peor, el estado
#: no retrocedía después con el `DEPA` siguiente, porque la etapa se queda con
#: la más avanzada.
EVENTOS_DE_ARRIBO: Final[frozenset[str]] = frozenset({"ARRV", "DISC"})

#: Las dos vías. La forma del payload es la misma; cambian los códigos de
#: evento y las claves de la ruta, y nada más.
VIA_MARITIMA: Final = "MARITIMO"
VIA_AEREA: Final = "AEREO"

#: Códigos **IATA CIMP** de la vía aérea — `US-46`.
#:
#: Medidos sobre el MAWB `020-50685434` de Lufthansa Cargo (PEK → FRA → SJO),
#: que trajo los diez en `ACT`. `MAN` (manifestado) queda fuera a propósito: es
#: un evento documental, no un movimiento de la carga, igual que `EMSH` y
#: `GTIN` en la vía marítima.
ETAPA_POR_EVENTO_AEREO: Final[dict[str, str]] = {
    "RCS": "EN_ORIGEN",  # recibido del expedidor
    "DEP": "EN_TRANSITO",  # despegó
    "ARR": "EN_TRANSITO",  # aterrizó en **un** aeropuerto
    "RCF": "EN_TRANSITO",  # recibido del vuelo en **un** aeropuerto
    "DLV": "EN_TRANSITO",  # entregado: ver la nota de abajo
}

#: Los que significan «llegó», **solo en el aeropuerto de destino**. Misma
#: trampa que el transbordo marítimo: esta guía hizo `ARR` y `RCF` en Fráncfort
#: sin haber llegado a San José.
#:
#: `DLV` entra aquí y **no** en `RECIBIDO_EN_PLANTA`: que la aerolínea entregue
#: la carga al agente en el aeropuerto no es que haya entrado a la planta de
#: Gutis. Eso lo registra una persona (`US-18`), y el paso a proceso aduanal es
#: manual por decisión del 04/09.
EVENTOS_DE_ARRIBO_AEREO: Final[frozenset[str]] = frozenset({"ARR", "RCF", "DLV"})

#: Orden de avance de las etapas. Sirve para quedarse con la **más avanzada**
#: entre los hitos ocurridos, en vez de con la última del arreglo: los eventos
#: vienen ordenados por fecha, pero un `ARRV` en un puerto de transbordo no
#: puede hacer retroceder a un pedido que ya zarpó de ahí.
_AVANCE: Final[dict[str, int]] = {
    "SIN_TRACKING": 0,
    "EN_ORIGEN": 1,
    "EN_TRANSITO": 2,
    "EN_DESTINO": 3,
    "EN_PROCESO_ADUANAL": 4,
    "RECIBIDO_EN_PLANTA": 5,
}

#: El `status` de ShipsGo a etapa de TrackIn. Solo lo usa el envío partido,
#: donde `status_extended` cuenta las partes por estado y no hay hitos que
#: separar por parte.
_ETAPA_POR_ESTADO: Final[dict[str, str]] = {
    "NEW": "SIN_TRACKING",
    "BOOKED": "EN_ORIGEN",
    "DEPARTED": "EN_TRANSITO",
    "SAILING": "EN_TRANSITO",
    "IN_TRANSIT": "EN_TRANSITO",
    "ARRIVED": "EN_DESTINO",
    "DISCHARGED": "EN_DESTINO",
    "DELIVERED": "EN_DESTINO",
}

#: `ACT` es un hecho; `EST` es una estimación. La distinción es de ShipsGo y es
#: exactamente la que RN-14 necesita.
OCURRIDO: Final = "ACT"
ESTIMADO: Final = "EST"


@dataclass(frozen=True, slots=True)
class Hito:
    """Un movimiento del contenedor, tal como lo cuenta la fuente."""

    evento: str
    ocurrido: bool
    instante: dt.datetime | None
    puerto: str | None
    puerto_nombre: str | None
    buque: str | None
    imo: int | None


def es_arribo(hito: Hito, via: str) -> bool:
    """Si el evento significa «llegó» en esa vía.

    **Función y no método, a propósito.** Como predicado del hito tendría que
    aceptar la vía, y una `via` con valor por defecto convierte `hito.es_arribo`
    —sin llamar— en un objeto método, que es *siempre* verdadero. Ese descuido
    daría por arribado todo lo que se le pusiera delante y no lo avisaría
    ninguna herramienta; así, la misma errata lanza `AttributeError`.

    **En qué puerto** ocurrió lo decide la lectura, que es la única que conoce
    el destino: `ARR` en Fráncfort y `ARR` en San José son el mismo código y
    significan cosas distintas.
    """
    arribos = EVENTOS_DE_ARRIBO_AEREO if via == VIA_AEREA else EVENTOS_DE_ARRIBO
    return hito.evento in arribos


@dataclass(frozen=True, slots=True)
class Vehiculo:
    """Una nave del trayecto. Varias significan transbordo."""

    nombre: str
    imo: int | None


@dataclass(slots=True)
class LecturaEmbarque:
    """Lo que TrackIn extrae de un embarque de ShipsGo."""

    id_embarque: int | None = None
    referencia: str | None = None
    estado_fuente: str | None = None
    #: Naviera o aerolínea, según la vía.
    naviera: str | None = None
    via: str = VIA_MARITIMA
    #: Partes de un envío repartido (`status_extended`). Vacío si no está
    #: partido. El cuarto criterio de `US-46` pide que la etapa refleje **cada**
    #: parte y no solo la primera.
    partes: dict[str, int] = field(default_factory=dict)

    #: Puerto de descarga normalizado (`CRPMN`, `CRCAL`).
    puerto_destino: str | None = None
    puerto_destino_nombre: str | None = None
    #: `route.port_of_discharge.date_of_discharge_predicted`.
    eta: dt.datetime | None = None
    #: `route.port_of_loading.date_of_loading` — el ETD/ATD que pide `US-43`.
    etd: dt.datetime | None = None
    ata: dt.datetime | None = None

    hitos: list[Hito] = field(default_factory=list)
    vehiculos: list[Vehiculo] = field(default_factory=list)

    #: `(longitud, latitud)` — el orden de GeoJSON, no el de PostGIS.
    posicion: tuple[float, float] | None = None
    vehiculo_actual: Vehiculo | None = None

    #: ShipsGo archiva solo lo terminado: si viene, el embarque puede dejar de
    #: ser consultable y el payload guardado pasa a ser la única copia.
    archivado_en: dt.datetime | None = None

    def _etapa_de(self, hito: Hito) -> str | None:
        """La etapa del hito, teniendo en cuenta **en qué puerto** ocurrió.

        Un `ARRV` es `EN_DESTINO` solo si el puerto es el de descarga; en
        cualquier otro es un transbordo, y la carga sigue en tránsito.
        """
        arribos = EVENTOS_DE_ARRIBO_AEREO if self.via == VIA_AEREA else EVENTOS_DE_ARRIBO
        mapa = ETAPA_POR_EVENTO_AEREO if self.via == VIA_AEREA else ETAPA_POR_EVENTO
        if hito.evento in arribos:
            if self.puerto_destino is not None and hito.puerto == self.puerto_destino:
                return "EN_DESTINO"
            return "EN_TRANSITO"
        return mapa.get(hito.evento)

    @property
    def etapa(self) -> str:
        """La etapa más avanzada entre los hitos **ocurridos** (RN-02..RN-06).

        La más avanzada y no la última: los eventos vienen ordenados por fecha,
        pero quedarse con el último haría retroceder a un pedido cuyo hito final
        ocurrido sea de patio.
        """
        etapas = [
            etapa
            for etapa in (self._etapa_de(h) for h in self.hitos if h.ocurrido)
            if etapa is not None
        ]
        if not etapas:
            return "SIN_TRACKING"
        avanzada = max(etapas, key=lambda e: _AVANCE.get(e, 0))

        # Cuarto criterio de `US-46`: *«dado un envío partido en varias
        # entregas, la etapa refleja el estado de cada parte y no solo de la
        # primera»*. Con partes en distinto estado manda la **menos** avanzada:
        # decir que llegó cuando llegó la mitad es la clase de optimismo que
        # hace que alguien planifique producción con material que no está.
        if len(self.partes) > 1:
            atrasada = min(self.partes, key=lambda e: _AVANCE.get(_ETAPA_POR_ESTADO.get(e, ""), 99))
            etapa_atrasada = _ETAPA_POR_ESTADO.get(atrasada)
            if etapa_atrasada is not None and _AVANCE.get(etapa_atrasada, 0) < _AVANCE.get(
                avanzada, 0
            ):
                return etapa_atrasada
        return avanzada

    @property
    def hay_transbordo(self) -> bool:
        """Más de una nave en el trayecto (`US-30`).

        Se midieron hasta **tres** en un solo envío. `US-30` estaba especificada
        como captura manual; con esto puede pasar a detección automática.
        """
        return len(self.vehiculos) > 1

    @property
    def arribado(self) -> bool:
        """Hay un `ARRV` o `DISC` **ocurrido** en el puerto de destino.

        Es el mecanismo primario de arribo de `US-11` desde que se midió que no
        hay cobertura AIS en ningún puerto de Gutis.
        """
        return any(
            h.ocurrido
            and es_arribo(h, self.via)
            and (self.puerto_destino is None or h.puerto == self.puerto_destino)
            for h in self.hitos
        )


def _a_instante(valor: Any) -> dt.datetime | None:
    """ISO-8601 con desfase horario a `datetime` con zona.

    ShipsGo entrega las horas en la zona **del puerto** (`-03:00` en Santos,
    `-06:00` en Moín). Se conserva el desfase en vez de normalizar a UTC acá:
    el instante es el mismo y la zona original es información de auditoría.
    """
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        return valor
    try:
        return dt.datetime.fromisoformat(str(valor))
    except ValueError:
        logger.warning("ShipsGo: instante ilegible %r; se descarta.", valor)
        return None


def _localizacion(bloque: Any) -> tuple[str | None, str | None]:
    """Código y nombre del lugar. Marítimo usa `code`; aéreo, `iata`."""
    if not isinstance(bloque, dict):
        return None, None
    return bloque.get("code") or bloque.get("iata"), bloque.get("name")


def _vehiculo(bloque: Any) -> Vehiculo | None:
    """El buque o el vuelo del tramo.

    La vía marítima lo entrega como objeto (`{"name", "imo"}`) y la aérea como
    una cadena suelta (`"LH8431"`). Un vuelo no tiene IMO: eso es de la OMI y
    solo aplica a naves.
    """
    if isinstance(bloque, str):
        nombre = bloque.strip()
        return Vehiculo(nombre=nombre, imo=None) if nombre else None
    if not isinstance(bloque, dict) or not bloque.get("name"):
        return None
    imo = bloque.get("imo")
    return Vehiculo(nombre=str(bloque["name"]), imo=int(imo) if imo is not None else None)


def interpretar(
    shipment: dict[str, Any] | None,
    geojson: dict[str, Any] | None = None,
) -> LecturaEmbarque:
    """Convierte los dos payloads en una lectura. Tolera que falte el segundo.

    Nunca lanza por un campo ausente: un payload incompleto es un embarque
    **recién dado de alta** que todavía no maduró (~90 s), no un error. Quien
    llama distingue los dos casos con `esta_maduro`.
    """
    lectura = LecturaEmbarque()
    if not shipment:
        return lectura

    lectura.id_embarque = shipment.get("id")
    lectura.referencia = (
        shipment.get("container_number")
        or shipment.get("booking_number")
        or shipment.get("awb_number")
        or shipment.get("reference")
    )
    lectura.estado_fuente = shipment.get("status")
    naviera = shipment.get("carrier") or shipment.get("airline")
    if isinstance(naviera, dict):
        lectura.naviera = naviera.get("name")
    lectura.archivado_en = _a_instante(shipment.get("discarded_at"))

    # La vía se deduce del propio payload: el aéreo trae `awb_number`.
    lectura.via = VIA_AEREA if shipment.get("awb_number") else VIA_MARITIMA

    partido = shipment.get("status_extended")
    if isinstance(partido, dict) and shipment.get("status_split"):
        lectura.partes = {str(k): int(v) for k, v in partido.items()}

    ruta = shipment.get("route")
    if isinstance(ruta, dict):
        # Marítimo: `port_of_discharge` / `port_of_loading`.
        # Aéreo:    `destination` / `origin`, con otras claves de fecha.
        descarga = ruta.get("port_of_discharge") or ruta.get("destination")
        if isinstance(descarga, dict):
            lectura.puerto_destino, lectura.puerto_destino_nombre = _localizacion(
                descarga.get("location")
            )
            # La predicha es la que vale: `date_of_discharge` puede venir con el
            # plan original y no con lo que la naviera espera hoy. En aéreo el
            # equivalente es `date_of_rcf`: recibido del vuelo en destino.
            lectura.eta = _a_instante(
                descarga.get("date_of_discharge_predicted")
                or descarga.get("date_of_discharge")
                or descarga.get("date_of_rcf")
                or descarga.get("date_of_rcf_initial")
            )
        carga = ruta.get("port_of_loading") or ruta.get("origin")
        if isinstance(carga, dict):
            lectura.etd = _a_instante(carga.get("date_of_loading") or carga.get("date_of_dep"))

    lectura.hitos = _leer_hitos(shipment)
    lectura.vehiculos = _leer_vehiculos(lectura.hitos)

    # La ATA sale del primer `ARRV`/`DISC` ocurrido en el destino, no de un
    # campo propio: ShipsGo no lo trae y deducirlo del hito es lo correcto.
    for hito in lectura.hitos:
        if (
            hito.ocurrido
            and es_arribo(hito, lectura.via)
            and (lectura.puerto_destino is None or hito.puerto == lectura.puerto_destino)
        ):
            lectura.ata = hito.instante
            break

    posicion, nave = _leer_posicion(geojson)
    lectura.posicion = posicion
    lectura.vehiculo_actual = nave or (lectura.vehiculos[-1] if lectura.vehiculos else None)
    return lectura


def _leer_hitos(shipment: dict[str, Any]) -> list[Hito]:
    """Los movimientos, vengan del contenedor (mar) o de la raíz (aire).

    En la vía marítima cuelgan de `containers[].movements[]`; en la aérea, de
    `movements[]` directamente. Es la única diferencia de **forma** entre las
    dos —los códigos de evento sí difieren, y los aéreos los mapea `US-46`—, y
    tratarla acá evita que esa historia tenga que duplicar el recorrido.
    """
    crudos: list[Any] = []
    contenedores = shipment.get("containers")
    if isinstance(contenedores, list):
        for contenedor in contenedores:
            if isinstance(contenedor, dict) and isinstance(contenedor.get("movements"), list):
                crudos.extend(contenedor["movements"])
    elif isinstance(shipment.get("movements"), list):
        crudos.extend(shipment["movements"])

    hitos: list[Hito] = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        codigo, nombre = _localizacion(crudo.get("location"))
        nave = _vehiculo(crudo.get("vessel") or crudo.get("flight"))
        hitos.append(
            Hito(
                evento=str(crudo.get("event") or ""),
                ocurrido=crudo.get("status") == OCURRIDO,
                instante=_a_instante(crudo.get("timestamp")),
                puerto=codigo,
                puerto_nombre=nombre,
                buque=nave.nombre if nave else None,
                imo=nave.imo if nave else None,
            )
        )
    return hitos


def _leer_vehiculos(hitos: list[Hito]) -> list[Vehiculo]:
    """Las naves del trayecto, en orden y sin repetir consecutivas.

    Un cambio de nave entre tramos **es** el transbordo: no hay campo que lo
    anuncie. El primer envío medido pasó de `MAERSK CHACHAI` a `POLAR BRASIL` en
    Cartagena, y el segundo encadenó tres.
    """
    vehiculos: list[Vehiculo] = []
    for hito in hitos:
        if hito.buque is None:
            continue
        candidata = Vehiculo(nombre=hito.buque, imo=hito.imo)
        if not vehiculos or vehiculos[-1] != candidata:
            vehiculos.append(candidata)
    return vehiculos


def _leer_posicion(
    geojson: dict[str, Any] | None,
) -> tuple[tuple[float, float] | None, Vehiculo | None]:
    """Posición actual y nave que la lleva, del tramo marcado `CURRENT`.

    El trayecto viene partido en *features* `PAST`, `CURRENT` y `FUTURE`, y solo
    el del medio trae `properties.current`. Que venga `null` es normal y no es
    un fallo: se midió así en el BL de COSCO.
    """
    if not isinstance(geojson, dict):
        return None, None

    for feature in geojson.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            continue
        actual = props.get("current")
        if not isinstance(actual, dict):
            continue
        coordenadas = actual.get("coordinates")
        if (
            isinstance(coordenadas, list | tuple)
            and len(coordenadas) >= 2
            and all(isinstance(c, int | float) for c in coordenadas[:2])
        ):
            return (float(coordenadas[0]), float(coordenadas[1])), _vehiculo(props.get("vessel"))
    return None, None


def esta_maduro(shipment: dict[str, Any] | None) -> bool:
    """Si el embarque ya tiene datos, o sigue madurando tras el alta.

    **El tercer estado.** A los 45 s del alta los dos embarques medidos
    devolvían `status: NEW`, `route: null` y `containers: []`; a los ~90 s
    estaban completos. No es un fallo ni una respuesta vacía definitiva, y
    tratarlo como cualquiera de las dos da un falso negativo —por eso `US-07`
    tiene que contemplarlo al planificar.
    """
    if not shipment:
        return False
    if shipment.get("status") == "NEW":
        return False
    if shipment.get("route"):
        return True
    contenedores = shipment.get("containers")
    movimientos = shipment.get("movements")
    return bool(contenedores) or bool(movimientos)


__all__ = [
    "ESTIMADO",
    "ETAPA_POR_EVENTO",
    "ETAPA_POR_EVENTO_AEREO",
    "EVENTOS_DE_ARRIBO",
    "EVENTOS_DE_ARRIBO_AEREO",
    "VIA_AEREA",
    "VIA_MARITIMA",
    "OCURRIDO",
    "Hito",
    "LecturaEmbarque",
    "Vehiculo",
    "es_arribo",
    "esta_maduro",
    "interpretar",
]
