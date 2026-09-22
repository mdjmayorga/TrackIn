"""Cliente HTTP de ShipsGo — `US-45` / RF-06, RF-09.

**El hallazgo de arquitectura de `TASK-28`:** ShipsGo no responde «¿dónde está
el contenedor X?» en frío. Primero hay que **dar de alta** el embarque en la
cuenta —eso es lo que cuesta— y después se consulta. `/ocean/shipments` lista
los embarques *de la cuenta*, no el universo de contenedores.

Las tres cosas que cambian el diseño, todas medidas el 14/09/2026
------------------------------------------------------------------

**1. El `409` no es un fallo.** Repetir el alta de una referencia ya registrada
devuelve `409 ALREADY_EXISTS` **con el embarque existente**, sin crear nada y
sin descontar crédito. Tiene una consecuencia presupuestaria concreta: si un
alta se corta por *timeout*, el adaptador no sabe si prosperó, y **reintentarla
es seguro y gratis**. Sin esa garantía habría que llevar un registro propio de
«qué ya registré» solo para no pagar dos veces.

**2. Un BL se da de alta sin enumerar contenedores.** Basta el
`booking_number`; ShipsGo los resuelve solo. Y la unidad de cobro es el
embarque: **`1 BL = 1 crédito`**, confirmado por el proveedor por escrito, sin
importar cuántos contenedores ampare.

**3. ShipsGo acepta y cobra cualquier cosa.** Un `POST` con el contenedor
inventado `XXXX0000000` devolvió `200 SUCCESS` y creó el embarque. **No hay
validación de formato del lado del proveedor**, así que la comprobación local
del dígito verificador (`services/referencia.py`) es lo único que separa una
errata de una factura de 2 USD. Este cliente **exige** que la referencia venga
validada: no es su trabajo decidirlo, pero sí negarse a gastar sin ello.

Por qué el transporte se inyecta
---------------------------------

`Transporte` es un protocolo de un solo método. No quedan créditos para probar
contra el servicio real —los dos trials de 3 altas se agotaron y la compra se
difiere—, así que todo lo de aquí se ejercita con un doble que devuelve los
payloads grabados. Cuando haya créditos, la implementación de `httpx` entra sin
tocar nada más.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Final, Protocol

from app.services import resiliencia

logger = logging.getLogger(__name__)

BASE: Final = "https://api.shipsgo.com/v2"

#: Cabecera de autenticación. El token va aquí y **nunca** en la URL: los
#: registros del proxy corporativo guardan la ruta completa.
CABECERA_TOKEN: Final = "X-Shipsgo-User-Token"

#: Lo que cada vía usa como clave de alta.
CAMPO_POR_TIPO: Final[dict[str, str]] = {
    "CONTENEDOR": "container_number",
    "BOOKING": "booking_number",
    "BL": "booking_number",
    "MAWB": "awb_number",
}

#: Qué endpoint le toca a cada tipo de referencia.
RUTA_POR_TIPO: Final[dict[str, str]] = {
    "CONTENEDOR": "/ocean/shipments",
    "BOOKING": "/ocean/shipments",
    "BL": "/ocean/shipments",
    "MAWB": "/air/shipments",
}


class ErrorShipsGo(RuntimeError):
    """Fallo de ShipsGo ya clasificado para la política de `US-03`."""

    def __init__(self, motivo: str, detalle: str = "") -> None:
        super().__init__(detalle or motivo)
        self.motivo = motivo
        self.detalle = detalle

    @property
    def clase(self) -> resiliencia.ClaseFallo:
        return resiliencia.clasificar(self.motivo)


@dataclass(frozen=True, slots=True)
class Respuesta:
    """Lo mínimo que el cliente necesita de una respuesta HTTP."""

    estado: int
    cuerpo: dict[str, Any]


class Transporte(Protocol):
    """El puerto HTTP. Una función, para poder doblarla sin ceremonia."""

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str],
        cuerpo: dict[str, Any] | None = None,
    ) -> Respuesta: ...


@dataclass(frozen=True, slots=True)
class ResultadoAlta:
    """Qué pasó con el alta, y **si costó dinero**."""

    id_embarque: int
    #: `False` cuando ShipsGo respondió `409`: ya estaba y no se cobró.
    consumio_credito: bool
    payload: dict[str, Any]


def clasificar_respuesta(estado: int, cuerpo: dict[str, Any]) -> str | None:
    """Traduce el error de ShipsGo a un motivo de `resiliencia`.

    Devuelve `None` cuando no hay fallo. Es el mapeo que `US-03` dejó pendiente
    al cerrarse el 08/09 —*«el mapeo de los errores concretos de cada
    proveedor»*— y que la fase 2 de `TASK-28` midió.
    """
    mensaje = str(cuerpo.get("message") or "").strip().upper()

    if estado in (200, 201, 409):
        # El `message` manda sobre el código cuando se contradicen. Es la
        # «trampa del 200 vacío» que la fase 2 midió en TrackingMore: un
        # `200` con un error dentro se leería como éxito mirando solo el
        # estado, y se contaría como contacto correcto una lectura que no lo es.
        if mensaje in ("TOKEN_MISSING", "TOKEN_NOT_FOUND"):
            return "credencial_invalida"
        if mensaje == "NOT_ENOUGH_CREDITS":
            return "cuota_agotada"
        return None
    if estado == 401:
        # `TOKEN_MISSING` / `TOKEN_NOT_FOUND`. Degradar la fuente, no reintentar.
        return "credencial_invalida"
    if estado == 403:
        return "permiso_denegado"
    if estado == 402:
        # `NOT_ENOUGH_CREDITS`. Insistir no lo cambia: hay que comprar.
        return "cuota_agotada"
    if estado == 404:
        # Sobre un id de embarque: la cuenta no lo tiene registrado. No es
        # «no existe para siempre», es «hay que darlo de alta».
        return "embarque_no_registrado"
    if estado == 422:
        return "referencia_mal_formada"
    if estado == 429:
        return "limite_de_tasa"  # transitorio: hay que esperar
    return "error_del_servidor"  # 5xx y cualquier otro: transitorio


class ClienteShipsGo:
    """Alta y lectura de embarques. No persiste nada."""

    def __init__(self, transporte: Transporte, token: str, base: str = BASE) -> None:
        self._transporte = transporte
        self._token = token
        self._base = base.rstrip("/")

    @property
    def _cabeceras(self) -> dict[str, str]:
        return {CABECERA_TOKEN: self._token, "Content-Type": "application/json"}

    async def _pedir(
        self, metodo: str, ruta: str, cuerpo: dict[str, Any] | None = None
    ) -> Respuesta:
        respuesta = await self._transporte(
            metodo, f"{self._base}{ruta}", cabeceras=self._cabeceras, cuerpo=cuerpo
        )
        motivo = clasificar_respuesta(respuesta.estado, respuesta.cuerpo)
        if motivo is not None:
            detalle = str(respuesta.cuerpo.get("message") or respuesta.cuerpo)[:200]
            raise ErrorShipsGo(motivo, f"{metodo} {ruta} → {respuesta.estado}: {detalle}")
        return respuesta

    async def dar_de_alta(self, tipo: str, numero: str) -> ResultadoAlta:
        """Registra el embarque. **Cuesta un crédito**, salvo que ya estuviera.

        `tipo` y `numero` tienen que venir **ya validados** por
        `services.referencia`: ShipsGo no valida el formato y cobra igual.
        """
        tipo_norm = tipo.strip().upper()
        campo = CAMPO_POR_TIPO.get(tipo_norm)
        ruta = RUTA_POR_TIPO.get(tipo_norm)
        if campo is None or ruta is None:
            raise ErrorShipsGo(
                "referencia_mal_formada",
                f"ShipsGo no da de alta referencias de tipo {tipo_norm!r}.",
            )

        respuesta = await self._pedir("POST", ruta, {campo: numero})
        cuerpo = respuesta.cuerpo

        if respuesta.estado == 409:
            # `ALREADY_EXISTS`: no crea nada y no descuenta crédito. Por eso
            # reintentar un alta cortada por *timeout* es seguro.
            embarque = cuerpo.get("shipment") or cuerpo
            id_embarque = embarque.get("id")
            if id_embarque is None:
                raise ErrorShipsGo(
                    "error_del_servidor", "409 sin el embarque existente en el cuerpo."
                )
            logger.info(
                "ShipsGo: %s %s ya estaba dado de alta (id %s).", tipo_norm, numero, id_embarque
            )
            return ResultadoAlta(int(id_embarque), consumio_credito=False, payload=embarque)

        embarque = cuerpo.get("shipment") or cuerpo
        id_embarque = embarque.get("id")
        if id_embarque is None:
            raise ErrorShipsGo("error_del_servidor", "el alta no devolvió id de embarque.")

        logger.warning(
            "ShipsGo: alta de %s %s → id %s. **Consumió un crédito** (~2 USD).",
            tipo_norm,
            numero,
            id_embarque,
        )
        return ResultadoAlta(int(id_embarque), consumio_credito=True, payload=embarque)

    async def consultar(self, ruta: str) -> dict[str, Any]:
        """Un `GET` cualquiera ya clasificado. **No consume crédito.**

        Existe para el catálogo de aerolíneas (`US-46`), que es una consulta
        libre y no encaja en `leer`: no pide un embarque.
        """
        return (await self._pedir("GET", ruta)).cuerpo

    async def leer(self, id_embarque: int, aereo: bool = False) -> dict[str, Any]:
        """El embarque completo: ruta, puertos, ETA, hitos y buque por tramo."""
        prefijo = "/air" if aereo else "/ocean"
        respuesta = await self._pedir("GET", f"{prefijo}/shipments/{id_embarque}")
        cuerpo = respuesta.cuerpo
        return cuerpo.get("shipment") or cuerpo

    async def leer_geojson(self, id_embarque: int, aereo: bool = False) -> dict[str, Any] | None:
        """Posición actual y trayecto. **Consultar no cuesta crédito.**

        El endpoint no estaba documentado en la guía del proveedor: sin él la
        conclusión habría sido que ShipsGo no entrega posición, que es falso.

        Un fallo aquí **no tumba la lectura**: la posición es opcional —el BL de
        COSCO vino sin ella— y los hitos ya llegaron por el otro endpoint.
        """
        prefijo = "/air" if aereo else "/ocean"
        try:
            respuesta = await self._pedir("GET", f"{prefijo}/shipments/{id_embarque}/geojson")
        except ErrorShipsGo as exc:
            logger.warning(
                "ShipsGo: sin geojson para el embarque %s (%s). Se sigue sin posición.",
                id_embarque,
                exc.motivo,
            )
            return None
        return respuesta.cuerpo


@dataclass(frozen=True, slots=True)
class Consumo:
    """Cuántas altas se hicieron y cuántas costaron.

    Lo que `US-07` tiene que vigilar es **esto**, no el número de consultas: el
    crédito se gasta en el alta. Sondear seguido no quema créditos, solo roza el
    límite de tasa.
    """

    altas_intentadas: int = 0
    creditos_consumidos: int = 0
    instante: dt.datetime | None = None


__all__ = [
    "BASE",
    "CABECERA_TOKEN",
    "CAMPO_POR_TIPO",
    "RUTA_POR_TIPO",
    "ClienteShipsGo",
    "Consumo",
    "ErrorShipsGo",
    "Respuesta",
    "ResultadoAlta",
    "Transporte",
    "clasificar_respuesta",
]
