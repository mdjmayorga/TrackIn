"""Pruebas de `/api/v1/shipsgo/altas` — altas en ShipsGo desde TrackIn (`US-55`).

ShipsGo está simulado: un transporte que responde por ruta —listado de la cuenta,
catálogo de aerolíneas y altas— y anota cada alta pedida. Ninguna prueba sale a
la red ni gasta un crédito. Lo que se fija es **lo que cuesta dinero**: qué se
ofrece, qué se paga y qué hace falta confirmar antes.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.dependencias import Autenticado, usuario_actual
from app.api.shipsgo import cliente_shipsgo
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.paquete_creditos import PaqueteCreditos
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import planificador
from app.services.rastreo.registro_embarque import CAMPO_ALTA_CON_CREDITO
from app.services.rastreo.shipsgo_cliente import BASE, ClienteShipsGo, Respuesta
from conftest import vaciar_auditoria

pytestmark = pytest.mark.integration

URL = "/api/v1/shipsgo/altas"

BL = "COSU6508789000"
CONTENEDOR_REGISTRADO = "MRSU8507472"
MAWB_LUFTHANSA = "020-50685434"
#: Formato y dígito verificador correctos, prefijo que ninguna aerolínea emite.
MAWB_SIN_AEROLINEA = "111-12345675"

_AEROLINEAS = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "scripts/spikes/task28/output/02b_shipsgo_airlines.json"
    ).read_text(encoding="utf-8")
)


class _SinCommit:
    """La sesión de la prueba, con `commit` convertido en `flush`.

    El endpoint de altas confirma la transacción. Sin esto, ese `commit` cerraría
    la transacción de la prueba y lo escrito quedaría en `trackin_test`: el
    `rollback` del final ya no tendría nada que deshacer.
    """

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()


class ShipsGoFalso:
    """Responde como ShipsGo según la ruta, y anota las altas."""

    def __init__(self, registrados: tuple[str, ...] = ()) -> None:
        self.registrados = registrados
        self.altas: list[dict[str, Any]] = []

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str],
        cuerpo: dict[str, Any] | None = None,
    ) -> Respuesta:
        ruta = url.removeprefix(BASE)
        primera_pagina = ruta.endswith("skip=0")
        if metodo == "POST":
            self.altas.append(cuerpo or {})
            return Respuesta(200, {"shipment": {"id": 9000 + len(self.altas)}})
        if ruta.startswith("/ocean/shipments"):
            lote = (
                [{"id": i, "container_number": n} for i, n in enumerate(self.registrados, 1)]
                if primera_pagina
                else []
            )
            return Respuesta(200, {"shipments": lote, "meta": {"more": False}})
        if ruta.startswith("/air/shipments"):
            return Respuesta(200, {"shipments": [], "meta": {"more": False}})
        if ruta.startswith("/air/airlines"):
            return Respuesta(200, {"airlines": _AEROLINEAS if primera_pagina else []})
        raise AssertionError(f"ruta inesperada: {metodo} {url}")


@pytest.fixture
async def compras(sesion) -> Usuario:
    cuenta = Usuario(
        usuario="compras.altas", nombre_completo="Compras", rol="COMPRAS", hash_contrasena="x"
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


@pytest.fixture
async def api(sesion, compras) -> AsyncGenerator[tuple[AsyncClient, ShipsGoFalso], None]:
    """Cliente de Compras con su sesión, los pedidos vaciados y ShipsGo simulado."""
    await vaciar_auditoria(sesion)
    await sesion.execute(delete(PedidoTransito))
    await sesion.flush()
    falso = ShipsGoFalso(registrados=(CONTENEDOR_REGISTRADO,))

    async def _misma_sesion():
        yield _SinCommit(sesion)

    async def _shipsgo_falso():
        yield ClienteShipsGo(falso, token="t")

    app.dependency_overrides[get_db] = _misma_sesion
    app.dependency_overrides[cliente_shipsgo] = _shipsgo_falso
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=compras, sesion=Sesion(id=0, id_usuario=compras.id)
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, falso
    finally:
        for dependencia in (get_db, cliente_shipsgo, usuario_actual):
            app.dependency_overrides.pop(dependencia, None)


async def _maestro(sesion, modelo, codigo: str, **extra) -> Any:
    fila = await sesion.scalar(select(modelo).where(modelo.codigo == codigo))
    if fila is None:
        fila = modelo(codigo=codigo, **extra)
        sesion.add(fila)
        await sesion.flush()
    return fila


async def _linea(
    sesion,
    referencia: tuple[str, str] | None,
    *,
    oc: str,
    posicion: int = 10,
    via: str = "MARITIMO",
    **extra,
) -> PedidoTransito:
    """Un pedido activo, con su referencia (tipo, número) si la trae."""
    destino = await sesion.scalar(
        select(MaestroDestino).where(
            MaestroDestino.codigo == ("MROC" if via == "AEREO" else "CRMOB")
        )
    )
    proveedor = await _maestro(sesion, Proveedor, "P-ALTAS", nombre="Proveedor")
    material = await _maestro(
        sesion, Material, "M-ALTAS", descripcion="Material", unidad_medida="KG"
    )
    elemento = None
    if referencia:
        tipo, numero = referencia
        elemento = await sesion.scalar(
            select(ElementoRastreado).where(ElementoRastreado.tracking_externo == numero)
        )
        if elemento is None:
            elemento = ElementoRastreado(
                tipo_tracking_externo=tipo, tracking_externo=numero, via_transporte=via
            )
            sesion.add(elemento)
            await sesion.flush()
    pedido = PedidoTransito(
        oc_numero=oc,
        posicion_oc=posicion,
        tracking_interno=f"TRK-{oc}-{posicion}",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte=via,
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        fecha_entrega_pedido=dt.date(2026, 11, 30),
        lead_time_destino_dias=destino.lead_time_dias,
        id_elemento_rastreado=elemento.id if elemento else None,
        etapa_viaje="EN_ORIGEN" if elemento else "SIN_TRACKING",
        estado_calculado="EN_ORIGEN" if elemento else "SIN_TRACKING",
        **extra,
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def _escenario(sesion) -> None:
    """Un BL en dos líneas, un contenedor ya registrado, dos MAWB y lo que no cuenta."""
    await _linea(sesion, ("BL", BL), oc="4577000001", posicion=10)
    await _linea(sesion, ("BL", BL), oc="4577000001", posicion=20)
    await _linea(sesion, ("CONTENEDOR", CONTENEDOR_REGISTRADO), oc="4577000002")
    await _linea(sesion, ("MAWB", MAWB_LUFTHANSA), oc="4577000003", via="AEREO")
    await _linea(sesion, ("MAWB", MAWB_SIN_AEROLINEA), oc="4577000004", via="AEREO")
    await _linea(sesion, ("HAWB", "ZIVHYD017"), oc="4577000005", via="AEREO")  # la sigue TICA
    await _linea(sesion, None, oc="4577000006")  # sin referencia


async def _tope(sesion, valor: int) -> None:
    await sesion.execute(
        delete(ParametroSistema).where(ParametroSistema.clave == "altas_maximas_dia")
    )
    sesion.add(
        ParametroSistema(
            clave="altas_maximas_dia", valor=str(valor), tipo_dato="ENTERO", descripcion="t"
        )
    )
    await sesion.flush()


# --- Lo pendiente: gratis ---------------------------------------------------------


async def test_lista_lo_pendiente_agrupado_por_referencia(api, sesion) -> None:
    cliente, falso = api
    await _escenario(sesion)

    cuerpo = (await cliente.get(f"{URL}/pendientes")).json()

    por_numero = {p["numero"]: p for p in cuerpo["pendientes"]}
    # El contenedor ya está en la cuenta; la HAWB no es de ShipsGo; sin referencia, nada.
    assert set(por_numero) == {BL, MAWB_LUFTHANSA, MAWB_SIN_AEROLINEA}
    assert [(ln["oc_numero"], ln["posicion_oc"]) for ln in por_numero[BL]["lineas"]] == [
        ("4577000001", 10),
        ("4577000001", 20),
    ]
    assert por_numero[MAWB_LUFTHANSA]["cubierta"] is True
    assert por_numero[MAWB_SIN_AEROLINEA]["ofrecible"] is False
    # Un BL de dos líneas es un solo crédito; la MAWB sin aerolínea no se ofrece.
    assert cuerpo["creditos_necesarios"] == 2
    assert cuerpo["altas_hoy"] == 0
    assert falso.altas == []  # listar no da de alta nada


async def test_un_pedido_cerrado_no_cuenta(api, sesion) -> None:
    cliente, _ = api
    pedido = await _linea(sesion, ("BL", BL), oc="4577000001")
    # RN-13: un cerrado lleva el motivo y el estado terminal a la vez.
    pedido.motivo_cierre = "CIERRE_FORZADO"
    pedido.estado_calculado = "CERRADO"
    await sesion.flush()

    assert (await cliente.get(f"{URL}/pendientes")).json()["pendientes"] == []


# --- El alta: cuesta -----------------------------------------------------------------


async def test_da_de_alta_lo_confirmado_y_lo_audita_con_su_costo(api, sesion, compras) -> None:
    cliente, falso = api
    await _escenario(sesion)

    respuesta = await cliente.post(
        URL,
        json={
            "referencias": [
                {"tipo": "BL", "numero": BL},
                {"tipo": "MAWB", "numero": MAWB_LUFTHANSA},
            ],
            "creditos_confirmados": 2,
            "superar_tope": True,
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["creditos_consumidos"] == 2
    assert all(r["registrado"] for r in cuerpo["resultados"])
    assert len(falso.altas) == 2
    asientos = list(
        await sesion.scalars(
            select(AuditoriaIntervencion).where(
                AuditoriaIntervencion.campo_afectado == CAMPO_ALTA_CON_CREDITO
            )
        )
    )
    assert len(asientos) == 2 and {a.id_usuario for a in asientos} == {compras.id}
    assert await planificador.altas_del_dia(sesion) == 2


async def test_sin_confirmar_el_costo_exacto_no_se_da_de_alta_nada(api, sesion) -> None:
    cliente, falso = api
    await _escenario(sesion)

    respuesta = await cliente.post(
        URL,
        json={
            "referencias": [
                {"tipo": "BL", "numero": BL},
                {"tipo": "MAWB", "numero": MAWB_LUFTHANSA},
            ],
            "creditos_confirmados": 1,
            "superar_tope": True,
        },
    )

    assert respuesta.status_code == 422
    assert "son 2 créditos" in respuesta.json()["detail"]
    assert falso.altas == []


@pytest.mark.parametrize("numero", [CONTENEDOR_REGISTRADO, MAWB_SIN_AEROLINEA, "MSKU0000000"])
async def test_solo_se_paga_por_lo_pendiente_y_ofrecible(api, sesion, numero) -> None:
    """Ya registrado, sin aerolínea, o que ningún pedido usa: no se paga."""
    cliente, falso = api
    await _escenario(sesion)

    respuesta = await cliente.post(
        URL,
        json={"referencias": [{"tipo": "BL", "numero": numero}], "creditos_confirmados": 1},
    )

    assert respuesta.status_code == 422
    assert falso.altas == []


async def test_pasar_el_tope_diario_pide_aceptarlo_antes(api, sesion) -> None:
    cliente, falso = api
    await _escenario(sesion)
    await _tope(sesion, 1)
    pedido = {
        "referencias": [{"tipo": "BL", "numero": BL}, {"tipo": "MAWB", "numero": MAWB_LUFTHANSA}],
        "creditos_confirmados": 2,
    }

    sin_aceptar = await cliente.post(URL, json=pedido)

    assert sin_aceptar.status_code == 409
    assert sin_aceptar.json()["requiere_superar_tope"] is True
    assert sin_aceptar.json()["altas_maximas_dia"] == 1
    assert falso.altas == []

    aceptado = await cliente.post(URL, json={**pedido, "superar_tope": True})

    assert aceptado.status_code == 200
    assert len(falso.altas) == 2


async def test_dentro_del_tope_no_hace_falta_aceptarlo(api, sesion) -> None:
    cliente, falso = api
    await _escenario(sesion)
    await _tope(sesion, 5)

    respuesta = await cliente.post(
        URL, json={"referencias": [{"tipo": "BL", "numero": BL}], "creditos_confirmados": 1}
    )

    assert respuesta.status_code == 200
    assert len(falso.altas) == 1


# --- Quién y con qué ---------------------------------------------------------------


@pytest.mark.parametrize("rol", ["LOGISTICA", "PLANIFICACION", "PLANTA"])
async def test_solo_compras_y_el_administrador(api, sesion, rol) -> None:
    cliente, falso = api
    otra = Usuario(
        usuario=f"{rol.lower()}.altas", nombre_completo=rol, rol=rol, hash_contrasena="x"
    )
    sesion.add(otra)
    await sesion.flush()
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=otra, sesion=Sesion(id=0, id_usuario=otra.id)
    )

    assert (await cliente.get(f"{URL}/pendientes")).status_code == 403
    assert (
        await cliente.post(
            URL, json={"referencias": [{"tipo": "BL", "numero": BL}], "creditos_confirmados": 1}
        )
    ).status_code == 403
    assert falso.altas == []


async def test_sin_token_de_shipsgo_lo_dice(api, monkeypatch) -> None:
    cliente, _ = api
    app.dependency_overrides.pop(cliente_shipsgo, None)
    monkeypatch.setattr(settings, "SHIPSGO_API_TOKEN", "")

    respuesta = await cliente.get(f"{URL}/pendientes")

    assert respuesta.status_code == 503
    assert "SHIPSGO_API_TOKEN" in respuesta.json()["detail"]


# --- US-57: el saldo, antes de gastar ----------------------------------------------


async def test_si_el_saldo_registrado_no_alcanza_pide_aceptarlo_antes(api, sesion, compras) -> None:
    from app.services import creditos

    cliente, falso = api
    await _escenario(sesion)
    await sesion.execute(delete(PaqueteCreditos))
    await creditos.registrar_paquete(
        sesion, cantidad=1, comprado_en=dt.date(2026, 9, 23), vence_en=None, id_usuario=compras.id
    )
    pedido = {
        "referencias": [{"tipo": "BL", "numero": BL}, {"tipo": "MAWB", "numero": MAWB_LUFTHANSA}],
        "creditos_confirmados": 2,
        "superar_tope": True,
    }

    pendientes = (await cliente.get(f"{URL}/pendientes")).json()
    sin_aceptar = await cliente.post(URL, json=pedido)

    assert pendientes["creditos"]["saldo"] == 1
    assert sin_aceptar.status_code == 409
    assert sin_aceptar.json()["requiere_aceptar_saldo"] is True
    assert falso.altas == []

    aceptado = await cliente.post(URL, json={**pedido, "aceptar_saldo": True})

    assert aceptado.status_code == 200
    assert len(falso.altas) == 2


async def test_sin_paquete_registrado_no_se_frena_el_alta(api, sesion) -> None:
    """Sin paquete, TrackIn no sabe el saldo: no puede negar por él."""
    cliente, falso = api
    await _escenario(sesion)
    await sesion.execute(delete(PaqueteCreditos))

    respuesta = await cliente.post(
        URL, json={"referencias": [{"tipo": "BL", "numero": BL}], "creditos_confirmados": 1}
    )

    assert respuesta.status_code == 200
    assert len(falso.altas) == 1
