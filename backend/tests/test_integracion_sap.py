"""TrackIn escucha a la API de SAP — `US-65`.

El orden de las guardas es parte del contrato (`docs/integraciones/sap/`): clave
(`401`), escucha (`503`), tamaño (`413`) y formato (`422`). Recién entonces se
carga, por el mismo camino que el Excel y **sin marcar ausentes**.
"""

from __future__ import annotations

import copy
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update

from app.api.cargas import resolutor_de_destinos
from app.api.dependencias import Autenticado, usuario_actual
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.carga_ztracking import CargaZTracking
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.schemas.integracion_sap import LoteSap, PedidoSap
from app.services.ingesta import frescura

pytestmark = pytest.mark.integration

URL = "/api/v1/integraciones/sap/pedidos"
CLAVE = "clave-de-prueba-sap"
CARPETA = Path(__file__).resolve().parents[2] / "docs" / "integraciones" / "sap"
EJEMPLO: dict[str, Any] = json.loads((CARPETA / "ejemplo_lote.json").read_text(encoding="utf-8"))


class _SinCommit:
    """La sesión de la prueba con `commit` convertido en `flush` (ver `test_altas_api`)."""

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()

    async def rollback(self) -> None:
        # Un rollback de verdad desharía también la preparación de la prueba.
        pass


@pytest.fixture
async def api(sesion, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setattr(settings, "SAP_INTEGRACION_CLAVE", CLAVE)

    async def _misma_sesion():
        yield _SinCommit(sesion)

    async def _sin_resolutor():
        yield None

    app.dependency_overrides[get_db] = _misma_sesion
    app.dependency_overrides[resolutor_de_destinos] = _sin_resolutor
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": CLAVE},
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(resolutor_de_destinos, None)


async def _escucha(sesion, encendida: bool) -> None:
    await sesion.execute(
        update(ParametroSistema)
        .where(ParametroSistema.clave == "sap_escucha_habilitada")
        .values(valor="true" if encendida else "false")
    )


@pytest.fixture
async def encendida(sesion, api) -> AsyncClient:
    await _escucha(sesion, True)
    await sesion.execute(delete(CargaZTracking))
    return api


def _lote(*pedidos: dict[str, Any], lote_id: str = "SAP-PRUEBA-1") -> dict[str, Any]:
    datos = copy.deepcopy(EJEMPLO)
    datos["lote"]["id"] = lote_id
    if pedidos:
        datos["pedidos"] = list(pedidos)
    return datos


def _minimo(oc: str, posicion: int = 10, **extra: Any) -> dict[str, Any]:
    return {
        "oc_numero": oc,
        "posicion_oc": posicion,
        "proveedor_codigo": "P-SAP",
        "proveedor_nombre": "Proveedor SAP",
        "material_codigo": "M-SAP",
        "material_descripcion": "Material SAP",
        "cantidad": 10,
        "unidad_medida": "KG",
        "fecha_entrega_pedido": "2026-12-15",
        "via_transporte": "AEREO",
        **extra,
    }


async def _pedido(sesion, oc: str, posicion: int = 10) -> PedidoTransito | None:
    return await sesion.scalar(
        select(PedidoTransito).where(
            PedidoTransito.oc_numero == oc, PedidoTransito.posicion_oc == posicion
        )
    )


# --- Las guardas, en orden ------------------------------------------------------------


@pytest.mark.parametrize("encabezados", [{"X-API-Key": ""}, {"X-API-Key": "otra-clave"}])
async def test_sin_la_clave_correcta_responde_401(api, encabezados) -> None:
    respuesta = await api.post(URL, json=_lote(), headers=encabezados)

    assert respuesta.status_code == 401


async def test_sin_clave_en_el_servidor_nadie_entra(api, monkeypatch) -> None:
    monkeypatch.setattr(settings, "SAP_INTEGRACION_CLAVE", None)

    assert (await api.post(URL, json=_lote())).status_code == 401


async def test_con_la_escucha_apagada_responde_503_sin_tocar_nada(api, sesion) -> None:
    """Así arranca: la migración la deja en `false`."""
    antes = await sesion.scalar(select(CargaZTracking.id).order_by(CargaZTracking.id.desc()))

    respuesta = await api.post(URL, json=_lote())

    assert respuesta.status_code == 503
    assert respuesta.json()["escucha_habilitada"] is False
    assert "deshabilitada" in respuesta.json()["detail"]
    assert (
        await sesion.scalar(select(CargaZTracking.id).order_by(CargaZTracking.id.desc())) == antes
    )
    assert await _pedido(sesion, EJEMPLO["pedidos"][0]["oc_numero"]) is None


async def test_apagada_ni_siquiera_valida_el_formato(api) -> None:
    respuesta = await api.post(URL, content=b"esto no es json")

    assert respuesta.status_code == 503


async def test_mas_de_5000_pedidos_responde_413(encendida) -> None:
    lote = _lote(*[_minimo("4500000001", i) for i in range(1, 5002)])

    assert (await encendida.post(URL, json=lote)).status_code == 413


@pytest.mark.parametrize(
    ("cambio", "donde"),
    [
        ({"posicion_oc": "10"}, "posicion_oc"),  # estricto: un texto no es un número
        ({"fecha_entrega_pedido": "15/12/2026"}, "fecha_entrega_pedido"),
        ({"cantidad": -5}, "cantidad"),
        ({"via_transporte": "BARCO"}, "via_transporte"),
        ({"campo_inventado": 1}, "campo_inventado"),  # lo que el contrato no conoce
    ],
)
async def test_un_lote_fuera_de_contrato_se_rechaza_entero(
    encendida, sesion, cambio, donde
) -> None:
    lote = _lote(_minimo("4500000101"), {**_minimo("4500000102"), **cambio})

    respuesta = await encendida.post(URL, json=lote)

    assert respuesta.status_code == 422
    assert any(donde in error["loc"] for error in respuesta.json()["detail"])
    # Nada a medias: tampoco entró la línea buena.
    assert await _pedido(sesion, "4500000101") is None


async def test_un_cuerpo_que_no_es_json_se_rechaza(encendida) -> None:
    assert (await encendida.post(URL, content=b"{roto")).status_code == 422


# --- La carga -------------------------------------------------------------------------


async def test_el_ejemplo_del_contrato_entra_y_queda_en_el_historial(encendida, sesion) -> None:
    respuesta = await encendida.post(URL, json=_lote())

    assert respuesta.status_code == 200, respuesta.text
    informe = respuesta.json()
    assert informe["lote_id"] == "SAP-PRUEBA-1"
    assert informe["recibidas"] == 2
    assert informe["insertadas"] + informe["actualizadas"] + informe["sin_cambios"] == 2

    maritimo = await _pedido(sesion, "4500123456")
    assert maritimo is not None
    assert maritimo.solicitud_pedido == "10012345"

    carga = await sesion.get(CargaZTracking, informe["id_carga"])
    assert carga is not None
    assert (carga.origen, carga.id_usuario, carga.archivo) == (
        "API_SAP",
        None,
        "Lote SAP-PRUEBA-1",
    )
    assert carga.informe is not None and carga.informe["lote"]["tipo"] == "INCREMENTAL"


async def test_reenviar_el_mismo_lote_no_duplica(encendida) -> None:
    await encendida.post(URL, json=_lote())

    segunda = (await encendida.post(URL, json=_lote())).json()

    assert (segunda["insertadas"], segunda["sin_cambios"]) == (0, 2)


async def test_no_marca_ausentes_los_pedidos_que_no_vienen(encendida, sesion) -> None:
    await encendida.post(URL, json=_lote(_minimo("4500000201"), lote_id="A"))

    await encendida.post(URL, json=_lote(_minimo("4500000202"), lote_id="B"))

    primero = await _pedido(sesion, "4500000201")
    assert primero is not None and primero.ausente_desde is None


async def test_busca_la_referencia_en_el_comentario_como_el_excel(encendida, sesion) -> None:
    lote = _lote(_minimo("4500000301", comentario="MAWB 020-50685434 sale el lunes"))

    assert (await encendida.post(URL, json=lote)).status_code == 200

    pedido = await _pedido(sesion, "4500000301")
    assert pedido is not None
    assert pedido.id_elemento_rastreado is not None


async def test_la_carga_semanal_sigue_siendo_la_del_excel(encendida, sesion) -> None:
    """Un lote de SAP no cumple la carga del martes (`US-23`)."""
    await encendida.post(URL, json=_lote())

    assert (await frescura.estado_semanal(sesion)).ultima is None


# --- El esquema del backend es el del contrato -----------------------------------------


def test_el_modelo_acepta_exactamente_los_campos_del_contrato() -> None:
    esquema = json.loads((CARPETA / "lote_pedidos.schema.json").read_text(encoding="utf-8"))
    pedido = esquema["$defs"]["pedido"]

    assert set(PedidoSap.model_fields) == set(pedido["properties"])
    obligatorios = {n for n, c in PedidoSap.model_fields.items() if c.is_required()}
    assert obligatorios == set(pedido["required"])
    assert set(LoteSap.model_fields) == set(esquema["required"])


# --- US-66: el interruptor ---------------------------------------------------------------


@pytest.fixture
async def como(sesion) -> AsyncGenerator[Any, None]:
    """`await como("COMPRAS")` hace que la API vea a ese usuario autenticado."""

    async def _como(rol: str) -> Usuario:
        cuenta = Usuario(
            usuario=f"{rol.lower()}.sap",
            nombre_completo=f"Cuenta {rol}",
            rol=rol,
            hash_contrasena="x",
        )
        sesion.add(cuenta)
        await sesion.flush()
        app.dependency_overrides[usuario_actual] = lambda: Autenticado(
            usuario=cuenta, sesion=Sesion(id=0, id_usuario=cuenta.id)
        )
        return cuenta

    yield _como
    app.dependency_overrides.pop(usuario_actual, None)


ESCUCHA = "/api/v1/integraciones/sap/escucha"


async def test_arranca_apagada_y_cualquiera_lo_ve(api, sesion, como) -> None:
    await sesion.execute(delete(CargaZTracking))
    await como("PLANTA")

    estado = (await api.get(ESCUCHA)).json()

    assert estado["habilitada"] is False
    assert estado["cambiada_por"] is None
    assert estado["clave_configurada"] is True
    assert estado["ultima_recepcion"] is None


@pytest.mark.parametrize("rol", ["COMPRAS", "LOGISTICA", "PLANIFICACION", "PLANTA"])
async def test_solo_el_administrador_la_cambia(api, como, rol) -> None:
    await como(rol)

    assert (await api.put(ESCUCHA, json={"habilitada": True})).status_code == 403


async def test_el_administrador_la_enciende_y_queda_quien_y_cuando(api, sesion, como) -> None:
    await sesion.execute(delete(CargaZTracking))
    await como("ADMINISTRADOR")

    encendida = (await api.put(ESCUCHA, json={"habilitada": True})).json()

    assert encendida["habilitada"] is True
    assert encendida["cambiada_por"]["nombre_completo"] == "Cuenta ADMINISTRADOR"
    assert encendida["cambiada_en"] is not None
    # Encendida, SAP ya puede enviar, y la pantalla muestra la última recepción.
    assert (await api.post(URL, json=_lote())).status_code == 200
    ultima = (await api.get(ESCUCHA)).json()["ultima_recepcion"]
    assert ultima["origen"] == "API_SAP"
    assert ultima["usuario"] is None

    apagada = (await api.put(ESCUCHA, json={"habilitada": False})).json()
    assert apagada["habilitada"] is False
    assert (await api.post(URL, json=_lote())).status_code == 503


async def test_avisa_si_el_servidor_no_tiene_clave(api, como, monkeypatch) -> None:
    monkeypatch.setattr(settings, "SAP_INTEGRACION_CLAVE", None)
    await como("ADMINISTRADOR")

    assert (await api.get(ESCUCHA)).json()["clave_configurada"] is False


async def test_health_informa_la_escucha(api, sesion) -> None:
    assert (await api.get("/health")).json()["sap_escucha_habilitada"] is False

    await _escucha(sesion, True)

    assert (await api.get("/health")).json()["sap_escucha_habilitada"] is True
