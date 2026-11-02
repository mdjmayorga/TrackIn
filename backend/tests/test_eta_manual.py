"""Pruebas de la ETA a Costa Rica registrada a mano — `US-67`.

El caso que la originó: la guía `78469391954` (4500018865) terminó en París y
ShipsGo no informa el tramo a San José. Sin ETA de ninguna fuente no había
fecha proyectada, y sin ella tampoco se podían ajustar días (02/11/2026).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

import test_intervenciones as base
from app.services.proyeccion import (
    ORIGEN_ETA_DECLARADA,
    ORIGEN_ETA_ESTIMADA,
    ORIGEN_ETA_FUENTE,
    ORIGEN_ETA_MANUAL,
    PRECEDENCIA,
    calcular,
)

api = base.api
_url = base._url

MOTIVO = "El agente confirma el vuelo CDG-SJO para el jueves"
ETA = dt.date(2026, 11, 5)


def _eta(eta: dt.date | None = ETA, motivo: str = MOTIVO) -> dict[str, Any]:
    return {"eta": eta.isoformat() if eta else None, "motivo": motivo}


async def _en_paris(sesion):
    """En tránsito, sin ETA de la fuente ni del archivo: sin fecha proyectada."""
    return await base._rastreado(sesion, "EN_TRANSITO")


# --- La precedencia de RN-14 ---------------------------------------------------


def test_va_debajo_de_la_eta_de_la_fuente_y_encima_de_la_estimada() -> None:
    indice = PRECEDENCIA.index
    assert indice(ORIGEN_ETA_FUENTE) < indice(ORIGEN_ETA_MANUAL) < indice(ORIGEN_ETA_ESTIMADA)
    assert indice(ORIGEN_ETA_MANUAL) < indice(ORIGEN_ETA_DECLARADA)


def test_la_eta_de_la_fuente_le_gana() -> None:
    """Si ShipsGo vuelve a dar una ETA a un destino nuestro, esa manda."""
    resultado = calcular(eta_fuente=ETA, eta_manual=dt.date(2026, 11, 9), lead_time_dias=2)

    assert resultado.origen == ORIGEN_ETA_FUENTE


def test_le_gana_a_la_del_archivo() -> None:
    resultado = calcular(eta_manual=ETA, eta_declarada=dt.date(2026, 10, 20), lead_time_dias=2)

    assert resultado.origen == ORIGEN_ETA_MANUAL
    assert resultado.fecha == dt.date(2026, 11, 7)


# --- La intervención -----------------------------------------------------------


async def test_da_fecha_proyectada_al_pedido_que_no_tenia(api, sesion) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await _en_paris(sesion)

    respuesta = await cliente.post(_url(pedido, "eta-manual"), json=_eta())

    assert respuesta.status_code == 200, respuesta.text
    calculo = respuesta.json()["calculo"]
    assert calculo["eta_manual"] == "2026-11-05"
    assert calculo["origen"] == ORIGEN_ETA_MANUAL
    assert calculo["fecha_proyectada"] is not None


async def test_con_la_eta_ya_se_pueden_ajustar_dias(api, sesion) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await _en_paris(sesion)
    antes = (await cliente.post(_url(pedido, "eta-manual"), json=_eta())).json()

    ajuste = {"dias": 2, "motivo": "Inspección anunciada en el aeropuerto"}
    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json=ajuste)

    proyectada = dt.date.fromisoformat(antes["calculo"]["fecha_proyectada"])
    assert respuesta.json()["calculo"]["fecha_proyectada"] == str(proyectada + dt.timedelta(days=2))


async def test_se_reemplaza_se_quita_y_cada_cambio_queda_en_la_bitacora(api, sesion) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await _en_paris(sesion)

    await cliente.post(_url(pedido, "eta-manual"), json=_eta())
    await cliente.post(_url(pedido, "eta-manual"), json=_eta(dt.date(2026, 11, 7)))
    quitada = await cliente.post(_url(pedido, "eta-manual"), json=_eta(None))

    assert quitada.json()["calculo"]["fecha_proyectada"] is None
    asientos = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert [(a["tipo"], a["valor_anterior"], a["valor_nuevo"]) for a in asientos] == [
        ("ETA_MANUAL", None, "2026-11-05"),
        ("ETA_MANUAL", "2026-11-05", "2026-11-07"),
        ("ETA_MANUAL", "2026-11-07", None),
    ]
    assert asientos[0]["motivo"] == MOTIVO


async def test_repetir_la_misma_eta_no_deja_asiento(api, sesion) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await _en_paris(sesion)
    await cliente.post(_url(pedido, "eta-manual"), json=_eta())

    respuesta = await cliente.post(_url(pedido, "eta-manual"), json=_eta())

    assert respuesta.status_code == 409
    assert len((await cliente.get(_url(pedido, "bitacora"))).json()) == 1


async def test_sin_motivo_tambien_se_registra(api, sesion) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await _en_paris(sesion)

    respuesta = await cliente.post(_url(pedido, "eta-manual"), json={"eta": ETA.isoformat()})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["calculo"]["eta_manual"] == "2026-11-05"
    (asiento,) = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert asiento["motivo"] == "Sin motivo declarado."


@pytest.mark.parametrize("etapa", ["EN_DESTINO", "EN_PROCESO_ADUANAL"])
async def test_un_pedido_que_ya_llego_no_la_admite(api, sesion, etapa) -> None:
    cliente, como = api
    await como("COMPRAS")
    pedido = await base._rastreado(sesion, etapa)

    respuesta = await cliente.post(_url(pedido, "eta-manual"), json=_eta())

    assert respuesta.status_code == 409
    assert "ya llegó" in respuesta.json()["detail"]


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [("COMPRAS", 200), ("ADMINISTRADOR", 200), ("LOGISTICA", 403), ("PLANIFICACION", 403)],
)
async def test_la_registran_compras_y_el_administrador(api, sesion, rol, esperado) -> None:
    cliente, como = api
    if rol != "LOGISTICA":
        # La fixture ya entra como Logística.
        await como(rol)
    pedido = await _en_paris(sesion)

    respuesta = await cliente.post(_url(pedido, "eta-manual"), json=_eta())

    assert respuesta.status_code == esperado
