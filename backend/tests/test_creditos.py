"""Saldo de créditos de ShipsGo y sus avisos — `US-57`.

El saldo se calcula: lo disponible del paquete vigente menos las altas que costaron
desde que se registró, según la auditoría (RF-14). Las fechas caen en octubre y
noviembre de 2026, en hora de Costa Rica.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import get_db
from app.main import app
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.paquete_creditos import PaqueteCreditos
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import creditos
from app.services.rastreo.registro_embarque import (
    CAMPO_ALTA_CON_CREDITO,
    CAMPO_ALTA_SIN_COSTO,
    TIPO_INTERVENCION,
)
from conftest import vaciar_auditoria

pytestmark = pytest.mark.integration

ZONA = creditos.ZONA_CR
COMPRA = dt.datetime(2026, 11, 6, 9, 0, tzinfo=ZONA)


class _SinCommit:
    """La sesión de la prueba con `commit` convertido en `flush` (ver `test_altas_api`)."""

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()


@pytest.fixture
async def base(sesion) -> tuple[Usuario, PedidoTransito]:
    """Sin paquetes ni auditoría, con una cuenta de Compras y un pedido para auditar."""
    await vaciar_auditoria(sesion)
    await sesion.execute(delete(PaqueteCreditos))
    cuenta = Usuario(
        usuario="compras.creditos", nombre_completo="Compras", rol="COMPRAS", hash_contrasena="x"
    )
    proveedor = Proveedor(codigo="P-CRED", nombre="Proveedor")
    material = Material(codigo="M-CRED", descripcion="Material", unidad_medida="KG")
    sesion.add_all([cuenta, proveedor, material])
    await sesion.flush()
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    pedido = PedidoTransito(
        oc_numero="4588880001",
        posicion_oc=10,
        tracking_interno="TRK-CRED-10",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte="MARITIMO",
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        fecha_entrega_pedido=dt.date(2026, 12, 1),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        estado_calculado="SIN_TRACKING",
    )
    sesion.add(pedido)
    await sesion.flush()
    return cuenta, pedido


async def _altas(sesion, base, cuantas: int, cuando: dt.datetime, campo=CAMPO_ALTA_CON_CREDITO):
    cuenta, pedido = base
    for _ in range(cuantas):
        sesion.add(
            AuditoriaIntervencion(
                id_pedido=pedido.id,
                id_usuario=cuenta.id,
                fecha_hora=cuando,
                tipo_intervencion=TIPO_INTERVENCION,
                campo_afectado=campo,
                valor_nuevo="1",
                motivo="Alta de prueba",
            )
        )
    await sesion.flush()


async def _paquete(sesion, base, cantidad: int, **extra) -> PaqueteCreditos:
    cuenta, _ = base
    datos: dict[str, Any] = {
        "comprado_en": COMPRA.date(),
        "vence_en": None,
        "instante": COMPRA,
        **extra,
    }
    return await creditos.registrar_paquete(
        sesion, cantidad=cantidad, id_usuario=cuenta.id, **datos
    )


# --- El saldo --------------------------------------------------------------------


async def test_sin_paquete_lo_dice(sesion, base) -> None:
    estado = await creditos.estado(sesion, instante=COMPRA)

    assert estado.nivel == "SIN_PAQUETE"
    assert estado.paquete is None


async def test_el_saldo_descuenta_solo_las_altas_que_costaron_desde_el_registro(
    sesion, base
) -> None:
    await _altas(sesion, base, 3, COMPRA - dt.timedelta(days=1))  # del paquete anterior
    await _paquete(sesion, base, 49)
    despues = COMPRA + dt.timedelta(hours=2)
    await _altas(sesion, base, 2, despues)
    await _altas(sesion, base, 4, despues, campo=CAMPO_ALTA_SIN_COSTO)  # 409: gratis
    await _altas(sesion, base, 1, despues, campo="id_elemento_rastreado")  # asociación manual

    estado = await creditos.estado(sesion, instante=despues)

    assert (estado.nivel, estado.disponible, estado.consumidos, estado.saldo) == ("OK", 49, 2, 47)


@pytest.mark.parametrize(
    ("usadas", "nivel"), [(7, "OK"), (8, "BAJO"), (9, "BAJO"), (10, "AGOTADO"), (11, "AGOTADO")]
)
async def test_avisa_al_ochenta_por_ciento_y_al_agotarse(sesion, base, usadas, nivel) -> None:
    await _paquete(sesion, base, 10)
    await _altas(sesion, base, usadas, COMPRA + dt.timedelta(hours=1))

    assert (await creditos.estado(sesion, instante=COMPRA + dt.timedelta(days=1))).nivel == nivel


async def test_avisa_a_sesenta_dias_del_vencimiento_cuanto_se_arrastraria(sesion, base) -> None:
    await _paquete(sesion, base, 1100, vence_en=dt.date(2027, 11, 6))

    lejos = await creditos.estado(sesion, instante=dt.datetime(2027, 8, 1, tzinfo=ZONA))
    cerca = await creditos.estado(sesion, instante=dt.datetime(2027, 9, 10, tzinfo=ZONA))

    assert lejos.nivel == "OK"
    assert cerca.nivel == "POR_VENCER"
    assert cerca.dias_para_vencer == 57
    assert "al menos 550" in cerca.mensaje


async def test_un_paquete_vencido_lo_dice(sesion, base) -> None:
    await _paquete(sesion, base, 1100, vence_en=dt.date(2027, 11, 6))

    estado = await creditos.estado(sesion, instante=dt.datetime(2027, 11, 7, 8, tzinfo=ZONA))

    assert estado.nivel == "VENCIDO"


# --- El arrastre: la condición de ShipsGo del 07/10/2026 -------------------------


async def test_los_49_de_prueba_se_suman_al_paquete_de_1100(sesion, base) -> None:
    """Confirmado con ShipsGo el 07/10: lo que sobre de los 49 pasa al paquete anual."""
    await _paquete(sesion, base, 49)
    await _altas(sesion, base, 9, COMPRA + dt.timedelta(hours=1))
    nueva = COMPRA + dt.timedelta(days=1)

    paquete = await _paquete(sesion, base, 1100, comprado_en=nueva.date(), instante=nueva)
    estado = await creditos.estado(sesion, instante=nueva + dt.timedelta(hours=1))

    assert paquete.saldo_arrastrado == 40
    assert (estado.disponible, estado.saldo) == (1140, 1140)


@pytest.mark.parametrize(("recompra", "arrastrado"), [(549, 0), (550, 100)])
async def test_solo_se_arrastra_si_la_recompra_es_de_la_mitad(
    sesion, base, recompra, arrastrado
) -> None:
    await _paquete(sesion, base, 1100)
    await _altas(sesion, base, 1000, COMPRA + dt.timedelta(hours=1))
    nueva = COMPRA + dt.timedelta(days=300)

    paquete = await _paquete(sesion, base, recompra, comprado_en=nueva.date(), instante=nueva)

    assert paquete.saldo_arrastrado == arrastrado


async def test_un_paquete_vencido_no_se_arrastra(sesion, base) -> None:
    await _paquete(sesion, base, 1100, vence_en=dt.date(2027, 11, 6))
    nueva = dt.datetime(2027, 11, 20, tzinfo=ZONA)

    paquete = await _paquete(sesion, base, 1100, comprado_en=nueva.date(), instante=nueva)

    assert paquete.saldo_arrastrado == 0


async def test_al_registrar_puede_subir_el_tope_diario(sesion, base) -> None:
    await _paquete(sesion, base, 1100, altas_maximas_dia=30)

    fila = await sesion.get(ParametroSistema, "altas_maximas_dia")
    assert fila is not None and fila.valor == "30"


# --- La API y `/health` ------------------------------------------------------------


@pytest.fixture
async def api(sesion, base) -> AsyncGenerator[AsyncClient, None]:
    cuenta, _ = base

    async def _misma_sesion():
        yield _SinCommit(sesion)

    app.dependency_overrides[get_db] = _misma_sesion
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=cuenta, sesion=Sesion(id=0, id_usuario=cuenta.id)
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(usuario_actual, None)


async def test_compras_registra_el_paquete_y_ve_el_saldo(api) -> None:
    registro = await api.post(
        "/api/v1/shipsgo/creditos/paquetes",
        json={"cantidad": 49, "comprado_en": "2026-09-23", "nota": "Créditos de prueba"},
    )

    assert registro.status_code == 201, registro.text
    cuerpo = (await api.get("/api/v1/shipsgo/creditos")).json()
    assert (cuerpo["nivel"], cuerpo["saldo"], cuerpo["recompra_minima"]) == ("OK", 49, 25)
    assert cuerpo["paquete"]["registrado_por"] == "Compras"


async def test_un_vencimiento_anterior_a_la_compra_se_rechaza(api) -> None:
    respuesta = await api.post(
        "/api/v1/shipsgo/creditos/paquetes",
        json={"cantidad": 1100, "comprado_en": "2026-11-06", "vence_en": "2026-11-01"},
    )

    assert respuesta.status_code == 422


@pytest.mark.parametrize("rol", ["LOGISTICA", "PLANTA"])
async def test_solo_compras_y_el_administrador_ven_los_creditos(api, sesion, rol) -> None:
    otra = Usuario(usuario=f"{rol.lower()}.cred", nombre_completo=rol, rol=rol, hash_contrasena="x")
    sesion.add(otra)
    await sesion.flush()
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=otra, sesion=Sesion(id=0, id_usuario=otra.id)
    )

    assert (await api.get("/api/v1/shipsgo/creditos")).status_code == 403
    assert (
        await api.post(
            "/api/v1/shipsgo/creditos/paquetes", json={"cantidad": 1, "comprado_en": "2026-11-06"}
        )
    ).status_code == 403


async def test_health_publica_el_nivel_de_los_creditos(api, sesion, base) -> None:
    # `/health` mira el saldo de ahora: el paquete se registra antes de las altas.
    hace_un_rato = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    await _paquete(sesion, base, 10, comprado_en=hace_un_rato.date(), instante=hace_un_rato)
    await _altas(sesion, base, 9, dt.datetime.now(dt.UTC))

    cuerpo = (await api.get("/health")).json()

    assert cuerpo["creditos_shipsgo"]["nivel"] == "BAJO"
    assert cuerpo["creditos_shipsgo"]["saldo"] == 1
