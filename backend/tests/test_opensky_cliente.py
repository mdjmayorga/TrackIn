"""Pruebas de `app.services.rastreo.opensky_cliente` — `US-05`.

Sin red: el transporte y el reloj se inyectan. Lo que se fija es el refresco
**proactivo** del token y la lectura de la cuota, que son los dos criterios que
no se pueden comprobar mirando el código.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.services.rastreo.opensky_cliente import (
    CABECERA_CUOTA,
    COSTA_RICA,
    FRACCION_REFRESCO,
    TTL_POR_DEFECTO_S,
    URL_TOKEN,
    BoundingBox,
    ClienteOpenSky,
    ErrorOpenSky,
    Respuesta,
    clasificar_respuesta,
)

ARRANQUE = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
HORA_SERVIDOR = 1787066777


def _token(ttl: int | None = 1800) -> Respuesta:
    cuerpo: dict[str, Any] = {"access_token": "t-1"}
    if ttl is not None:
        cuerpo["expires_in"] = ttl
    return Respuesta(200, cuerpo, {})


def _aeronave() -> list[Any]:
    vector: list[Any] = [None] * 17
    vector[0] = "0ac9e1"
    vector[1] = "AVA072  "
    vector[4] = HORA_SERVIDOR - 1
    vector[5] = -85.333
    vector[6] = 10.9489
    vector[7] = 10972.8
    vector[9] = 240.82
    return vector


def _estados(*aeronaves: list[Any], cuota: int | None = 3917) -> Respuesta:
    cabeceras = {CABECERA_CUOTA: str(cuota)} if cuota is not None else {}
    return Respuesta(
        200,
        {"time": HORA_SERVIDOR, "states": list(aeronaves) or None},
        cabeceras,
    )


@dataclass
class TransporteFalso:
    respuestas: list[Respuesta]
    llamadas: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)
    cabeceras_vistas: list[dict[str, str] | None] = field(default_factory=list)

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str] | None = None,
        datos: dict[str, str] | None = None,
        parametros: dict[str, Any] | None = None,
    ) -> Respuesta:
        self.llamadas.append((metodo, url, parametros or datos))
        self.cabeceras_vistas.append(cabeceras)
        return self.respuestas.pop(0)

    @property
    def tokens_pedidos(self) -> int:
        return sum(1 for _, url, _ in self.llamadas if url == URL_TOKEN)


class RelojFalso:
    def __init__(self, inicio: dt.datetime) -> None:
        self.ahora = inicio

    def __call__(self) -> dt.datetime:
        return self.ahora

    def avanzar(self, **kwargs: float) -> None:
        self.ahora += dt.timedelta(**kwargs)


def _cliente(*respuestas: Respuesta) -> tuple[ClienteOpenSky, TransporteFalso, RelojFalso]:
    transporte = TransporteFalso(list(respuestas))
    reloj = RelojFalso(ARRANQUE)
    cliente = ClienteOpenSky(transporte, "cli-api-client", "secreto", reloj=reloj)
    return cliente, transporte, reloj


# --- El refresco proactivo del token ---------------------------------------


async def test_el_token_se_pide_una_vez_y_se_reutiliza() -> None:
    cliente, transporte, _ = _cliente(_token(), _estados(_aeronave()), _estados(_aeronave()))

    await cliente.estados()
    await cliente.estados()

    assert transporte.tokens_pedidos == 1


async def test_el_token_se_renueva_al_ochenta_por_ciento_del_ttl() -> None:
    """*«Renovar al ~80 % del TTL, es decir a los 24 min, no reactivo al 401»*.

    Importa por dos razones medidas: obtener el token cuesta ~1000 ms, y un
    `401` **no devuelve el header de cuota**, así que descubrir la caducidad
    consultando deja un hueco en la contabilidad además de perder la lectura.
    """
    cliente, transporte, reloj = _cliente(
        _token(1800), _estados(_aeronave()), _token(1800), _estados(_aeronave())
    )

    await cliente.estados()
    reloj.avanzar(minutes=23)  # todavía dentro del 80 %
    assert cliente.token_vigente is True

    reloj.avanzar(minutes=2)  # 25 min: pasado el umbral de 24
    assert cliente.token_vigente is False
    await cliente.estados()

    assert transporte.tokens_pedidos == 2


def test_la_fraccion_de_refresco_es_el_ochenta_por_ciento() -> None:
    assert FRACCION_REFRESCO == 0.8
    assert TTL_POR_DEFECTO_S == 1800
    assert TTL_POR_DEFECTO_S * FRACCION_REFRESCO == 1440  # 24 minutos


async def test_sin_expires_in_se_usa_el_ttl_medido() -> None:
    """TG-11 lo verificó contra los claims `iat`/`exp` del JWT: 1800 s."""
    cliente, _, reloj = _cliente(_token(ttl=None), _estados(_aeronave()))

    await cliente.estados()
    reloj.avanzar(seconds=TTL_POR_DEFECTO_S * FRACCION_REFRESCO - 1)

    assert cliente.token_vigente is True


async def test_el_token_usa_client_credentials() -> None:
    cliente, transporte, _ = _cliente(_token(), _estados(_aeronave()))

    await cliente.estados()

    _, url, datos = transporte.llamadas[0]
    assert url == URL_TOKEN
    assert datos is not None
    assert datos["grant_type"] == "client_credentials"
    assert datos["client_id"] == "cli-api-client"


async def test_el_token_viaja_como_bearer() -> None:
    cliente, transporte, _ = _cliente(_token(), _estados(_aeronave()))

    await cliente.estados()

    assert transporte.cabeceras_vistas[1] == {"Authorization": "Bearer t-1"}


@pytest.mark.parametrize(
    "respuesta",
    [Respuesta(401, {"error": "invalid_client"}, {}), Respuesta(200, {}, {})],
)
async def test_un_token_que_no_llega_se_reporta_como_credencial(
    respuesta: Respuesta,
) -> None:
    cliente, _, _ = _cliente(respuesta)

    with pytest.raises(ErrorOpenSky) as exc:
        await cliente.estados()

    assert exc.value.motivo == "credencial_invalida"


# --- La cuota: se lee, no se lleva -----------------------------------------


async def test_registra_la_cuota_de_cada_respuesta() -> None:
    """Cuarto criterio: *«registro el valor de x-rate-limit-remaining»*."""
    cliente, _, _ = _cliente(_token(), _estados(_aeronave(), cuota=3917))

    assert cliente.cuota_restante is None
    await cliente.estados()

    assert cliente.cuota_restante == 3917


async def test_la_cabecera_se_busca_sin_distinguir_mayusculas() -> None:
    cliente, _, _ = _cliente(
        _token(),
        Respuesta(200, {"time": 1, "states": None}, {"X-Rate-Limit-Remaining": "3000"}),
    )

    await cliente.estados()

    assert cliente.cuota_restante == 3000


async def test_quedarse_sin_cuota_avisa(caplog) -> None:
    """Por debajo de 400 no cabe ni el sondeo de una cuenta anónima."""
    import logging

    cliente, _, _ = _cliente(_token(), _estados(_aeronave(), cuota=120))

    with caplog.at_level(logging.WARNING):
        await cliente.estados()

    assert "120 créditos" in caplog.text


async def test_una_cuota_ilegible_no_tumba_la_lectura(caplog) -> None:
    import logging

    cliente, _, _ = _cliente(
        _token(), Respuesta(200, {"time": 1, "states": None}, {CABECERA_CUOTA: "muchos"})
    )

    with caplog.at_level(logging.WARNING):
        posiciones = await cliente.estados()

    assert posiciones == []
    assert "cuota ilegible" in caplog.text


async def test_sin_cabecera_de_cuota_no_se_inventa_un_valor() -> None:
    cliente, _, _ = _cliente(_token(), _estados(_aeronave(), cuota=None))

    await cliente.estados()

    assert cliente.cuota_restante is None


# --- La consulta -----------------------------------------------------------


async def test_el_bounding_box_viaja_como_parametros() -> None:
    cliente, transporte, _ = _cliente(_token(), _estados(_aeronave()))

    await cliente.estados()

    _, url, parametros = transporte.llamadas[1]
    assert url.endswith("/states/all")
    assert parametros == {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}


async def test_una_respuesta_sin_aeronaves_no_es_un_fallo() -> None:
    """`200` con `states: null`. De madrugada es lo corriente, y consume
    crédito igual: es el argumento a favor de las ventanas activas."""
    cliente, _, _ = _cliente(_token(), _estados())

    assert await cliente.estados() == []


async def test_devuelve_las_aeronaves_parseadas() -> None:
    cliente, _, _ = _cliente(_token(), _estados(_aeronave()))

    posiciones = await cliente.estados()

    assert len(posiciones) == 1
    assert posiciones[0].icao24 == "0ac9e1"
    assert posiciones[0].callsign == "AVA072"


def test_el_area_de_costa_rica_es_la_medida() -> None:
    """La que TG-11 usó: 12 a 14 aeronaves por muestra, 1 crédito."""
    assert COSTA_RICA.grados_cuadrados == pytest.approx(11.55, abs=0.01)


def test_un_area_mayor_se_puede_declarar() -> None:
    grande = BoundingBox(lat_min=0.0, lon_min=-90.0, lat_max=20.0, lon_max=-70.0)
    assert grande.grados_cuadrados == 400.0


# --- El contrato de errores ------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [
        (200, None),
        (400, "referencia_mal_formada"),
        (401, "credencial_invalida"),
        (403, "permiso_denegado"),
        (404, "referencia_inexistente"),
        (429, "cuota_agotada"),
        (500, "error_del_servidor"),
        (503, "error_del_servidor"),
    ],
)
def test_el_mapeo_de_errores(estado: int, motivo: str | None) -> None:
    assert clasificar_respuesta(estado) == motivo


async def test_un_error_de_consulta_lleva_el_detalle() -> None:
    cliente, _, _ = _cliente(_token(), Respuesta(500, {"error": "boom"}, {}))

    with pytest.raises(ErrorOpenSky) as exc:
        await cliente.estados()

    assert exc.value.motivo == "error_del_servidor"
    assert "500" in exc.value.detalle
