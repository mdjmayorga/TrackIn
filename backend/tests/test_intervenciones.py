"""Pruebas de `US-14`: confirmar el desembarco y pasar a proceso aduanal.

La auditoría exige un usuario que exista (FK), así que aquí la API ve a un
usuario de Logística **real**, creado dentro de la transacción de la prueba.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import get_db
from app.main import app
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import arribo
from app.workers import rastreo

pytestmark = pytest.mark.integration

#: La llegada que se confirma: un martes de la semana pasada, hora de Costa Rica.
LLEGADA = dt.datetime(2026, 9, 22, 8, 15, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
MOTIVO = "La naviera no reportó la descarga; confirmado con el agente aduanal"


class _SinCommit:
    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()


async def _usuario(sesion, rol: str = "LOGISTICA") -> Usuario:
    cuenta = Usuario(
        usuario=f"{rol.lower()}.us14", nombre_completo=f"{rol} US-14", rol=rol, hash_contrasena="x"
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


@pytest.fixture
async def api(sesion) -> AsyncGenerator[tuple[AsyncClient, Any], None]:
    """Cliente con un usuario real; `como(rol)` cambia de rol en la misma prueba."""

    async def _misma_sesion():
        yield _SinCommit(sesion)

    async def como(rol: str) -> None:
        cuenta = await _usuario(sesion, rol)
        app.dependency_overrides[usuario_actual] = lambda: Autenticado(
            usuario=cuenta, sesion=Sesion(id=0, id_usuario=cuenta.id)
        )

    app.dependency_overrides[get_db] = _misma_sesion
    await como("LOGISTICA")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, como
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(usuario_actual, None)


async def _pedido(sesion, **kwargs) -> PedidoTransito:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    proveedor = Proveedor(codigo=f"P-US14-{len(kwargs)}", nombre="Proveedor")
    material = Material(codigo=f"M-US14-{len(kwargs)}", descripcion="Material", unidad_medida="KG")
    sesion.add_all([proveedor, material])
    await sesion.flush()
    datos = {
        "oc_numero": "4544400001",
        "posicion_oc": 10,
        "tracking_interno": "TRK-4544400001-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": "MARITIMO",
        "cantidad_pedida": Decimal("1.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 10, 30),
        "lead_time_destino_dias": destino.lead_time_dias,
        "etapa_viaje": "SIN_TRACKING",
        "estado_calculado": "SIN_TRACKING",
    }
    datos.update(kwargs)
    pedido = PedidoTransito(**datos)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def _rastreado(sesion, etapa: str = "EN_TRANSITO", **elemento_kwargs) -> PedidoTransito:
    elemento = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR",
        tracking_externo="MRSU0001414",
        via_transporte="MARITIMO",
        **elemento_kwargs,
    )
    sesion.add(elemento)
    await sesion.flush()
    return await _pedido(
        sesion, id_elemento_rastreado=elemento.id, etapa_viaje=etapa, estado_calculado=etapa
    )


def _url(pedido: PedidoTransito, accion: str) -> str:
    return f"/api/v1/pedidos/{pedido.id}/{accion}"


# --- Confirmar el desembarco ------------------------------------------------------


async def test_un_pedido_sin_rastreo_llega_cuando_alguien_lo_confirma(api, sesion) -> None:
    """El caso de 106 de los 107 pedidos: sin referencia, sin hito, sin AIS."""
    cliente, _ = api
    pedido = await _pedido(sesion)

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["etapa_viaje"] == "EN_DESTINO"
    assert cuerpo["calculo"]["origen"] == "ATA_CONFIRMADA"
    assert cuerpo["arribos"]["confirmado"] is not None
    destino = await sesion.get(MaestroDestino, pedido.id_destino)
    assert (
        cuerpo["fecha_proyectada_disponible"]
        == (
            LLEGADA.astimezone(dt.UTC).date() + dt.timedelta(days=destino.lead_time_dias)
        ).isoformat()
    )


async def test_la_llegada_confirmada_manda_sobre_la_eta_de_la_fuente(api, sesion) -> None:
    """Primer criterio: RN-14."""
    cliente, _ = api
    pedido = await _rastreado(sesion, eta_api=dt.datetime(2026, 10, 9, tzinfo=dt.UTC))

    cuerpo = (
        await cliente.post(
            _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
        )
    ).json()

    assert cuerpo["calculo"]["origen"] == "ATA_CONFIRMADA"
    assert cuerpo["eta_utilizada"].startswith("2026-09-22")


async def test_queda_auditado_con_el_autor_de_la_sesion(api, sesion) -> None:
    """Cuarto criterio."""
    cliente, _ = api
    pedido = await _pedido(sesion)

    await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    bitacora = (await cliente.get(_url(pedido, "bitacora"))).json()
    (asiento,) = bitacora
    assert asiento["tipo"] == "CONFIRMACION_DESEMBARCO"
    assert asiento["usuario"] == "logistica.us14"
    assert asiento["valor_anterior"] is None
    assert asiento["valor_nuevo"] == "2026-09-22T14:15:00+00:00"  # en UTC
    assert asiento["motivo"] == MOTIVO


@pytest.mark.parametrize(
    ("ata", "esperado"),
    [
        ((dt.datetime.now(dt.UTC) + dt.timedelta(days=1)).isoformat(), "no puede ser futura"),
        ("2026-09-22T08:15:00", "zona horaria"),
    ],
)
async def test_una_fecha_futura_o_sin_zona_se_rechaza(api, sesion, ata, esperado) -> None:
    """Segundo criterio, y la zona: sin ella, «08:15» es una hora distinta en cada servidor."""
    cliente, _ = api
    pedido = await _pedido(sesion)

    respuesta = await cliente.post(_url(pedido, "desembarco"), json={"ata": ata, "motivo": MOTIVO})

    assert respuesta.status_code == 422
    assert esperado in respuesta.json()["detail"]
    await sesion.refresh(pedido)
    assert pedido.ata_confirmada is None and pedido.etapa_viaje == "SIN_TRACKING"


async def test_sobrescribir_una_llegada_confirmada_exige_confirmarlo(api, sesion) -> None:
    """Tercer criterio."""
    cliente, _ = api
    pedido = await _pedido(sesion)
    await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )
    corregida = (LLEGADA - dt.timedelta(days=1)).isoformat()

    sin_confirmar = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": corregida, "motivo": "Fecha corregida por aduana"}
    )
    confirmado = await cliente.post(
        _url(pedido, "desembarco"),
        json={"ata": corregida, "motivo": "Fecha corregida por aduana", "confirmar": True},
    )

    assert sin_confirmar.status_code == 409
    assert sin_confirmar.json()["requiere_confirmacion"] is True
    actual = dt.datetime.fromisoformat(sin_confirmar.json()["ata_confirmada_actual"])
    assert actual == LLEGADA
    assert confirmado.status_code == 200
    segundo = (await cliente.get(_url(pedido, "bitacora"))).json()[-1]
    assert segundo["valor_anterior"].startswith("2026-09-22T14:15:00")
    assert segundo["valor_nuevo"].startswith("2026-09-21")


async def test_sin_motivo_no_se_confirma(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion)

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": " "}
    )

    assert respuesta.status_code == 422
    assert "motivo es obligatorio" in respuesta.json()["detail"]


async def test_un_pedido_cerrado_no_admite_la_confirmacion(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion, estado_calculado="CANCELADO", motivo_cierre="CANCELACION")

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 409
    assert "RN-13" in respuesta.json()["detail"]


async def test_solo_logistica_confirma(api, sesion) -> None:
    cliente, como = api
    pedido = await _pedido(sesion)
    await como("COMPRAS")

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 403


async def test_un_pedido_que_no_existe_da_404(api) -> None:
    cliente, _ = api
    respuesta = await cliente.post(
        "/api/v1/pedidos/999999999/desembarco", json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 404


# --- Pasar a proceso aduanal ------------------------------------------------------


async def test_tras_el_desembarco_se_pasa_a_aduana(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion)
    await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    respuesta = await cliente.post(
        _url(pedido, "paso-aduanal"), json={"motivo": "Documentos entregados al agente"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["etapa_viaje"] == "EN_PROCESO_ADUANAL"
    tipos = [a["tipo"] for a in (await cliente.get(_url(pedido, "bitacora"))).json()]
    assert tipos == ["CONFIRMACION_DESEMBARCO", "PASO_A_ADUANAL"]


async def test_si_el_arribo_lo_dio_la_fuente_no_hace_falta_confirmarlo(api, sesion) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa="EN_DESTINO", ata_api=LLEGADA)

    respuesta = await cliente.post(
        _url(pedido, "paso-aduanal"), json={"motivo": "Documentos entregados al agente"}
    )

    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    ("etapa", "esperado"),
    [
        ("EN_TRANSITO", "Confirme primero el desembarco"),
        ("EN_PROCESO_ADUANAL", "ya está en proceso aduanal"),
        ("RECIBIDO_EN_PLANTA", "ya pasó el proceso aduanal"),
    ],
)
async def test_solo_se_pasa_a_aduana_desde_en_destino(api, sesion, etapa, esperado) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa=etapa)

    respuesta = await cliente.post(
        _url(pedido, "paso-aduanal"), json={"motivo": "Documentos entregados al agente"}
    )

    assert respuesta.status_code == 409
    assert esperado in respuesta.json()["detail"]


# --- Las etapas solo avanzan --------------------------------------------------------


async def test_corregir_la_llegada_de_un_pedido_en_aduana_no_lo_devuelve(api, sesion) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa="EN_PROCESO_ADUANAL")

    cuerpo = (
        await cliente.post(
            _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
        )
    ).json()

    assert cuerpo["etapa_viaje"] == "EN_PROCESO_ADUANAL"


async def test_el_worker_no_devuelve_a_destino_un_pedido_en_aduana(sesion) -> None:
    """Antes de `US-14`, cada lectura con el hito de arribo lo devolvía."""
    pedido = await _rastreado(sesion, etapa="EN_PROCESO_ADUANAL", ata_api=LLEGADA)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado
    assert pedido.etapa_viaje == "EN_PROCESO_ADUANAL"


@pytest.mark.parametrize(
    ("antes", "de_la_fuente", "despues"),
    [
        ("EN_ORIGEN", "EN_TRANSITO", "EN_TRANSITO"),  # el BL de COSCO del 28/09
        ("EN_TRANSITO", "EN_ORIGEN", "EN_TRANSITO"),  # una lectura vieja no retrocede
        ("EN_DESTINO", "EN_TRANSITO", "EN_DESTINO"),
    ],
)
async def test_el_worker_aplica_la_etapa_de_la_fuente_solo_hacia_adelante(
    sesion, antes, de_la_fuente, despues
) -> None:
    pedido = await _rastreado(sesion, etapa=antes)
    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)

    await rastreo._arribo_y_recalculo(
        sesion, elemento, rastreo.ResumenCiclo(instante=LLEGADA), LLEGADA, de_la_fuente
    )

    assert pedido.etapa_viaje == despues


# --- RN-02 en la base -----------------------------------------------------------------


async def test_sin_rastreo_ni_llegada_confirmada_la_etapa_sigue_atada(sesion) -> None:
    """La excepción de la migración `0018` es solo la llegada confirmada."""
    pedido = await _pedido(sesion)

    with pytest.raises(IntegrityError, match="ck_pedidos_transito_sin_tracking"):
        async with sesion.begin_nested():
            await sesion.execute(
                text("UPDATE pedidos_transito SET etapa_viaje = 'EN_DESTINO' WHERE id = :id"),
                {"id": pedido.id},
            )

    filas = await sesion.scalars(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert list(filas) == []
