"""Pruebas del transporte HTTP real — `US-45`, `US-46`, `US-05`.

Con `httpx.MockTransport`: **httpx de verdad, red falsa**. Es lo que permite
verificar lo que solo se ve al bajar a la capa HTTP —que el token viaje como
`form-urlencoded`, que los parámetros lleguen en la *query string*, que las
cabeceras de respuesta se propaguen— sin salir a internet ni gastar créditos.

La pieza de arriba se prueba con dobles y la de abajo con `MockTransport`: entre
las dos queda cubierto el camino entero hasta el borde de la red.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.services.rastreo import opensky_cliente, shipsgo_cliente, transporte_http
from app.services.resiliencia import ClaseFallo, clasificar


def _cliente_con(manejador) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(manejador))


def _cliente_que_falla(exc: Exception) -> httpx.AsyncClient:
    def manejador(peticion: httpx.Request) -> httpx.Response:
        raise exc

    return _cliente_con(manejador)


# --- Clasificación de fallos de red ----------------------------------------


@pytest.mark.parametrize(
    ("excepcion", "motivo"),
    [
        (httpx.ConnectTimeout("nada"), "tiempo_agotado"),
        (httpx.ReadTimeout("nada"), "tiempo_agotado"),
        (httpx.WriteTimeout("nada"), "tiempo_agotado"),
        (httpx.PoolTimeout("nada"), "tiempo_agotado"),
        (httpx.ProxyError("nada"), "error_de_red"),
        (httpx.TooManyRedirects("nada"), "error_de_red"),
        (httpx.ConnectError("nada"), "error_de_red"),
        (RuntimeError("algo raro"), "error_de_red"),
    ],
)
def test_cada_fallo_de_red_tiene_su_motivo(excepcion: Exception, motivo: str) -> None:
    resultado, explicacion = transporte_http.clasificar_error_de_red(excepcion)

    assert resultado == motivo
    assert explicacion, "el motivo sin explicación no le sirve a quien diagnostica"


def test_un_dns_bloqueado_se_distingue_de_un_rechazo_tcp() -> None:
    """Reportar «no funcionó» para los dos deja a quien diagnostica sin nada.

    En una red corporativa apuntan a causas distintas: un DNS filtrado y un
    firewall descartando SYN se arreglan en sitios diferentes.
    """
    _, dns = transporte_http.clasificar_error_de_red(
        httpx.ConnectError("[Errno -2] Name or service not known")
    )
    _, tcp = transporte_http.clasificar_error_de_red(httpx.ConnectError("connection refused"))

    assert "DNS" in dns
    assert "TCP" in tcp


@pytest.mark.parametrize("motivo", ["tiempo_agotado", "error_de_red"])
def test_los_fallos_de_red_son_transitorios(motivo: str) -> None:
    """Un corte de red **no** puede degradar una fuente como si la credencial
    estuviera mal: se arregla solo o con el tiempo, y `US-03` sabe esperar."""
    assert clasificar(motivo) is ClaseFallo.TRANSITORIO


# --- El transporte de ShipsGo ----------------------------------------------


async def test_shipsgo_envia_el_token_en_la_cabecera() -> None:
    vistas: dict[str, Any] = {}

    def manejador(peticion: httpx.Request) -> httpx.Response:
        vistas["cabeceras"] = dict(peticion.headers)
        vistas["cuerpo"] = peticion.content
        return httpx.Response(200, json={"id": 1})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token="t-oken")
        await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")

    assert vistas["cabeceras"][shipsgo_cliente.CABECERA_TOKEN.lower()] == "t-oken"
    assert b"MRSU8507472" in vistas["cuerpo"]


async def test_shipsgo_manda_el_cuerpo_como_json() -> None:
    vistas: dict[str, Any] = {}

    def manejador(peticion: httpx.Request) -> httpx.Response:
        vistas["tipo"] = peticion.headers.get("content-type", "")
        return httpx.Response(200, json={"id": 1})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token="t")
        await cliente.dar_de_alta("BL", "271102440")

    assert "application/json" in vistas["tipo"]


async def test_shipsgo_propaga_el_409_sin_tratarlo_como_fallo() -> None:
    """El `409` llega hasta el cliente, que sabe que no es un error ni cobra."""

    def manejador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"message": "ALREADY_EXISTS", "shipment": {"id": 42}})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token="t")
        resultado = await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")

    assert resultado.id_embarque == 42
    assert resultado.consumio_credito is False


async def test_shipsgo_lee_un_embarque_completo() -> None:
    def manejador(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url.path.endswith("/ocean/shipments/7")
        return httpx.Response(200, json={"id": 7, "status": "SAILING"})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token="t")
        embarque = await cliente.leer(7)

    assert embarque["status"] == "SAILING"


async def test_shipsgo_convierte_un_corte_de_red_en_su_error() -> None:
    async with _cliente_que_falla(httpx.ConnectTimeout("nada")) as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token="t")

        with pytest.raises(shipsgo_cliente.ErrorShipsGo) as exc:
            await cliente.leer(7)

    assert exc.value.clase is ClaseFallo.TRANSITORIO


async def test_shipsgo_no_revienta_con_una_respuesta_sin_json() -> None:
    """Un `502` del proxy llega como HTML. Reventar al deserializar convertiría
    un error transitorio en una excepción que nadie clasificó."""

    def manejador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token="t")

        with pytest.raises(shipsgo_cliente.ErrorShipsGo) as exc:
            await cliente.leer(7)

    assert exc.value.motivo == "error_del_servidor"


# --- El transporte de OpenSky ----------------------------------------------


async def test_opensky_pide_el_token_como_form_urlencoded() -> None:
    """El endpoint de token lo exige: con JSON responde `400`."""
    vistas: dict[str, Any] = {}

    def manejador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == opensky_cliente.URL_TOKEN:
            vistas["tipo"] = peticion.headers.get("content-type", "")
            vistas["cuerpo"] = peticion.content.decode()
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
        return httpx.Response(200, json={"time": 1, "states": None})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_opensky(http, "cli-api-client", "secreto")
        await cliente.estados()

    assert "application/x-www-form-urlencoded" in vistas["tipo"]
    assert "grant_type=client_credentials" in vistas["cuerpo"]
    assert "client_id=cli-api-client" in vistas["cuerpo"]


async def test_opensky_manda_el_bounding_box_en_la_query() -> None:
    vistas: dict[str, Any] = {}

    def manejador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == opensky_cliente.URL_TOKEN:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
        vistas["query"] = dict(peticion.url.params)
        return httpx.Response(200, json={"time": 1, "states": None})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_opensky(http, "c", "s")
        await cliente.estados()

    assert vistas["query"]["lamin"] == "8.0"
    assert vistas["query"]["lomax"] == "-82.5"


async def test_opensky_propaga_la_cabecera_de_cuota() -> None:
    """De ahí sale `x-rate-limit-remaining`, que es el cuarto criterio.

    Si el transporte no la devolviera, el cliente no tendría de dónde leerla y
    el criterio quedaría cumplido solo en apariencia.
    """

    def manejador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == opensky_cliente.URL_TOKEN:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
        return httpx.Response(
            200,
            json={"time": 1, "states": None},
            headers={opensky_cliente.CABECERA_CUOTA: "3917"},
        )

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_opensky(http, "c", "s")
        await cliente.estados()

        assert cliente.cuota_restante == 3917


async def test_opensky_parsea_las_aeronaves_de_punta_a_punta() -> None:
    """El camino completo: HTTP → JSON → vector de estado → `PosicionAerea`."""
    vector: list[Any] = [None] * 17
    vector[0] = "0ac9e1"
    vector[1] = "AVA072  "
    vector[4] = 1787066777
    vector[5] = -85.333
    vector[6] = 10.9489

    def manejador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == opensky_cliente.URL_TOKEN:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
        return httpx.Response(200, json={"time": 1787066778, "states": [vector]})

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_opensky(http, "c", "s")
        posiciones = await cliente.estados()

    assert len(posiciones) == 1
    assert posiciones[0].icao24 == "0ac9e1"
    assert posiciones[0].callsign == "AVA072"


async def test_opensky_sobrevive_al_404_con_cuerpo_de_lista() -> None:
    """Medido: el `404` por aeropuerto inexistente llega con cuerpo `[]`."""

    def manejador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == opensky_cliente.URL_TOKEN:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
        return httpx.Response(404, json=[])

    async with _cliente_con(manejador) as http:
        cliente = transporte_http.crear_cliente_opensky(http, "c", "s")

        with pytest.raises(opensky_cliente.ErrorOpenSky) as exc:
            await cliente.estados()

    assert exc.value.motivo == "referencia_inexistente"


async def test_opensky_convierte_un_corte_de_red_en_su_error() -> None:
    async with _cliente_que_falla(httpx.ConnectError("nada")) as http:
        cliente = transporte_http.crear_cliente_opensky(http, "c", "s")

        with pytest.raises(opensky_cliente.ErrorOpenSky) as exc:
            await cliente.estados()

    assert clasificar(exc.value.motivo) is ClaseFallo.TRANSITORIO


# --- La configuración del cliente compartido -------------------------------


async def test_el_cliente_trae_los_tiempos_medidos() -> None:
    """El token de OpenSky tardó 1085 ms desde la red de Gutis y
    `/states/all` 915 ms: 30 s de lectura da margen de sobra."""
    async with transporte_http.crear_cliente_http() as http:
        assert http.timeout.connect == transporte_http.TIMEOUT_CONEXION_S
        assert http.timeout.read == transporte_http.TIMEOUT_LECTURA_S


async def test_el_cliente_no_sigue_redirecciones() -> None:
    """Un portal cautivo corporativo responde `302` a cualquier cosa.

    Seguirlo devolvería el HTML del portal con un `200` alegre, que el cliente
    leería como una respuesta válida y vacía.
    """
    async with transporte_http.crear_cliente_http() as http:
        assert http.follow_redirects is False


def test_la_verificacion_tls_no_se_desactiva() -> None:
    """TG-10 y TG-11 verificaron que **no hay inspección TLS** en la red de
    Gutis. Desactivar la verificación es lo que uno se siente tentado a hacer
    cuando algo falla, y dejaría el tráfico abierto para siempre.
    """
    import inspect

    fuente = inspect.getsource(transporte_http)

    assert "verify=False" not in fuente
    assert "verify = False" not in fuente
