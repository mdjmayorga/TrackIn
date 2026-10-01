"""Pruebas de la bitácora de intervenciones — `US-15` / RF-14, RNF-06.

Los tres criterios, contra la base de verdad: que cada intervención guarde lo
que RF-14 exige, que un registro no se pueda alterar ni borrar, y que la
bitácora de un pedido se lea en orden cronológico.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.session import get_db
from app.main import app
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.services import auditoria
from app.services.auditoria import IntervencionInvalida

pytestmark = pytest.mark.integration

AHORA = dt.datetime(2026, 9, 30, 15, 0, tzinfo=dt.UTC)


async def _usuario(sesion, usuario: str = "logistica.audit", rol: str = "LOGISTICA") -> Usuario:
    cuenta = Usuario(
        usuario=usuario, nombre_completo="Logística Prueba", rol=rol, hash_contrasena="x"
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


async def _pedido(sesion) -> PedidoTransito:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    proveedor = Proveedor(codigo="P-AUD-1", nombre="Proveedor")
    material = Material(codigo="M-AUD-1", descripcion="Material", unidad_medida="KG")
    sesion.add_all([proveedor, material])
    await sesion.flush()
    pedido = PedidoTransito(
        oc_numero="4555500001",
        posicion_oc=10,
        tracking_interno="TRK-4555500001-010",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte="MARITIMO",
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        fecha_entrega_pedido=dt.date(2026, 10, 30),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        estado_calculado="SIN_TRACKING",
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def _intervencion(sesion, pedido, usuario, **cambios) -> AuditoriaIntervencion:
    datos = {
        "id_pedido": pedido.id,
        "id_usuario": usuario.id,
        "tipo": "AJUSTE_MANUAL",
        "campo": "ajuste_manual_dias",
        "anterior": 0,
        "nuevo": 3,
        "motivo": "El proveedor avisó de un retraso en el despacho",
    }
    datos.update(cambios)
    fila = auditoria.registrar(sesion, **datos)
    await sesion.flush()
    return fila


# --- Primer criterio: se registra lo que RF-14 exige --------------------------


async def test_registra_usuario_fecha_valores_y_motivo(sesion) -> None:
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)

    fila = await _intervencion(sesion, pedido, usuario)
    await sesion.refresh(fila)

    assert fila.id_usuario == usuario.id
    assert fila.fecha_hora is not None
    assert (fila.valor_anterior, fila.valor_nuevo) == ("0", "3")
    assert fila.motivo == "El proveedor avisó de un retraso en el despacho"


@pytest.mark.parametrize("motivo", ["", "   ", "ok", None])
async def test_sin_motivo_declarado_no_hay_intervencion(sesion, motivo) -> None:
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)

    with pytest.raises(IntervencionInvalida, match="motivo es obligatorio"):
        await _intervencion(sesion, pedido, usuario, motivo=motivo)


async def test_un_tipo_que_no_existe_se_rechaza(sesion) -> None:
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)

    with pytest.raises(IntervencionInvalida, match="desconocido"):
        await _intervencion(sesion, pedido, usuario, tipo="BORRADO")


async def test_los_valores_se_escriben_de_una_sola_manera(sesion) -> None:
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)

    fecha = await _intervencion(
        sesion, pedido, usuario, anterior=None, nuevo=dt.date(2026, 10, 5), campo="ata"
    )
    cantidad = await _intervencion(sesion, pedido, usuario, nuevo=Decimal("100.500"))
    booleano = await _intervencion(sesion, pedido, usuario, anterior=True, nuevo=False)

    assert (fecha.valor_anterior, fecha.valor_nuevo) == (None, "2026-10-05")
    assert cantidad.valor_nuevo == "100.5"
    assert (booleano.valor_anterior, booleano.valor_nuevo) == ("sí", "no")


# --- Segundo criterio: un registro no se altera --------------------------------


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE auditoria_intervenciones SET motivo = 'otra cosa' WHERE id = :id",
        "DELETE FROM auditoria_intervenciones WHERE id = :id",
        "TRUNCATE auditoria_intervenciones CASCADE",
    ],
)
async def test_la_base_rechaza_alterar_o_borrar_la_auditoria(sesion, sentencia) -> None:
    """Directo contra la base: tiene que fallar aunque no pase por el código."""
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)
    fila = await _intervencion(sesion, pedido, usuario)

    with pytest.raises(DBAPIError, match="auditoria_intervenciones es inmutable"):
        async with sesion.begin_nested():
            await sesion.execute(text(sentencia), {"id": fila.id})

    await sesion.refresh(fila)
    assert fila.motivo == "El proveedor avisó de un retraso en el despacho"


async def test_tampoco_por_el_orm(sesion) -> None:
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)
    fila = await _intervencion(sesion, pedido, usuario)

    with pytest.raises(DBAPIError, match="inmutable"):
        async with sesion.begin_nested():
            fila.valor_nuevo = "99"
            await sesion.flush()


# --- Tercer criterio: la bitácora, en orden cronológico ------------------------


@pytest.fixture
async def api(sesion, como_rol) -> AsyncGenerator[AsyncClient, None]:
    como_rol("PLANIFICACION")

    async def _misma_sesion():
        yield sesion

    app.dependency_overrides[get_db] = _misma_sesion
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_la_bitacora_sale_en_orden_cronologico_con_su_autor(api, sesion) -> None:
    logistica = await _usuario(sesion)
    compras = await _usuario(sesion, usuario="compras@gutis.com", rol="COMPRAS")
    pedido = await _pedido(sesion)
    # Se escriben desordenadas a propósito: manda la fecha, no el orden de alta.
    await _intervencion(sesion, pedido, logistica, instante=AHORA + dt.timedelta(hours=2), nuevo=5)
    await _intervencion(
        sesion,
        pedido,
        compras,
        instante=AHORA,
        tipo="ASOCIACION_TRACKING",
        campo="id_elemento_rastreado",
        anterior=None,
        nuevo="BL:COSU6508789000",
        motivo="BL recibido del proveedor",
    )

    respuesta = await api.get(f"/api/v1/pedidos/{pedido.id}/bitacora")

    assert respuesta.status_code == 200
    asientos = respuesta.json()
    assert [a["tipo"] for a in asientos] == ["ASOCIACION_TRACKING", "AJUSTE_MANUAL"]
    primero = asientos[0]
    assert primero["usuario"] == "compras@gutis.com" and primero["rol"] == "COMPRAS"
    assert primero["valor_nuevo"] == "BL:COSU6508789000"
    assert primero["motivo"] == "BL recibido del proveedor"


async def test_un_pedido_sin_intervenciones_tiene_la_bitacora_vacia(api, sesion) -> None:
    pedido = await _pedido(sesion)

    assert (await api.get(f"/api/v1/pedidos/{pedido.id}/bitacora")).json() == []


async def test_la_bitacora_de_un_pedido_que_no_existe_da_404(api) -> None:
    assert (await api.get("/api/v1/pedidos/999999999/bitacora")).status_code == 404


async def test_una_fecha_con_hora_se_escribe_siempre_en_utc(sesion) -> None:
    """El mismo instante, venga con la zona de Costa Rica o de la base."""
    usuario = await _usuario(sesion)
    pedido = await _pedido(sesion)
    costa_rica = dt.timezone(dt.timedelta(hours=-6))

    fila = await _intervencion(
        sesion, pedido, usuario, anterior=dt.datetime(2026, 9, 22, 8, 15, tzinfo=costa_rica)
    )

    assert fila.valor_anterior == "2026-09-22T14:15:00+00:00"
