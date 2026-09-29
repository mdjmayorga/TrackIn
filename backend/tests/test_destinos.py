"""Pruebas de `app.services.destinos` — el lead time del maestro (`US-12`)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services.destinos import LeadTimeInvalido, cambiar_lead_time, validar_lead_time


@pytest.mark.parametrize("valor", [0, 3, 30])
def test_acepta_dias_enteros_no_negativos(valor) -> None:
    assert validar_lead_time(valor) == valor


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (-1, "negativo"),
        (2.5, "número entero de días"),
        ("3", "número entero de días"),
        (None, "número entero de días"),
        (True, "número entero de días"),
    ],
)
def test_rechaza_lo_que_no_es_un_lead_time_y_dice_que_esperaba(valor, esperado) -> None:
    with pytest.raises(LeadTimeInvalido, match=esperado):
        validar_lead_time(valor)


# --- Contra la base ---------------------------------------------------------


async def _destino(sesion, codigo: str) -> MaestroDestino:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == codigo))
    assert destino is not None
    return destino


async def _pedido(sesion, destino: MaestroDestino, posicion: int, **kwargs) -> PedidoTransito:
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-DST-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-DST-1", nombre="Proveedor")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-DST-1"))
    if material is None:
        material = Material(codigo="M-DST-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()
    datos = {"estado_calculado": "SIN_TRACKING", **kwargs}
    pedido = PedidoTransito(
        oc_numero="4566600001",
        posicion_oc=posicion,
        tracking_interno=f"TRK-4566600001-{posicion:03d}",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte=destino.via_transporte,
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        fecha_entrega_pedido=dt.date(2026, 10, 30),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        eta_declarada=dt.date(2026, 10, 1),
        **datos,
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido


@pytest.fixture
async def sin_pedidos(sesion):
    await sesion.execute(delete(PedidoTransito))
    await sesion.flush()
    return sesion


@pytest.mark.integration
async def test_cambiar_el_lead_time_recalcula_los_activos_del_destino(sesion, sin_pedidos) -> None:
    moin = await _destino(sesion, "CRMOB")
    caldera = await _destino(sesion, "CRCAL")
    activo = await _pedido(sesion, moin, 10)
    cerrado = await _pedido(
        sesion, moin, 20, estado_calculado="CANCELADO", motivo_cierre="CANCELACION"
    )
    otro_destino = await _pedido(sesion, caldera, 30)
    nuevo = moin.lead_time_dias + 5

    cambio = await cambiar_lead_time(sesion, moin.id, nuevo)

    assert (cambio.destino, cambio.nuevo) == ("CRMOB", nuevo)
    assert cambio.recalculo is not None and cambio.recalculo.evaluados == 1
    assert moin.lead_time_dias == nuevo
    assert activo.lead_time_destino_dias == nuevo
    assert activo.fecha_proyectada_disponible == dt.date(2026, 10, 1) + dt.timedelta(days=nuevo)
    # RN-13: el cerrado no se toca. El de otro destino, tampoco.
    assert cerrado.fecha_proyectada_disponible is None
    assert otro_destino.fecha_proyectada_disponible is None


@pytest.mark.integration
async def test_el_mismo_valor_no_recalcula(sesion, sin_pedidos) -> None:
    moin = await _destino(sesion, "CRMOB")

    cambio = await cambiar_lead_time(sesion, moin.id, moin.lead_time_dias)

    assert cambio.recalculo is None


@pytest.mark.integration
async def test_un_valor_invalido_no_toca_el_maestro(sesion) -> None:
    moin = await _destino(sesion, "CRMOB")
    antes = moin.lead_time_dias

    with pytest.raises(LeadTimeInvalido):
        await cambiar_lead_time(sesion, moin.id, -2)

    assert moin.lead_time_dias == antes


@pytest.mark.integration
async def test_un_destino_inexistente_se_informa(sesion) -> None:
    with pytest.raises(LookupError, match="No existe el destino 999999"):
        await cambiar_lead_time(sesion, 999999, 3)
