"""Los transbordos — `US-30`, replanteada el 22/10/2026.

Lo automático: ShipsGo informa el cambio de nave y se registra una vez por
embarque, con su puerto y su fecha; el detalle y la bitácora lo muestran a todas
las líneas del BL. Lo manual, solo la excepción: pasar de la guía hija a la
guía madre que resolvió TICA. Reutiliza los datos de `test_intervenciones`.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from sqlalchemy import select

import test_intervenciones as base
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado
from app.models.transbordo import Transbordo
from app.services import intervenciones, transbordos
from app.services.rastreo import colector_shipsgo
from app.services.rastreo.shipsgo import CambioDeVehiculo, Hito, LecturaEmbarque, interpretar

pytestmark = pytest.mark.integration

#: El cliente con un usuario real y `como(rol)`, el mismo de las intervenciones.
api = base.api
_url = base._url

CR = dt.timezone(dt.timedelta(hours=-6))
CARTAGENA = dt.datetime(2026, 9, 7, 12, tzinfo=CR)
MANZANILLO = dt.datetime(2026, 9, 13, 12, tzinfo=CR)

_SPIKE = (
    Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output/06_payload_personal.json"
)


def _hito(evento: str, buque: str | None, puerto: str, instante: dt.datetime, ocurrido=True):
    return Hito(
        evento=evento,
        ocurrido=ocurrido,
        instante=instante,
        puerto=puerto,
        puerto_nombre={"COCTG": "CARTAGENA", "PAMIT": "MANZANILLO"}.get(puerto, puerto),
        buque=buque,
        imo=None,
    )


def _cambio(anterior: str, nuevo: str, ocurrido: bool = True) -> CambioDeVehiculo:
    return CambioDeVehiculo(
        anterior=anterior,
        nuevo=nuevo,
        puerto="COCTG",
        puerto_nombre="CARTAGENA",
        instante=CARTAGENA,
        ocurrido=ocurrido,
    )


async def _bl(sesion, referencia: str = "MAEU123456789") -> ElementoRastreado:
    elemento = ElementoRastreado(
        tipo_tracking_externo="BL", tracking_externo=referencia, via_transporte="MARITIMO"
    )
    sesion.add(elemento)
    await sesion.flush()
    return elemento


# --- La detección ----------------------------------------------------------------------------


def test_un_cambio_de_nave_es_un_transbordo_con_su_puerto_y_su_fecha() -> None:
    lectura = LecturaEmbarque(
        hitos=[
            _hito("LOAD", "MAERSK CHACHAI", "CNSHA", CARTAGENA - dt.timedelta(days=20)),
            _hito("GTOT", None, "COCTG", CARTAGENA - dt.timedelta(days=1)),
            _hito("DEPA", "MAERSK NACALA", "COCTG", CARTAGENA),
            _hito("DEPA", "MAERSK MONTE PASCOAL", "PAMIT", MANZANILLO, ocurrido=False),
        ]
    )

    cambios = lectura.transbordos

    assert [(c.anterior, c.nuevo, c.puerto, c.ocurrido) for c in cambios] == [
        ("MAERSK CHACHAI", "MAERSK NACALA", "COCTG", True),
        ("MAERSK NACALA", "MAERSK MONTE PASCOAL", "PAMIT", False),
    ]
    assert cambios[0].instante == CARTAGENA


@pytest.mark.skipif(not _SPIKE.exists(), reason="falta el payload grabado del spike TASK-28")
def test_el_envio_real_de_tres_naves_da_dos_transbordos() -> None:
    """`MRSU8132490`, medido en el spike: Cartagena y Manzanillo (Panamá)."""
    datos = json.loads(_SPIKE.read_text(encoding="utf-8"))
    embarque = next(
        e for e in datos["embarques"] if "MRSU8132490" in json.dumps(e.get("payload_shipment", {}))
    )

    lectura = interpretar(embarque["payload_shipment"], embarque.get("payload_geojson"))

    assert [(c.nuevo, c.puerto) for c in lectura.transbordos] == [
        ("MAERSK NACALA", "COCTG"),
        ("MAERSK MONTE PASCOAL", "PAMIT"),
    ]


# --- El registro, una vez por embarque -------------------------------------------------------


async def test_se_registra_una_sola_vez_y_lo_previsto_se_actualiza(sesion) -> None:
    elemento = await _bl(sesion)

    primera = await transbordos.registrar(
        sesion, elemento, [_cambio("MAERSK CHACHAI", "MAERSK NACALA", ocurrido=False)]
    )
    segunda = await transbordos.registrar(
        sesion, elemento, [_cambio("MAERSK CHACHAI", "MAERSK NACALA", ocurrido=True)]
    )

    filas = await transbordos.del_elemento(sesion, elemento.id)
    assert (primera, segunda) == (1, 0)
    assert len(filas) == 1
    assert filas[0].ocurrido is True
    assert (filas[0].puerto, filas[0].puerto_nombre) == ("COCTG", "CARTAGENA")


@pytest.mark.skipif(not _SPIKE.exists(), reason="falta el payload grabado del spike TASK-28")
async def test_el_colector_registra_los_transbordos_del_envio(sesion) -> None:
    datos = json.loads(_SPIKE.read_text(encoding="utf-8"))
    embarque = next(
        e for e in datos["embarques"] if "MRSU8132490" in json.dumps(e.get("payload_shipment", {}))
    )
    elemento = await _bl(sesion, "MRSU8132490")

    for _ in range(2):  # dos consultas del worker
        await colector_shipsgo.procesar(
            sesion, elemento, embarque["payload_shipment"], embarque.get("payload_geojson")
        )

    filas = await sesion.scalars(
        select(Transbordo).where(Transbordo.id_elemento_rastreado == elemento.id)
    )
    assert [t.vehiculo_nuevo for t in filas] == ["MAERSK NACALA", "MAERSK MONTE PASCOAL"]


# --- El detalle y la bitácora ------------------------------------------------------------------


async def test_todas_las_lineas_del_bl_lo_ven_en_el_detalle_y_la_bitacora(api, sesion) -> None:
    cliente, _ = api
    elemento = await _bl(sesion)
    una = await base._pedido(sesion, id_elemento_rastreado=elemento.id, etapa_viaje="EN_TRANSITO")
    otra = await base._pedido(
        sesion,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_TRANSITO",
        posicion_oc=20,
        tracking_interno="TRK-4544400001-020",
    )
    await transbordos.registrar(
        sesion,
        elemento,
        [
            _cambio("MAERSK CHACHAI", "MAERSK NACALA"),
            _cambio("MAERSK NACALA", "MAERSK MONTE PASCOAL", ocurrido=False),
        ],
    )

    for pedido in (una, otra):
        rastreo = (await cliente.get(f"/api/v1/pedidos/{pedido.id}")).json()["rastreo"]
        assert [t["vehiculo_nuevo"] for t in rastreo["transbordos"]] == [
            "MAERSK NACALA",
            "MAERSK MONTE PASCOAL",
        ]
        bitacora = (await cliente.get(_url(pedido, "bitacora"))).json()
        # En la línea de tiempo, solo el que ya ocurrió.
        (asiento,) = (a for a in bitacora if a["tipo"] == "TRANSBORDO")
        assert (asiento["valor_anterior"], asiento["valor_nuevo"]) == (
            "MAERSK CHACHAI",
            "MAERSK NACALA",
        )
        assert asiento["rol"] == "SISTEMA"
        assert asiento["motivo"] == "Informado por ShipsGo en CARTAGENA."


# --- La excepción manual: de la guía hija a la madre ------------------------------------------


async def _con_guia_hija(sesion, guia_madre: str | None = "176-12345675"):
    aeropuerto = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "MROC"))
    hija = ElementoRastreado(
        tipo_tracking_externo="HAWB",
        tracking_externo="ZIVHYD017",
        via_transporte="AEREO",
        guia_madre=guia_madre,
    )
    sesion.add(hija)
    await sesion.flush()
    pedido = await base._pedido(
        sesion,
        id_destino=aeropuerto.id,
        via_transporte="AEREO",
        lead_time_destino_dias=aeropuerto.lead_time_dias,
        id_elemento_rastreado=hija.id,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="EN_TRANSITO",
    )
    return pedido, hija


async def test_sigue_por_la_guia_madre_conservando_el_tramo_de_la_hija(api, sesion) -> None:
    cliente, _ = api
    pedido, hija = await _con_guia_hija(sesion)

    respuesta = await cliente.post(_url(pedido, "guia-madre"), json={})

    assert respuesta.status_code == 200, respuesta.text
    rastreo = respuesta.json()["rastreo"]
    assert (rastreo["tipo"], rastreo["referencia"]) == ("MAWB", "176-12345675")
    tramos = list(
        await sesion.scalars(
            select(PedidoElementoRastreado)
            .where(PedidoElementoRastreado.id_pedido == pedido.id)
            .order_by(PedidoElementoRastreado.tramo)
        )
    )
    assert [(t.tramo, t.id_elemento_rastreado == hija.id) for t in tramos] == [
        (1, True),
        (2, False),
    ]
    assert tramos[0].fecha_hasta is not None and tramos[1].fecha_hasta is None
    asiento = await sesion.scalar(
        select(AuditoriaIntervencion).where(
            AuditoriaIntervencion.id_pedido == pedido.id,
            AuditoriaIntervencion.tipo_intervencion == "TRANSBORDO",
        )
    )
    assert asiento is not None
    assert (asiento.valor_anterior, asiento.valor_nuevo) == (
        "HAWB:ZIVHYD017",
        "MAWB:176-12345675",
    )
    assert asiento.motivo == intervenciones.MOTIVO_GUIA_MADRE_POR_OMISION


async def test_sin_guia_madre_resuelta_no_se_puede(api, sesion) -> None:
    cliente, _ = api
    pedido, _ = await _con_guia_hija(sesion, guia_madre=None)

    respuesta = await cliente.post(_url(pedido, "guia-madre"), json={})

    assert respuesta.status_code == 409
    assert "TICA todavía no resolvió" in respuesta.json()["detail"]


async def test_un_pedido_que_no_va_por_guia_hija_no_tiene_guia_madre(api, sesion) -> None:
    cliente, _ = api
    elemento = await _bl(sesion)
    pedido = await base._pedido(
        sesion, id_elemento_rastreado=elemento.id, etapa_viaje="EN_TRANSITO"
    )

    assert (await cliente.post(_url(pedido, "guia-madre"), json={})).status_code == 409


@pytest.mark.parametrize(("rol", "esperado"), [("COMPRAS", 200), ("PLANIFICACION", 403)])
async def test_lo_hacen_quienes_asocian_referencias(api, sesion, rol, esperado) -> None:
    cliente, como = api
    await como(rol)
    pedido, _ = await _con_guia_hija(sesion)

    assert (await cliente.post(_url(pedido, "guia-madre"), json={})).status_code == esperado
