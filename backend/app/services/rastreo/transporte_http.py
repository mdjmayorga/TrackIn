"""El transporte HTTP real de las fuentes REST — `US-45`, `US-46`, `US-05`.

Hasta aquí los tres clientes hablaban con un protocolo inyectado y un doble.
Esto es la implementación con `httpx` que los conecta al mundo, y lo único que
faltaba para una corrida en vivo.

Por qué son dos adaptadores y no uno
-------------------------------------

Porque las dos APIs piden cosas distintas y forzar un protocolo común habría
escondido la diferencia en vez de resolverla:

| | ShipsGo | OpenSky |
|---|---|---|
| Autenticación | Cabecera con token fijo | OAuth2, cuerpo `form-urlencoded` |
| Parámetros | Van en la ruta | Van en la *query string* |
| Cabeceras de respuesta | No se usan | **Sí**: `x-rate-limit-remaining` |
| Cuerpo | Siempre JSON | JSON, o vacío en algunos errores |

El de OpenSky devuelve las cabeceras porque su cuota **se lee de ahí**; el de
ShipsGo no las necesita y no las carga.

Un fallo de red no es un fallo de la fuente
--------------------------------------------

Los dos adaptadores traducen las excepciones de `httpx` a un motivo de
`resiliencia`, y la distinción importa: un DNS bloqueado, un *timeout* y un
rechazo TLS apuntan a causas distintas en una red corporativa, y reportar «no
funcionó» para los tres deja a quien diagnostica sin nada. La clasificación es
la misma que usaron los spikes para diferenciarlos desde la red de Gutis.

Todos son **transitorios**: un problema de red se arregla solo o con el tiempo,
y `US-03` ya sabe esperar. Lo que no puede pasar es que un corte de red degrade
una fuente como si la credencial estuviera mal.

Los tiempos salen de lo medido
-------------------------------

TG-11 cronometró desde la red de Gutis: el token de OpenSky tarda **1085 ms** y
`/states/all` **915 ms**. Con eso, 30 s de lectura da margen de sobra sin dejar
una petición colgada tomando un hueco del *pool*. La conexión tiene su propio
tope, más corto: si el TCP no completa el saludo en 10 s, no es lentitud, es un
firewall descartando paquetes.

> **Sin inspección TLS.** TG-11 lo verificó en los dos hosts de OpenSky y TG-10
> en AISStream: los certificados llegan intactos desde la red corporativa. Por
> eso aquí **no** se desactiva la verificación ni se carga un CA propio, que es
> justo lo que uno se siente tentado a hacer cuando algo falla y lo que dejaría
> el tráfico abierto para siempre.
"""

from __future__ import annotations

import logging
from typing import Any, Final

import httpx

from app.services.rastreo import opensky_cliente, shipsgo_cliente

logger = logging.getLogger(__name__)

#: Segundos. La conexión es corta a propósito: pasado ese punto no es lentitud.
TIMEOUT_CONEXION_S: Final = 10.0
#: La lectura es holgada: lo más lento medido fueron 1085 ms.
TIMEOUT_LECTURA_S: Final = 30.0

#: Conexiones que se reutilizan. El sondeo es de decenas de peticiones por
#: tic, no de miles: un pool grande solo reservaría descriptores ociosos.
CONEXIONES_MAXIMAS: Final = 10


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=TIMEOUT_CONEXION_S,
        read=TIMEOUT_LECTURA_S,
        write=TIMEOUT_LECTURA_S,
        pool=TIMEOUT_LECTURA_S,
    )


def crear_cliente_http() -> httpx.AsyncClient:
    """Un `AsyncClient` configurado, para compartir entre peticiones.

    Se comparte porque abrir una conexión TLS por consulta desperdiciaría el
    saludo completo en cada una; con el sondeo por ventanas eso son cientos de
    saludos al día por nada.
    """
    return httpx.AsyncClient(
        timeout=_timeout(),
        limits=httpx.Limits(max_connections=CONEXIONES_MAXIMAS),
        follow_redirects=False,
    )


def clasificar_error_de_red(exc: Exception) -> tuple[str, str]:
    """Traduce una excepción de `httpx` a `(motivo, explicación)`.

    El punto es no reportar «no funcionó»: un DNS bloqueado, un *timeout* y un
    rechazo TLS apuntan a causas distintas en una red corporativa. Todos son
    motivos **transitorios** para `resiliencia`.
    """
    if isinstance(exc, httpx.ConnectTimeout):
        return "tiempo_agotado", "el TCP no completó el saludo; puede haber un firewall"
    if isinstance(exc, httpx.ReadTimeout | httpx.WriteTimeout | httpx.PoolTimeout):
        return "tiempo_agotado", "la conexión abrió pero no hubo respuesta a tiempo"
    if isinstance(exc, httpx.ProxyError):
        return "error_de_red", "falló el proxy configurado en el sistema"
    if isinstance(exc, httpx.TooManyRedirects):
        return "error_de_red", "bucle de redirecciones; típico de un portal cautivo"
    if isinstance(exc, httpx.ConnectError):
        detalle = str(exc).lower()
        if any(pista in detalle for pista in ("name", "resolve", "getaddrinfo")):
            return "error_de_red", "no se pudo resolver el hostname; posible DNS bloqueado"
        return "error_de_red", "no se pudo establecer la conexión TCP/TLS"
    if isinstance(exc, httpx.HTTPError):
        return "error_de_red", f"error HTTP genérico: {type(exc).__name__}"
    return "error_de_red", f"{type(exc).__name__}: {exc}"


def _cuerpo_json(respuesta: httpx.Response) -> Any:
    """El JSON de la respuesta, o un diccionario con el texto si no lo es.

    OpenSky devuelve `404` con cuerpo `[]` y algunos errores llegan sin JSON.
    Reventar al deserializar convertiría un error del servidor —transitorio— en
    una excepción distinta que nadie clasificó.
    """
    try:
        return respuesta.json()
    except ValueError:
        return {"texto": respuesta.text[:500]}


class TransporteShipsGoHTTP:
    """Implementa `shipsgo_cliente.Transporte` sobre `httpx`."""

    def __init__(self, cliente: httpx.AsyncClient) -> None:
        self._cliente = cliente

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str],
        cuerpo: dict[str, Any] | None = None,
    ) -> shipsgo_cliente.Respuesta:
        try:
            respuesta = await self._cliente.request(metodo, url, headers=cabeceras, json=cuerpo)
        except Exception as exc:  # se clasifican todas, ninguna escapa sin motivo
            motivo, explicacion = clasificar_error_de_red(exc)
            logger.warning("ShipsGo: %s %s — %s (%s)", metodo, url, explicacion, motivo)
            raise shipsgo_cliente.ErrorShipsGo(motivo, explicacion) from exc

        datos = _cuerpo_json(respuesta)
        return shipsgo_cliente.Respuesta(
            estado=respuesta.status_code,
            cuerpo=datos if isinstance(datos, dict) else {"datos": datos},
        )


class TransporteOpenSkyHTTP:
    """Implementa `opensky_cliente.Transporte` sobre `httpx`.

    Devuelve las cabeceras porque de ahí sale `x-rate-limit-remaining`, que es
    el cuarto criterio de `US-05` y la única forma de saber la cuota sin llevar
    contabilidad propia — que además estaría mal, porque cada familia de
    endpoints tiene su propio contador.
    """

    def __init__(self, cliente: httpx.AsyncClient) -> None:
        self._cliente = cliente

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str] | None = None,
        datos: dict[str, str] | None = None,
        parametros: dict[str, Any] | None = None,
    ) -> opensky_cliente.Respuesta:
        try:
            respuesta = await self._cliente.request(
                metodo,
                url,
                headers=cabeceras,
                # `data` va como `form-urlencoded`, que es lo que el endpoint
                # de token exige; `params`, como *query string*.
                data=datos,
                params=parametros,
            )
        except Exception as exc:  # se clasifican todas, ninguna escapa sin motivo
            motivo, explicacion = clasificar_error_de_red(exc)
            logger.warning("OpenSky: %s %s — %s (%s)", metodo, url, explicacion, motivo)
            raise opensky_cliente.ErrorOpenSky(motivo, explicacion) from exc

        return opensky_cliente.Respuesta(
            estado=respuesta.status_code,
            cuerpo=_cuerpo_json(respuesta),
            cabeceras=dict(respuesta.headers),
        )


def crear_cliente_shipsgo(
    cliente_http: httpx.AsyncClient, token: str
) -> shipsgo_cliente.ClienteShipsGo:
    """El cliente de ShipsGo listo para hablar con el servicio real."""
    return shipsgo_cliente.ClienteShipsGo(TransporteShipsGoHTTP(cliente_http), token=token)


def crear_cliente_opensky(
    cliente_http: httpx.AsyncClient, client_id: str, client_secret: str
) -> opensky_cliente.ClienteOpenSky:
    """El cliente de OpenSky listo para hablar con el servicio real."""
    return opensky_cliente.ClienteOpenSky(
        TransporteOpenSkyHTTP(cliente_http),
        client_id=client_id,
        client_secret=client_secret,
    )


__all__ = [
    "CONEXIONES_MAXIMAS",
    "TIMEOUT_CONEXION_S",
    "TIMEOUT_LECTURA_S",
    "TransporteOpenSkyHTTP",
    "TransporteShipsGoHTTP",
    "clasificar_error_de_red",
    "crear_cliente_http",
    "crear_cliente_opensky",
    "crear_cliente_shipsgo",
]
