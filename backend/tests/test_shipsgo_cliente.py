"""Pruebas de `app.services.rastreo.shipsgo_cliente` — `US-45`.

Sin red: el transporte se inyecta. No quedan créditos para probar contra el
servicio real, así que lo que se fija aquí es el **contrato medido** por
`TASK-28` el 14/09/2026, con especial cuidado en lo que cuesta dinero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.services.rastreo.shipsgo_cliente import (
    CABECERA_TOKEN,
    CAMPO_POR_TIPO,
    RUTA_POR_TIPO,
    ClienteShipsGo,
    ErrorShipsGo,
    Respuesta,
    clasificar_respuesta,
)
from app.services.resiliencia import ClaseFallo


@dataclass
class TransporteFalso:
    """Devuelve respuestas preparadas y anota lo que se le pidió."""

    respuestas: list[Respuesta]
    llamadas: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)
    cabeceras_vistas: list[dict[str, str]] = field(default_factory=list)

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str],
        cuerpo: dict[str, Any] | None = None,
    ) -> Respuesta:
        self.llamadas.append((metodo, url, cuerpo))
        self.cabeceras_vistas.append(cabeceras)
        return self.respuestas.pop(0)


def _cliente(*respuestas: Respuesta) -> tuple[ClienteShipsGo, TransporteFalso]:
    transporte = TransporteFalso(list(respuestas))
    return ClienteShipsGo(transporte, token="t-oken"), transporte


# --- El alta, que es lo que cuesta -----------------------------------------


async def test_el_alta_devuelve_el_id_y_avisa_que_costo() -> None:
    cliente, _ = _cliente(Respuesta(200, {"message": "SUCCESS", "id": 6734886}))

    resultado = await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")

    assert resultado.id_embarque == 6734886
    assert resultado.consumio_credito is True


async def test_un_409_no_es_un_fallo_y_no_cobra() -> None:
    """`ALREADY_EXISTS`: no crea nada, devuelve el embarque y no descuenta.

    De esto depende que reintentar un alta cortada por *timeout* sea seguro:
    sin la garantía habría que llevar un registro propio de «qué ya registré»
    solo para no pagar dos veces.
    """
    cliente, _ = _cliente(
        Respuesta(409, {"message": "ALREADY_EXISTS", "shipment": {"id": 6734941}})
    )

    resultado = await cliente.dar_de_alta("BOOKING", "COSU6508789000")

    assert resultado.id_embarque == 6734941
    assert resultado.consumio_credito is False


async def test_reintentar_un_alta_cortada_es_gratis() -> None:
    """El escenario real: el primer intento se corta y no se sabe si prosperó."""
    cliente, _ = _cliente(
        Respuesta(500, {"message": "BOOM"}),
        Respuesta(409, {"message": "ALREADY_EXISTS", "shipment": {"id": 42}}),
    )

    with pytest.raises(ErrorShipsGo):
        await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")
    segundo = await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")

    assert segundo.id_embarque == 42
    assert segundo.consumio_credito is False


async def test_un_bl_se_da_de_alta_sin_enumerar_contenedores() -> None:
    """Basta el `booking_number`: ShipsGo los resuelve solo, y cobra **uno**."""
    cliente, transporte = _cliente(Respuesta(200, {"id": 1, "container_count": 3}))

    await cliente.dar_de_alta("BL", "271102440")

    _, _, cuerpo = transporte.llamadas[0]
    assert cuerpo == {"booking_number": "271102440"}


@pytest.mark.parametrize(
    ("tipo", "campo"),
    [
        ("CONTENEDOR", "container_number"),
        ("BOOKING", "booking_number"),
        ("BL", "booking_number"),
        ("MAWB", "awb_number"),
    ],
)
async def test_cada_tipo_usa_su_campo_de_alta(tipo: str, campo: str) -> None:
    cliente, transporte = _cliente(Respuesta(200, {"id": 1}))

    await cliente.dar_de_alta(tipo, "X")

    assert transporte.llamadas[0][2] == {campo: "X"}


async def test_el_mawb_va_al_endpoint_aereo() -> None:
    cliente, transporte = _cliente(Respuesta(200, {"id": 1}))

    await cliente.dar_de_alta("MAWB", "020-50685434")

    assert transporte.llamadas[0][1].endswith("/air/shipments")


@pytest.mark.parametrize("tipo", ["MMSI", "IMO", "VUELO", "BUQUE", "INVENTADO"])
async def test_un_tipo_que_shipsgo_no_sigue_no_gasta_una_llamada(tipo: str) -> None:
    """Se detiene **antes** de la red: no es su clave de consulta."""
    cliente, transporte = _cliente()

    with pytest.raises(ErrorShipsGo, match="no da de alta"):
        await cliente.dar_de_alta(tipo, "123")

    assert transporte.llamadas == []


async def test_los_dos_mapas_cubren_los_mismos_tipos() -> None:
    """Un tipo en uno y no en el otro daría un `KeyError` en producción."""
    assert set(CAMPO_POR_TIPO) == set(RUTA_POR_TIPO)


async def test_un_alta_sin_id_se_trata_como_error_del_servidor() -> None:
    cliente, _ = _cliente(Respuesta(200, {"message": "SUCCESS"}))

    with pytest.raises(ErrorShipsGo) as exc:
        await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")

    assert exc.value.clase is ClaseFallo.TRANSITORIO


# --- El token --------------------------------------------------------------


async def test_el_token_viaja_en_la_cabecera_y_no_en_la_url() -> None:
    """Los registros del proxy corporativo guardan la ruta completa."""
    cliente, transporte = _cliente(Respuesta(200, {"id": 1}))

    await cliente.dar_de_alta("CONTENEDOR", "MRSU8507472")

    assert transporte.cabeceras_vistas[0][CABECERA_TOKEN] == "t-oken"
    assert "t-oken" not in transporte.llamadas[0][1]


# --- Lectura ---------------------------------------------------------------


async def test_leer_devuelve_el_embarque() -> None:
    cliente, transporte = _cliente(Respuesta(200, {"id": 7, "status": "SAILING"}))

    embarque = await cliente.leer(7)

    assert embarque["status"] == "SAILING"
    assert transporte.llamadas[0][1].endswith("/ocean/shipments/7")


async def test_leer_desenvuelve_el_embarque_si_viene_anidado() -> None:
    cliente, _ = _cliente(Respuesta(200, {"shipment": {"id": 7, "status": "SAILING"}}))
    assert (await cliente.leer(7))["id"] == 7


async def test_el_geojson_va_a_su_propio_endpoint() -> None:
    """Los datos viven en **dos** endpoints; la posición solo en este."""
    cliente, transporte = _cliente(Respuesta(200, {"type": "FeatureCollection"}))

    await cliente.leer_geojson(7)

    assert transporte.llamadas[0][1].endswith("/ocean/shipments/7/geojson")


async def test_un_geojson_caido_no_tumba_la_lectura() -> None:
    """La posición es opcional y los hitos ya llegaron por el otro endpoint."""
    cliente, _ = _cliente(Respuesta(500, {"message": "BOOM"}))

    assert await cliente.leer_geojson(7) is None


# --- El mapeo de errores que `US-03` dejó pendiente ------------------------


@pytest.mark.parametrize(
    ("estado", "motivo", "clase"),
    [
        (200, None, None),
        (201, None, None),
        (409, None, None),
        (401, "credencial_invalida", ClaseFallo.PERMANENTE),
        (403, "permiso_denegado", ClaseFallo.PERMANENTE),
        (402, "cuota_agotada", ClaseFallo.PERMANENTE),
        (404, "embarque_no_registrado", ClaseFallo.REQUIERE_ALTA),
        (422, "referencia_mal_formada", ClaseFallo.PERMANENTE),
        (429, "limite_de_tasa", ClaseFallo.TRANSITORIO),
        (500, "error_del_servidor", ClaseFallo.TRANSITORIO),
        (503, "error_del_servidor", ClaseFallo.TRANSITORIO),
    ],
)
def test_el_mapeo_de_errores(estado: int, motivo: str | None, clase: ClaseFallo | None) -> None:
    resultado = clasificar_respuesta(estado, {})

    assert resultado == motivo
    if motivo is not None:
        assert ErrorShipsGo(motivo).clase is clase


def test_un_404_pide_alta_en_vez_de_darse_por_vencido() -> None:
    """No es «no existe para siempre», es «hay que darlo de alta primero».

    Tratarlo como permanente dejaría la referencia muerta; como transitorio,
    reintentando en vano contra un embarque que nadie registró.
    """
    error = ErrorShipsGo(clasificar_respuesta(404, {}) or "")

    assert error.clase is ClaseFallo.REQUIERE_ALTA


@pytest.mark.parametrize(
    ("mensaje", "motivo"),
    [("TOKEN_MISSING", "credencial_invalida"), ("NOT_ENOUGH_CREDITS", "cuota_agotada")],
)
def test_un_200_con_un_error_dentro_no_cuenta_como_exito(mensaje: str, motivo: str) -> None:
    """La «trampa del 200 vacío» que la fase 2 midió en TrackingMore.

    Mirando solo el código se leería como contacto correcto una lectura que no
    lo es, y la fuente parecería sana mientras no devuelve nada.
    """
    assert clasificar_respuesta(200, {"message": mensaje}) == motivo


async def test_el_error_lleva_el_detalle_para_diagnosticar() -> None:
    cliente, _ = _cliente(Respuesta(401, {"message": "TOKEN_NOT_FOUND"}))

    with pytest.raises(ErrorShipsGo) as exc:
        await cliente.leer(7)

    assert "TOKEN_NOT_FOUND" in exc.value.detalle
    assert "401" in exc.value.detalle
