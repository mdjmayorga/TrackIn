"""Pruebas del destino por definir y su asignación a mano (26/11/2026).

Corrida en vivo con Compras al cargar el Z-tracking: muchos marítimos todavía
no tienen incoterm, y sin puerto la carga los rechazaba. Desde ahora entran con
el destino «Por definir», y Compras o Logística lo eligen en el detalle. La
precedencia en las cargas siguientes es: ShipsGo, después lo elegido a mano y
por último el archivo.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

import test_intervenciones as base
from app.models.maestro_destino import MaestroDestino
from app.services.ingesta.carga import PREFIJO_DISCREPANCIA, cargar
from test_carga import FuenteFalsa, ResolutorFalso, _crudo

pytestmark = pytest.mark.integration

api = base.api
_url = base._url

MOTIVO = "Compras confirma con el agente que descarga en Caldera"


def _destino(codigo: str | None = "CRCAL", motivo: str = MOTIVO) -> dict[str, Any]:
    return {"codigo": codigo, "motivo": motivo}


async def _por_definir(sesion, **kwargs):
    """Un marítimo como lo deja la carga cuando no hay puerto: sin destino."""
    return await base._pedido(sesion, id_destino=None, lead_time_destino_dias=None, **kwargs)


async def _id(sesion, codigo: str) -> int:
    return await sesion.scalar(select(MaestroDestino.id).where(MaestroDestino.codigo == codigo))


# --- La consulta ------------------------------------------------------------------


async def test_el_pedido_por_definir_se_lista_y_se_ve_en_el_detalle(api, sesion) -> None:
    cliente, _ = api
    pedido = await _por_definir(sesion)

    detalle = await cliente.get(f"/api/v1/pedidos/{pedido.id}")
    listado = await cliente.get("/api/v1/pedidos", params={"q": pedido.oc_numero})

    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["destino"] is None
    assert detalle.json()["calculo"]["fecha_proyectada"] is None
    (fila,) = (p for p in listado.json()["items"] if p["id"] == pedido.id)
    assert fila["destino"] is None


# --- La asignación --------------------------------------------------------------


async def test_compras_asigna_el_puerto_y_queda_en_la_bitacora(api, sesion) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await _por_definir(sesion)

    respuesta = await cliente.post(_url(pedido, "destino"), json=_destino())

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["destino"]["codigo"] == "CRCAL"
    await sesion.refresh(pedido)
    assert pedido.destino_manual is True
    assert pedido.lead_time_destino_dias is not None
    (asiento,) = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert (asiento["tipo"], asiento["valor_anterior"], asiento["valor_nuevo"]) == (
        "ASIGNACION_DESTINO",
        None,
        "CRCAL",
    )
    assert asiento["motivo"] == MOTIVO


async def test_tambien_se_cambia_un_puerto_ya_asignado(api, sesion) -> None:
    cliente, _ = api
    pedido = await base._pedido(sesion)

    respuesta = await cliente.post(_url(pedido, "destino"), json=_destino("CRLIO"))

    assert respuesta.status_code == 200, respuesta.text
    (asiento,) = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert (asiento["valor_anterior"], asiento["valor_nuevo"]) == ("CRMOB", "CRLIO")


async def test_el_mismo_puerto_no_deja_asiento(api, sesion) -> None:
    cliente, _ = api
    pedido = await base._pedido(sesion)

    respuesta = await cliente.post(_url(pedido, "destino"), json=_destino("CRMOB"))

    assert respuesta.status_code == 409
    assert (await cliente.get(_url(pedido, "bitacora"))).json() == []


async def test_un_puerto_de_otra_via_se_rechaza(api, sesion) -> None:
    """Un marítimo no descarga en el aeropuerto."""
    cliente, _ = api
    pedido = await _por_definir(sesion)

    respuesta = await cliente.post(_url(pedido, "destino"), json=_destino("MROC"))

    assert respuesta.status_code == 422
    assert "marítimo" in respuesta.json()["detail"]


async def test_un_codigo_que_no_existe_se_rechaza(api, sesion) -> None:
    cliente, _ = api
    pedido = await _por_definir(sesion)

    respuesta = await cliente.post(_url(pedido, "destino"), json=_destino("XXXXX"))

    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [("COMPRAS", 200), ("LOGISTICA", 200), ("ADMINISTRADOR", 200), ("PLANIFICACION", 403)],
)
async def test_lo_asignan_compras_y_logistica(api, sesion, rol, esperado) -> None:
    cliente, como = api
    if rol != "LOGISTICA":
        await como(rol)
    pedido = await _por_definir(sesion)

    respuesta = await cliente.post(_url(pedido, "destino"), json=_destino())

    assert respuesta.status_code == esperado


# --- La precedencia en las cargas siguientes --------------------------------------


def _linea_del_pedido(**kwargs):
    """La línea del Z-tracking del pedido de `base._pedido`, sin referencia."""
    return _crudo(
        oc_numero="4544400001",
        posicion_oc=10,
        destino_codigo=None,
        tipo_referencia="BL",
        numero_referencia="COSU6508789000",
        **kwargs,
    )


async def test_el_archivo_no_pisa_lo_elegido_a_mano(api, sesion) -> None:
    cliente, _ = api
    pedido = await _por_definir(sesion)
    await cliente.post(_url(pedido, "destino"), json=_destino("CRCAL"))

    await cargar(
        sesion, FuenteFalsa([_linea_del_pedido(incoterm="CIF LIMON")]), señalar_ausentes=False
    )

    await sesion.refresh(pedido)
    assert pedido.id_destino == await _id(sesion, "CRCAL")
    assert pedido.destino_manual is True


async def test_un_archivo_sin_puerto_tampoco_lo_borra(api, sesion) -> None:
    cliente, _ = api
    pedido = await _por_definir(sesion)
    await cliente.post(_url(pedido, "destino"), json=_destino("CRCAL"))

    resultado = await cargar(
        sesion, FuenteFalsa([_linea_del_pedido(incoterm=None)]), señalar_ausentes=False
    )

    await sesion.refresh(pedido)
    assert pedido.id_destino == await _id(sesion, "CRCAL")
    assert resultado.destinos_por_definir == []


async def test_shipsgo_gana_sobre_lo_elegido_a_mano_y_lo_avisa(api, sesion) -> None:
    cliente, _ = api
    pedido = await _por_definir(sesion)
    await cliente.post(_url(pedido, "destino"), json=_destino("CRCAL"))

    resultado = await cargar(
        sesion,
        FuenteFalsa([_linea_del_pedido(incoterm=None)]),
        señalar_ausentes=False,
        resolutor_destino=ResolutorFalso("CRMOB"),
    )

    await sesion.refresh(pedido)
    assert pedido.id_destino == await _id(sesion, "CRMOB")
    assert pedido.destino_manual is False
    (aviso,) = resultado.destinos_discrepantes
    assert aviso.detalle.startswith(PREFIJO_DISCREPANCIA)
    assert "a mano CRCAL" in aviso.detalle
