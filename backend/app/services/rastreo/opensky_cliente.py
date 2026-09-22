"""Cliente de OpenSky con OAuth2 — `US-05` / RF-07, RF-09.

El token se renueva **antes** de caducar
-----------------------------------------

OpenSky retiró la autenticación Basic; hoy es `client_credentials` con un token
de **1800 s**, verificado por TG-11 contra los claims `iat`/`exp` del JWT.

El refresco es **proactivo al 80 % del TTL** —a los 24 minutos— y no reactivo
al primer `401`. La diferencia importa por dos razones medidas: obtener el token
cuesta ~1000 ms, y un `401` **no devuelve el header de cuota**, así que
descubrir la caducidad consultando deja un hueco en la contabilidad además de
perder la lectura.

La cuota se lee, no se lleva
-----------------------------

El servidor devuelve `x-rate-limit-remaining` en cada respuesta. Llevar
contabilidad propia sería peor y además estaría mal: TG-11 confirmó por
aritmética que **cada familia de endpoints tiene su propio contador**, los dos
con 4000/día. La serie observada no es monótona (3960, 3956, **3970**, 3940)
precisamente por eso.

| Cuenta | Cuota diaria |
|---|---|
| Autenticada (OAuth2) | 4000 créditos |
| Anónima (por IP) | 400 |

Una consulta con *bounding box* de ~11,5 grados² cuesta **1 crédito**. Un `404`
por código OACI mal escrito cuesta **30** — el 0,75 % de la cuota diaria de
`/flights/*`—, así que esos códigos se validan antes de consultar.

Lo que **no** consume cuota: un `401` por token inválido y un `400` por
parámetros mal formados. Lo que **sí**, aunque no devuelva nada: un `200` con
`states: null`.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Final, Protocol

from app.services.rastreo.opensky import PosicionAerea, parsear_estados

logger = logging.getLogger(__name__)

URL_TOKEN: Final = (
    "https://auth.opensky-network.org/auth/realms/opensky-network" "/protocol/openid-connect/token"
)
BASE: Final = "https://opensky-network.org/api"

#: TTL medido del token. Se usa solo si la respuesta no trae `expires_in`.
TTL_POR_DEFECTO_S: Final = 1800

#: Fracción del TTL tras la cual se renueva. TG-11: *«el refresco debe ser
#: proactivo (renovar al ~80 % del TTL, es decir a los 24 min), no reactivo al
#: primer 401»*.
FRACCION_REFRESCO: Final = 0.8

#: Cabecera con la cuota restante. Se registra en cada respuesta.
CABECERA_CUOTA: Final = "x-rate-limit-remaining"


class ErrorOpenSky(RuntimeError):
    """Fallo de OpenSky ya clasificado para la política de `US-03`."""

    def __init__(self, motivo: str, detalle: str = "") -> None:
        super().__init__(detalle or motivo)
        self.motivo = motivo
        self.detalle = detalle


@dataclass(frozen=True, slots=True)
class Respuesta:
    """Lo mínimo que el cliente necesita de una respuesta HTTP."""

    estado: int
    cuerpo: Any
    cabeceras: dict[str, str]


class Transporte(Protocol):
    """El puerto HTTP, inyectable para poder probar sin red."""

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str] | None = None,
        datos: dict[str, str] | None = None,
        parametros: dict[str, Any] | None = None,
    ) -> Respuesta: ...


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """El área que se consulta. Su tamaño decide lo que cuesta."""

    lat_min: float
    lon_min: float
    lat_max: float
    lon_max: float

    def como_parametros(self) -> dict[str, float]:
        return {
            "lamin": self.lat_min,
            "lomin": self.lon_min,
            "lamax": self.lat_max,
            "lomax": self.lon_max,
        }

    @property
    def grados_cuadrados(self) -> float:
        return abs(self.lat_max - self.lat_min) * abs(self.lon_max - self.lon_min)


#: Costa Rica, el área que TG-11 midió: 12 a 14 aeronaves por muestra, 1 crédito.
COSTA_RICA = BoundingBox(lat_min=8.0, lon_min=-86.0, lat_max=11.3, lon_max=-82.5)


def clasificar_respuesta(estado: int) -> str | None:
    """Traduce el código de OpenSky a un motivo de `resiliencia`."""
    if estado == 200:
        return None
    if estado == 401:
        # No consume cuota. Con refresco proactivo no debería verse nunca.
        return "credencial_invalida"
    if estado == 403:
        return "permiso_denegado"
    if estado == 400:
        # Parámetros mal formados. No consume cuota, pero tampoco se arregla
        # reintentando: es un error nuestro.
        return "referencia_mal_formada"
    if estado == 404:
        return "referencia_inexistente"
    if estado == 429:
        return "cuota_agotada"
    return "error_del_servidor"


class ClienteOpenSky:
    """Token proactivo y consultas a `/states/all`. No persiste nada."""

    def __init__(
        self,
        transporte: Transporte,
        client_id: str,
        client_secret: str,
        reloj: Any = None,
        base: str = BASE,
    ) -> None:
        self._transporte = transporte
        self._client_id = client_id
        self._client_secret = client_secret
        self._base = base.rstrip("/")
        self._reloj = reloj or (lambda: dt.datetime.now(dt.UTC))
        self._token: str | None = None
        self._renovar_en: dt.datetime | None = None
        self._cuota_restante: int | None = None

    @property
    def cuota_restante(self) -> int | None:
        """Lo que dijo la última respuesta, o `None` si aún no hubo ninguna."""
        return self._cuota_restante

    @property
    def token_vigente(self) -> bool:
        return self._token is not None and (
            self._renovar_en is None or self._reloj() < self._renovar_en
        )

    async def _obtener_token(self) -> str:
        """Pide un token nuevo y calcula cuándo habrá que renovarlo."""
        respuesta = await self._transporte(
            "POST",
            URL_TOKEN,
            cabeceras={"Content-Type": "application/x-www-form-urlencoded"},
            datos={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if respuesta.estado != 200 or not isinstance(respuesta.cuerpo, dict):
            raise ErrorOpenSky(
                "credencial_invalida",
                f"el token devolvió {respuesta.estado}: {str(respuesta.cuerpo)[:200]}",
            )

        token = respuesta.cuerpo.get("access_token")
        if not token:
            raise ErrorOpenSky("credencial_invalida", "la respuesta no trae access_token.")

        ttl = respuesta.cuerpo.get("expires_in") or TTL_POR_DEFECTO_S
        self._token = str(token)
        self._renovar_en = self._reloj() + dt.timedelta(seconds=float(ttl) * FRACCION_REFRESCO)
        logger.info("OpenSky: token nuevo, TTL %s s; se renovará a las %s.", ttl, self._renovar_en)
        return self._token

    async def token(self) -> str:
        """El token vigente, renovándolo **antes** de que caduque."""
        if self.token_vigente and self._token is not None:
            return self._token
        return await self._obtener_token()

    def _anotar_cuota(self, cabeceras: dict[str, str]) -> None:
        """Registra `x-rate-limit-remaining`, que es el cuarto criterio.

        Las claves llegan con la caja que les dé el servidor, así que se busca
        sin distinguir mayúsculas.
        """
        for clave, valor in cabeceras.items():
            if clave.lower() != CABECERA_CUOTA:
                continue
            try:
                self._cuota_restante = int(valor)
            except (TypeError, ValueError):
                logger.warning("OpenSky: cuota ilegible en la cabecera: %r", valor)
                return
            if self._cuota_restante < 400:
                logger.warning(
                    "OpenSky: quedan %d créditos del día. El sondeo continuo no cabe.",
                    self._cuota_restante,
                )
            else:
                logger.debug("OpenSky: %d créditos restantes.", self._cuota_restante)
            return

    async def estados(self, area: BoundingBox = COSTA_RICA) -> list[PosicionAerea]:
        """Las aeronaves del área. Una lista vacía **no** es un fallo.

        Un *bounding box* sin tráfico devuelve `200` con `states: null`, y de
        madrugada es lo corriente. Consume crédito igual, que es el argumento a
        favor de las ventanas activas.
        """
        respuesta = await self._transporte(
            "GET",
            f"{self._base}/states/all",
            cabeceras={"Authorization": f"Bearer {await self.token()}"},
            parametros=area.como_parametros(),
        )
        self._anotar_cuota(respuesta.cabeceras)

        motivo = clasificar_respuesta(respuesta.estado)
        if motivo is not None:
            raise ErrorOpenSky(
                motivo, f"GET /states/all → {respuesta.estado}: {str(respuesta.cuerpo)[:200]}"
            )

        posiciones = parsear_estados(
            respuesta.cuerpo if isinstance(respuesta.cuerpo, dict) else None
        )
        logger.info(
            "OpenSky: %d aeronaves en %.1f grados²; %s créditos restantes.",
            len(posiciones),
            area.grados_cuadrados,
            self._cuota_restante if self._cuota_restante is not None else "?",
        )
        return posiciones


__all__ = [
    "BASE",
    "CABECERA_CUOTA",
    "COSTA_RICA",
    "FRACCION_REFRESCO",
    "TTL_POR_DEFECTO_S",
    "URL_TOKEN",
    "BoundingBox",
    "ClienteOpenSky",
    "ErrorOpenSky",
    "Respuesta",
    "Transporte",
    "clasificar_respuesta",
]
