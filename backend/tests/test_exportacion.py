"""El Excel con los pedidos de la grilla — `US-68`.

Lo que importa es la vuelta completa: lo que se descarga se vuelve a cargar en
otro equipo y queda igual. «Otro equipo» es la misma base sin pedidos ni
referencias, y sin ShipsGo (`resolutor_de_destinos` anulado en el fixture).
"""

from __future__ import annotations

import datetime as dt
import io
from typing import Any

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

import test_cargas_api as cargas
import test_pedidos_api as base
from app.api.dependencias import Autenticado, usuario_actual
from app.main import app
from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.models.sesion import Sesion
from app.services.ingesta import plantilla
from app.services.ingesta.ztracking import PLANTILLA
from test_cargas_api import _subir, _usuario

pytestmark = pytest.mark.integration

#: El cliente de Compras sin pedidos y sin ShipsGo, el de las pruebas de la carga.
api = cargas.api

URL = "/api/v1/cargas/exportacion"


def _ztracking(*lineas: dict[str, Any]) -> bytes:
    """La plantilla de `US-59` llenada, como la llenaría Compras."""
    libro = plantilla.libro_plantilla()
    hoja = libro["PRODUCCION"]
    for numero, linea in enumerate(lineas, start=2):
        for columna, (campo, _) in enumerate(PLANTILLA, start=1):
            hoja.cell(row=numero, column=columna, value=linea.get(campo))
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _linea(**valores: Any) -> dict[str, Any]:
    return {
        "oc_numero": "4500016174",
        "posicion_oc": 20,
        "proveedor_codigo": "1007052",
        "proveedor_nombre": "ROUSSELOT GELATINAS DO BRASIL LTDA",
        "material_codigo": "11000371",
        "material_descripcion": "Colágeno hidrolizado bovino",
        "cantidad": 15000000,
        "unidad_medida": "G",
        "fecha_entrega_pedido": dt.datetime(2026, 11, 13),
        "via_transporte": "MARITIMO",
        "incoterm": "CIF LIMON",
        "pais_origen": "BRASIL",
        "eta_declarada": dt.datetime(2026, 11, 20),
        "solicitud_pedido": "1000029502",
        "tipo_referencia": "BL",
        "numero_referencia": "MAEU275293933",
        **valores,
    }


_LINEAS = (
    _linea(),
    # Otro puerto y otro tipo de referencia; sin ETA ni país.
    _linea(
        oc_numero="4500016175",
        posicion_oc=10,
        incoterm="CIF CALDERA",
        tipo_referencia="CONTENEDOR",
        numero_referencia="MSCU1234566",
        eta_declarada="PENDIENTE",
        pais_origen=None,
    ),
    # Aéreo: «AWB», como lo escribe Compras; la carga deduce la guía madre.
    _linea(
        oc_numero="4500016176",
        posicion_oc=10,
        via_transporte="AEREO",
        incoterm="CIP",
        tipo_referencia="AWB",
        numero_referencia="020-50685434",
        cantidad=2.5,
        unidad_medida="KG",
    ),
)


async def _foto(sesion) -> list[tuple[Any, ...]]:
    """Lo que el archivo puede decir de cada pedido, para comparar antes y después."""
    pedidos = await sesion.scalars(
        select(PedidoTransito)
        .options(
            selectinload(PedidoTransito.proveedor),
            selectinload(PedidoTransito.material),
            selectinload(PedidoTransito.destino),
            selectinload(PedidoTransito.pais_origen),
            selectinload(PedidoTransito.elemento_rastreado),
        )
        .where(PedidoTransito.motivo_cierre.is_(None))
        .order_by(PedidoTransito.oc_numero, PedidoTransito.posicion_oc)
        .execution_options(populate_existing=True)
    )
    return [
        (
            p.oc_numero,
            p.posicion_oc,
            p.proveedor.codigo,
            p.material.codigo,
            p.cantidad_pedida,
            p.unidad_medida,
            p.fecha_entrega_pedido,
            p.via_transporte,
            p.incoterm,
            p.destino.codigo,
            p.pais_origen.nombre if p.pais_origen else None,
            p.eta_declarada,
            p.solicitud_pedido,
            p.elemento_rastreado.tipo_tracking_externo if p.elemento_rastreado else None,
            p.elemento_rastreado.tracking_externo if p.elemento_rastreado else None,
        )
        for p in pedidos
    ]


async def test_lo_descargado_se_vuelve_a_cargar_en_otro_equipo_y_queda_igual(api, sesion):
    cliente, _ = api
    assert (await _subir(cliente, _ztracking(*_LINEAS))).json()["insertadas"] == 3
    antes = await _foto(sesion)

    respuesta = await cliente.get(URL)
    assert respuesta.status_code == 200, respuesta.text

    # «Otro equipo»: ni pedidos ni referencias, y sin ShipsGo.
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    carga = (await _subir(cliente, respuesta.content, "exportado.xlsx")).json()

    assert (carga["recibidas"], carga["insertadas"], carga["no_entraron"]) == (3, 3, 0)
    assert carga["incidencias"] == []
    # El archivo tiene la estructura de la plantilla: sin avisos de columnas.
    assert [a for a in carga["avisos"] if a["tipo"] == "estructura"] == []
    assert await _foto(sesion) == antes
    # El incoterm se guarda sin el puerto, pero el destino se resolvió con él.
    assert [(f[8], f[9]) for f in antes] == [("CIF", "CRLIO"), ("CIF", "CRCAL"), ("CIP", "MROC")]


async def test_la_grilla_va_primero_y_dice_lo_mismo_que_el_panel(api, sesion):
    cliente, _ = api
    await _subir(cliente, _ztracking(*_LINEAS))
    # Un pedido de antes del 04/11, sin referencia: está en la grilla.
    await base._pedido(sesion, "4500099999", 10)

    respuesta = await cliente.get(URL)

    assert respuesta.headers["content-disposition"].startswith(
        'attachment; filename="TrackIn pedidos '
    )
    libro = load_workbook(io.BytesIO(respuesta.content))
    assert libro.sheetnames == ["Grilla", "PRODUCCION", "IDA", "INSTRUCCIONES"]
    assert libro.active.title == "Grilla"

    filas = list(libro["Grilla"].iter_rows(values_only=True))
    assert filas[0] == (
        "Material",
        "Etapa",
        "Cumplimiento",
        "OC",
        "POS",
        "F. Proyectada",
        "F. Comprometida",
        "Vía",
        "Destino",
    )
    por_oc = {fila[3]: fila for fila in filas[1:]}
    assert set(por_oc) == {"4500016174", "4500016175", "4500016176", "4500099999"}
    maritimo = por_oc["4500016174"]
    assert maritimo[0] == "11000371 Colágeno hidrolizado bovino"
    assert (maritimo[4], maritimo[6], maritimo[7]) == (20, dt.datetime(2026, 11, 13), "Marítimo")
    # Como el panel: el aeropuerto por su código, el puerto por su nombre.
    assert por_oc["4500016176"][8] == "MROC"
    assert por_oc["4500099999"][1] == "Sin Tracking"

    # Sin referencia, la carga lo rechazaría: no va en la hoja que se carga.
    cargables = [fila[0] for fila in libro["PRODUCCION"].iter_rows(min_row=2, values_only=True)]
    assert sorted(c for c in cargables if c) == ["4500016174", "4500016175", "4500016176"]


async def test_el_aereo_va_como_awb_y_el_maritimo_con_su_puerto(api, sesion):
    cliente, _ = api
    await _subir(cliente, _ztracking(*_LINEAS))

    libro = load_workbook(io.BytesIO((await cliente.get(URL)).content))

    campos = [campo for campo, _ in PLANTILLA]
    filas = {
        fila[0]: dict(zip(campos, fila, strict=False))
        for fila in libro["PRODUCCION"].iter_rows(min_row=2, values_only=True)
        if fila[0]
    }
    assert filas["4500016174"]["incoterm"] == "CIF LIMON"
    assert filas["4500016175"]["incoterm"] == "CIF CALDERA"
    assert (filas["4500016176"]["incoterm"], filas["4500016176"]["tipo_referencia"]) == (
        "CIP",
        "AWB",
    )
    assert filas["4500016175"]["eta_declarada"] is None


@pytest.mark.parametrize("rol", ["LOGISTICA", "PLANIFICACION", "PLANTA"])
async def test_los_demas_roles_no_descargan_los_pedidos(api, sesion, rol):
    cliente, _ = api
    otro = await _usuario(sesion, rol)
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=otro, sesion=Sesion(id=0, id_usuario=otro.id)
    )

    assert (await cliente.get(URL)).status_code == 403
