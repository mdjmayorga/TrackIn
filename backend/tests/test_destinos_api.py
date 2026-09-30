"""Pruebas de `/api/v1/destinos` — el maestro de destinos (`US-13`).

Los endpoints hacen `commit`. Aquí el cliente recibe la sesión de la prueba con
el `commit` convertido en `flush`: todo sigue dentro de la transacción que se
revierte al terminar, y la base de desarrollo queda intacta.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import get_db
from app.main import app
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services.ingesta.carga import resolver_destino

pytestmark = pytest.mark.integration

URL = "/api/v1/destinos"

QUEPOS = {
    "codigo": "CRXQP",
    "nombre": "Puerto Quepos",
    "pais": "CR",
    "via_transporte": "MARITIMO",
    "latitud": 9.4232,
    "longitud": -84.1662,
    "lead_time_dias": 6,
}


class _SinCommit:
    """La sesión de la prueba, con `commit` convertido en `flush`."""

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()


@pytest.fixture
async def api(sesion, como_rol) -> AsyncGenerator[AsyncClient, None]:
    """Cliente de Logística: el rol que mantiene el maestro (`US-42`)."""
    como_rol("LOGISTICA")

    async def _misma_sesion():
        yield _SinCommit(sesion)

    app.dependency_overrides[get_db] = _misma_sesion
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _crear(api, **cambios) -> dict[str, Any]:
    respuesta = await api.post(URL, json={**QUEPOS, **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


async def _pedido(sesion, id_destino: int, **kwargs) -> PedidoTransito:
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-DAPI-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-DAPI-1", nombre="Proveedor")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-DAPI-1"))
    if material is None:
        material = Material(codigo="M-DAPI-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()
    datos = {
        "oc_numero": "4577700001",
        "posicion_oc": 10,
        "tracking_interno": "TRK-4577700001-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": id_destino,
        "via_transporte": "MARITIMO",
        "cantidad_pedida": Decimal("1.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 11, 30),
        "lead_time_destino_dias": 6,
        "etapa_viaje": "SIN_TRACKING",
        "estado_calculado": "SIN_TRACKING",
        "eta_declarada": dt.date(2026, 11, 1),
    }
    datos.update(kwargs)
    pedido = PedidoTransito(**datos)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


# --- Primer criterio: el alta queda disponible ------------------------------


async def test_un_destino_nuevo_queda_disponible_para_la_ingesta(api, sesion) -> None:
    creado = await _crear(api, codigo="crxqp", pais="cr")

    assert creado["codigo"] == "CRXQP" and creado["pais"] == "CR"
    assert creado["activo"] is True and creado["pedidos_activos"] == 0
    assert creado["latitud"] == pytest.approx(9.4232)
    assert creado["longitud"] == pytest.approx(-84.1662)
    lista = (await api.get(URL)).json()
    assert "CRXQP" in {d["codigo"] for d in lista}
    # La ingesta ya lo resuelve por su código.
    destino, _ = await resolver_destino(sesion, "CRXQP", "MARITIMO")
    assert destino is not None and destino.id == creado["id"]


# --- Segundo criterio: el lead time dice qué formato espera -----------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(-1, "no puede ser negativo"), ("seis", "número entero de días"), (2.5, "número entero")],
)
async def test_un_lead_time_invalido_se_rechaza_con_el_formato_esperado(
    api, valor, esperado
) -> None:
    respuesta = await api.post(URL, json={**QUEPOS, "lead_time_dias": valor})

    assert respuesta.status_code == 422
    assert esperado in respuesta.text


async def test_tambien_al_editarlo(api) -> None:
    creado = await _crear(api)

    respuesta = await api.patch(f"{URL}/{creado['id']}", json={"lead_time_dias": -3})

    assert respuesta.status_code == 422
    assert "no puede ser negativo" in respuesta.text


# --- Tercer criterio: desactivar con pedidos activos pide confirmación ------


async def test_desactivar_con_pedidos_activos_advierte_y_pide_confirmacion(api, sesion) -> None:
    creado = await _crear(api)
    pedido = await _pedido(sesion, creado["id"])

    sin_confirmar = await api.patch(f"{URL}/{creado['id']}", json={"activo": False})

    assert sin_confirmar.status_code == 409
    cuerpo = sin_confirmar.json()
    assert cuerpo["pedidos_activos"] == 1 and cuerpo["requiere_confirmacion"] is True
    assert (await api.get(f"{URL}/{creado['id']}")).json()["activo"] is True

    confirmado = await api.patch(f"{URL}/{creado['id']}", json={"activo": False, "confirmar": True})

    assert confirmado.status_code == 200
    assert confirmado.json()["activo"] is False
    await sesion.refresh(pedido)
    assert pedido.id_destino == creado["id"]  # el pedido no se toca
    assert "CRXQP" not in {d["codigo"] for d in (await api.get(URL)).json()}
    todos = (await api.get(URL, params={"incluir_inactivos": True})).json()
    assert "CRXQP" in {d["codigo"] for d in todos}


async def test_sin_pedidos_activos_se_desactiva_sin_preguntar(api, sesion) -> None:
    creado = await _crear(api)
    await _pedido(sesion, creado["id"], estado_calculado="CANCELADO", motivo_cierre="CANCELACION")

    respuesta = await api.patch(f"{URL}/{creado['id']}", json={"activo": False})

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False


# --- Cuarto criterio: no hay duplicados --------------------------------------


async def test_el_mismo_nombre_en_la_misma_via_no_se_duplica(api) -> None:
    await _crear(api)

    otra_vez = await api.post(URL, json={**QUEPOS, "codigo": "CRQP2", "nombre": "puerto QUEPOS"})

    assert otra_vez.status_code == 409
    assert "Ya existe «Puerto Quepos» por vía MARITIMO" in otra_vez.json()["detail"]


async def test_el_mismo_codigo_no_se_duplica(api) -> None:
    await _crear(api)

    otra_vez = await api.post(URL, json={**QUEPOS, "nombre": "Otro nombre"})

    assert otra_vez.status_code == 409
    assert "código CRXQP" in otra_vez.json()["detail"]


async def test_el_mismo_nombre_en_otra_via_si_se_admite(api) -> None:
    await _crear(api)

    respuesta = await api.post(URL, json={**QUEPOS, "codigo": "MRXQP", "via_transporte": "AEREO"})

    assert respuesta.status_code == 201


async def test_renombrar_a_un_nombre_ocupado_tambien_se_impide(api) -> None:
    await _crear(api)
    otro = await _crear(api, codigo="CRXGO", nombre="Puerto Golfito")

    respuesta = await api.patch(f"{URL}/{otro['id']}", json={"nombre": "Puerto Quepos"})

    assert respuesta.status_code == 409


# --- Edición ------------------------------------------------------------------


async def test_cambiar_el_lead_time_recalcula_sus_pedidos(api, sesion) -> None:
    """El camino de `US-12`, ahora desde la API."""
    creado = await _crear(api)
    pedido = await _pedido(sesion, creado["id"])

    respuesta = await api.patch(f"{URL}/{creado['id']}", json={"lead_time_dias": 10})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["lead_time_dias"] == 10
    assert cuerpo["recalculo"].startswith("1 evaluados")
    await sesion.refresh(pedido)
    assert pedido.fecha_proyectada_disponible == dt.date(2026, 11, 11)


async def test_solo_cambia_lo_que_se_envia_y_el_radio_se_puede_borrar(api) -> None:
    creado = await _crear(api, radio_geocerca_km=15, observacion="Nota")

    respuesta = await api.patch(f"{URL}/{creado['id']}", json={"radio_geocerca_km": None})

    cuerpo = respuesta.json()
    assert cuerpo["radio_geocerca_km"] is None
    assert cuerpo["observacion"] == "Nota"
    assert cuerpo["lead_time_dias"] == 6
    assert cuerpo["recalculo"] is None


async def test_el_codigo_y_la_via_no_se_editan(api) -> None:
    creado = await _crear(api)

    await api.patch(f"{URL}/{creado['id']}", json={"codigo": "XXXXX", "via_transporte": "AEREO"})

    cuerpo = (await api.get(f"{URL}/{creado['id']}")).json()
    assert (cuerpo["codigo"], cuerpo["via_transporte"]) == ("CRXQP", "MARITIMO")


async def test_un_id_inexistente_da_404(api) -> None:
    assert (await api.get(f"{URL}/999999999")).status_code == 404
    assert (await api.patch(f"{URL}/999999999", json={"nombre": "X"})).status_code == 404


# --- Quién puede mantenerlo (`US-42`) -----------------------------------------


@pytest.mark.parametrize("rol", ["COMPRAS", "PLANIFICACION"])
async def test_leer_puede_cualquiera_pero_mantener_no(api, como_rol, rol) -> None:
    como_rol(rol)

    assert (await api.get(URL)).status_code == 200
    respuesta = await api.post(URL, json=QUEPOS)
    assert respuesta.status_code == 403
    assert rol in respuesta.json()["detail"]


async def test_el_administrador_tambien_mantiene(api, como_rol) -> None:
    como_rol("ADMINISTRADOR")

    assert (await api.post(URL, json=QUEPOS)).status_code == 201
