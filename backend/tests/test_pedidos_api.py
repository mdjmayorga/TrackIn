"""Pruebas de `/api/v1/pedidos` — `US-16`.

El cliente HTTP usa la **misma sesión** que la prueba (se sobreescribe
`get_db`): así ve lo que la prueba escribió y todo se deshace al terminar, sin
tocar los pedidos cargados en la base de desarrollo.

Cada prueba vacía `pedidos_transito` dentro de su transacción, porque los
totales y el orden solo se pueden afirmar sobre un conjunto conocido.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import get_args

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import get_db
from app.main import app
from app.models import enums
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.schemas import pedidos as esquemas
from app.services import historial
from app.services.recalculo import CLAVE_UMBRAL

URL = "/api/v1/pedidos"
COMPROMETIDA = dt.date(2026, 10, 20)


# --- El contrato publicado no se desincroniza del modelo --------------------


@pytest.mark.parametrize(
    ("literal", "dominio"),
    [
        (esquemas.Via, enums.VIAS_TRANSPORTE),
        (esquemas.EtapaViaje, enums.ETAPAS_VIAJE),
        (esquemas.Cumplimiento, enums.ESTADOS_CUMPLIMIENTO),
        (esquemas.EstadoCalculado, enums.ESTADOS_CALCULADOS),
    ],
)
def test_los_dominios_de_la_api_son_los_del_modelo(literal, dominio) -> None:
    assert get_args(literal) == dominio


# --- Datos ------------------------------------------------------------------


@pytest.fixture
async def api(sesion) -> AsyncGenerator[AsyncClient, None]:
    """Cliente cuya sesión es la de la prueba, con la tabla de pedidos vacía."""
    await sesion.execute(delete(PedidoTransito))
    await sesion.flush()

    async def _misma_sesion():
        yield sesion

    app.dependency_overrides[get_db] = _misma_sesion
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def umbral_dos(sesion) -> int:
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == CLAVE_UMBRAL))
    sesion.add(
        ParametroSistema(
            clave=CLAVE_UMBRAL, valor="2", tipo_dato="ENTERO", descripcion="Umbral de prueba"
        )
    )
    await sesion.flush()
    return 2


async def _destino(sesion, codigo: str = "CRMOB") -> MaestroDestino:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == codigo))
    assert destino is not None, "la migración 0002 siembra los cuatro destinos"
    return destino


async def _maestro(sesion, modelo, codigo: str, **campos):
    fila = await sesion.scalar(select(modelo).where(modelo.codigo == codigo))
    if fila is None:
        fila = modelo(codigo=codigo, **campos)
        sesion.add(fila)
        await sesion.flush()
    return fila


async def _pedido(sesion, oc: str = "4588800001", posicion: int = 10, **kwargs) -> PedidoTransito:
    destino = kwargs.pop("destino", None) or await _destino(sesion)
    proveedor = kwargs.pop("proveedor", None) or await _maestro(
        sesion, Proveedor, "P-API-1", nombre="Proveedor Uno"
    )
    material = kwargs.pop("material", None) or await _maestro(
        sesion, Material, "M-API-1", descripcion="Material uno", unidad_medida="KG"
    )
    base = {
        "oc_numero": oc,
        "posicion_oc": posicion,
        "tracking_interno": f"TRK-{oc}-{posicion:03d}",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": destino.via_transporte,
        "cantidad_pedida": Decimal("100.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": COMPROMETIDA,
        "lead_time_destino_dias": destino.lead_time_dias,
        "etapa_viaje": "SIN_TRACKING",
        "estado_calculado": "SIN_TRACKING",
    }
    base.update(kwargs)
    pedido = PedidoTransito(**base)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def _elemento(sesion, **kwargs) -> ElementoRastreado:
    base = {
        "tipo_tracking_externo": "CONTENEDOR",
        "tracking_externo": "MRSU0000001",
        "via_transporte": "MARITIMO",
    }
    base.update(kwargs)
    elemento = ElementoRastreado(**base)
    sesion.add(elemento)
    await sesion.flush()
    return elemento


def _medianoche(fecha: dt.date) -> dt.datetime:
    return dt.datetime.combine(fecha, dt.time.min, tzinfo=dt.UTC)


# --- Listado: RF-04 ---------------------------------------------------------


@pytest.mark.integration
async def test_el_listado_trae_las_columnas_de_la_grilla(api, sesion) -> None:
    pedido = await _pedido(
        sesion,
        eta_utilizada=_medianoche(dt.date(2026, 10, 1)),
        fecha_proyectada_disponible=dt.date(2026, 10, 8),
        estado_cumplimiento="A_TIEMPO",
        estado_calculado="A_TIEMPO",
    )

    respuesta = await api.get(URL)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    fila = cuerpo["items"][0]
    assert fila["id"] == pedido.id
    assert (fila["oc_numero"], fila["posicion_oc"]) == ("4588800001", 10)
    assert fila["material"]["codigo"] == "M-API-1"
    assert fila["proveedor"]["nombre"] == "Proveedor Uno"
    assert fila["destino"]["codigo"] == "CRMOB"
    assert fila["via_transporte"] == "MARITIMO"
    assert fila["eta_utilizada"].startswith("2026-10-01")
    assert fila["fecha_proyectada_disponible"] == "2026-10-08"
    assert fila["fecha_entrega_pedido"] == "2026-10-20"
    assert fila["etapa_viaje"] == "SIN_TRACKING"
    assert fila["estado_cumplimiento"] == "A_TIEMPO"
    assert fila["estado_calculado"] == "A_TIEMPO"
    assert fila["rastreable"] is False
    assert fila["ultima_actualizacion_fuente"] is None


@pytest.mark.integration
async def test_la_frescura_de_la_fuente_viaja_en_la_fila(api, sesion) -> None:
    leido = dt.datetime(2026, 9, 28, 15, 0, tzinfo=dt.UTC)
    elemento = await _elemento(sesion, ultima_actualizacion_api=leido)
    await _pedido(
        sesion,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="EN_TRANSITO",
    )

    fila = (await api.get(URL)).json()["items"][0]

    assert fila["rastreable"] is True
    assert dt.datetime.fromisoformat(fila["ultima_actualizacion_fuente"]) == leido


@pytest.mark.integration
async def test_sin_filtro_de_estado_no_salen_los_cerrados(api, sesion) -> None:
    await _pedido(sesion, posicion=10)
    await _pedido(
        sesion,
        posicion=20,
        estado_calculado="CANCELADO",
        motivo_cierre="CANCELACION",
    )

    activos = (await api.get(URL)).json()
    cancelados = (await api.get(URL, params={"estado": "CANCELADO"})).json()

    assert [f["posicion_oc"] for f in activos["items"]] == [10]
    assert [f["posicion_oc"] for f in cancelados["items"]] == [20]


@pytest.mark.integration
async def test_los_filtros_se_combinan(api, sesion) -> None:
    otro_proveedor = await _maestro(sesion, Proveedor, "P-API-2", nombre="Proveedor Dos")
    otro_material = await _maestro(
        sesion, Material, "M-API-2", descripcion="Material dos", unidad_medida="L"
    )
    aeropuerto = await _destino(sesion, "MROC")
    await _pedido(sesion, oc="4588800001")
    await _pedido(sesion, oc="4588800002", proveedor=otro_proveedor)
    await _pedido(sesion, oc="4588800003", material=otro_material)
    await _pedido(sesion, oc="4588800004", destino=aeropuerto)
    await _pedido(
        sesion,
        oc="4599900005",
        estado_calculado="EN_RIESGO",
        estado_cumplimiento="EN_RIESGO",
        eta_utilizada=_medianoche(dt.date(2026, 10, 12)),
        fecha_proyectada_disponible=dt.date(2026, 10, 19),
    )

    async def ocs(**params) -> list[str]:
        cuerpo = (await api.get(URL, params=params)).json()
        return sorted(f["oc_numero"] for f in cuerpo["items"])

    assert await ocs(oc="45888") == ["4588800001", "4588800002", "4588800003", "4588800004"]
    assert await ocs(proveedor=otro_proveedor.id) == ["4588800002"]
    assert await ocs(material=otro_material.id) == ["4588800003"]
    assert await ocs(via="AEREO") == ["4588800004"]
    assert await ocs(destino=aeropuerto.id) == ["4588800004"]
    assert await ocs(estado="EN_RIESGO") == ["4599900005"]
    assert await ocs(estado=["EN_RIESGO", "SIN_TRACKING"], oc="45999") == ["4599900005"]
    assert await ocs(via=["AEREO", "MARITIMO"], oc="45888") == [
        "4588800001",
        "4588800002",
        "4588800003",
        "4588800004",
    ]


@pytest.mark.integration
async def test_el_prefijo_de_oc_no_es_un_comodin(api, sesion) -> None:
    await _pedido(sesion)

    cuerpo = (await api.get(URL, params={"oc": "%"})).json()

    assert cuerpo["total"] == 0


@pytest.mark.integration
async def test_una_combinacion_sin_resultados_es_una_lista_vacia(api, sesion) -> None:
    await _pedido(sesion)

    respuesta = await api.get(URL, params={"oc": "123"})

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 0, "limite": 50, "desplazamiento": 0, "items": []}


# --- Orden y paginación -----------------------------------------------------


async def _tres_fechas(sesion) -> None:
    """Tres pedidos: uno sin fecha proyectada y dos con fechas distintas."""
    await _pedido(sesion, oc="4588800001", posicion=10)
    for posicion, dia in ((20, 15), (30, 5)):
        await _pedido(
            sesion,
            oc="4588800001",
            posicion=posicion,
            eta_utilizada=_medianoche(dt.date(2026, 10, dia)),
            fecha_proyectada_disponible=dt.date(2026, 10, dia),
        )


@pytest.mark.integration
async def test_por_omision_ordena_por_fecha_proyectada_con_las_nulas_al_final(api, sesion) -> None:
    await _tres_fechas(sesion)

    cuerpo = (await api.get(URL)).json()

    assert [f["posicion_oc"] for f in cuerpo["items"]] == [30, 20, 10]


@pytest.mark.integration
async def test_el_menos_invierte_el_orden_pero_las_nulas_siguen_al_final(api, sesion) -> None:
    await _tres_fechas(sesion)

    cuerpo = (await api.get(URL, params={"orden": "-fecha_proyectada"})).json()

    assert [f["posicion_oc"] for f in cuerpo["items"]] == [20, 30, 10]


@pytest.mark.integration
async def test_la_oc_ordena_tambien_por_posicion(api, sesion) -> None:
    await _pedido(sesion, oc="4588800002", posicion=10)
    await _pedido(sesion, oc="4588800001", posicion=20)
    await _pedido(sesion, oc="4588800001", posicion=10)

    cuerpo = (await api.get(URL, params={"orden": "oc"})).json()

    assert [(f["oc_numero"], f["posicion_oc"]) for f in cuerpo["items"]] == [
        ("4588800001", 10),
        ("4588800001", 20),
        ("4588800002", 10),
    ]


@pytest.mark.integration
async def test_la_paginacion_no_cambia_el_total(api, sesion) -> None:
    for posicion in range(10, 60, 10):
        await _pedido(sesion, posicion=posicion)

    primera = (await api.get(URL, params={"orden": "oc", "limite": 2})).json()
    tercera = (await api.get(URL, params={"orden": "oc", "limite": 2, "desplazamiento": 4})).json()

    assert primera["total"] == tercera["total"] == 5
    assert [f["posicion_oc"] for f in primera["items"]] == [10, 20]
    assert [f["posicion_oc"] for f in tercera["items"]] == [50]


@pytest.mark.parametrize(
    "params",
    [
        {"orden": "precio"},
        {"orden": "--oc"},
        {"via": "FERROVIARIO"},
        {"estado": "PERDIDO"},
        {"limite": 0},
        {"limite": 201},
        {"desplazamiento": -1},
    ],
)
async def test_los_parametros_invalidos_se_rechazan_con_422(client, params) -> None:
    respuesta = await client.get(URL, params=params)

    assert respuesta.status_code == 422


# --- Detalle: RF-05 ---------------------------------------------------------


@pytest.mark.integration
async def test_un_id_inexistente_da_404_con_un_motivo(api) -> None:
    respuesta = await api.get(f"{URL}/999999999")

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No existe el pedido 999999999."}


@pytest.mark.integration
async def test_un_pedido_sin_elemento_se_declara_no_rastreable(api, sesion, umbral_dos) -> None:
    pedido = await _pedido(sesion, incoterm="CIF", temperatura="2-8 °C")

    cuerpo = (await api.get(f"{URL}/{pedido.id}")).json()

    assert cuerpo["rastreable"] is False
    assert cuerpo["rastreo"] is None
    assert cuerpo["incoterm"] == "CIF"
    assert cuerpo["temperatura"] == "2-8 °C"
    assert cuerpo["cantidad_pedida"] == "100.000"
    assert cuerpo["calculo"]["fecha_proyectada"] is None
    assert cuerpo["calculo"]["al_dia"] is True
    assert cuerpo["calculo"]["desglose"].startswith("Sin fecha proyectada: ")
    assert cuerpo["calculo"]["ventana_aduanal_dias"] is None


@pytest.mark.integration
async def test_el_detalle_trae_rastreo_posicion_y_desglose(api, sesion, umbral_dos) -> None:
    leido = dt.datetime(2026, 9, 28, 15, 0, tzinfo=dt.UTC)
    elemento = await _elemento(
        sesion,
        nombre="MAERSK KALMAR",
        imo=9632179,
        eta_api=dt.datetime(2026, 10, 5, 8, 0, tzinfo=dt.UTC),
        velocidad_actual=Decimal("14.20"),
        ultima_actualizacion_api=leido,
        posicion_actual=historial.punto_wkt(-79.5, 9.3),
    )
    destino = await _destino(sesion)
    pedido = await _pedido(
        sesion,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="EN_RIESGO",
        estado_cumplimiento="EN_RIESGO",
        eta_utilizada=_medianoche(dt.date(2026, 10, 5)),
        lead_time_destino_dias=destino.lead_time_dias,
        fecha_proyectada_disponible=dt.date(2026, 10, 5)
        + dt.timedelta(days=destino.lead_time_dias),
        fecha_entrega_pedido=dt.date(2026, 10, 5) + dt.timedelta(days=destino.lead_time_dias + 1),
    )

    cuerpo = (await api.get(f"{URL}/{pedido.id}")).json()

    rastreo = cuerpo["rastreo"]
    assert rastreo["tipo"] == "CONTENEDOR"
    assert rastreo["referencia"] == "MRSU0000001"
    assert rastreo["nombre"] == "MAERSK KALMAR"
    assert rastreo["posicion"] == {"latitud": pytest.approx(9.3), "longitud": pytest.approx(-79.5)}
    assert dt.datetime.fromisoformat(rastreo["ultima_consulta_exitosa"]) == leido

    calculo = cuerpo["calculo"]
    assert calculo["origen"] == "ETA_FUENTE"
    assert calculo["al_dia"] is True
    assert calculo["desglose_actual"] is None
    assert calculo["margen_dias"] == 1
    # `US-53`: llega a CR el 05/10 y a Gutis se espera lead time + 1 día después.
    assert calculo["ventana_aduanal_dias"] == destino.lead_time_dias + 1
    assert calculo["umbral_riesgo_dias"] == 2
    assert calculo["desglose"] == (
        f"2026-10-05 (ETA_FUENTE) + {destino.lead_time_dias} d de lead time "
        f"= {calculo['fecha_proyectada']}"
    )


@pytest.mark.integration
async def test_los_tres_arribos_se_distinguen(api, sesion, umbral_dos) -> None:
    fuente = dt.datetime(2026, 9, 18, 6, 0, tzinfo=dt.UTC)
    inferido = dt.datetime(2026, 9, 18, 5, 34, tzinfo=dt.UTC)
    elemento = await _elemento(sesion, ata_api=fuente)
    pedido = await _pedido(
        sesion,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_DESTINO",
        estado_calculado="EN_DESTINO",
        ata_inferida=inferido,
    )

    arribos = (await api.get(f"{URL}/{pedido.id}")).json()["arribos"]

    assert arribos["confirmado"] is None
    assert dt.datetime.fromisoformat(arribos["fuente"]) == fuente
    assert dt.datetime.fromisoformat(arribos["inferido"]) == inferido


@pytest.mark.integration
async def test_una_fecha_que_ya_no_sale_de_sus_insumos_se_senala(api, sesion, umbral_dos) -> None:
    """El caso real del 29/09: una fecha guardada cuyo insumo desapareció."""
    pedido = await _pedido(
        sesion,
        eta_utilizada=_medianoche(dt.date(2026, 8, 29)),
        lead_time_destino_dias=2,
        fecha_proyectada_disponible=dt.date(2026, 8, 31),
    )

    calculo = (await api.get(f"{URL}/{pedido.id}")).json()["calculo"]

    assert calculo["al_dia"] is False
    # El origen de hoy no produjo la fecha guardada: no se atribuye.
    assert calculo["origen"] is None
    assert calculo["desglose"] == "2026-08-29 + 2 d de lead time = 2026-08-31"
    assert calculo["desglose_actual"].startswith("Sin fecha proyectada: ")
    assert calculo["lead_time_dias"] == 2
    assert calculo["lead_time_maestro_dias"] == (await _destino(sesion)).lead_time_dias


@pytest.mark.integration
async def test_el_ajuste_manual_aparece_como_sumando_propio(api, sesion, umbral_dos) -> None:
    pedido = await _pedido(
        sesion,
        eta_declarada=dt.date(2026, 10, 1),
        eta_utilizada=_medianoche(dt.date(2026, 10, 1)),
        lead_time_destino_dias=7,
        ajuste_manual_dias=3,
        fecha_proyectada_disponible=dt.date(2026, 10, 11),
    )

    calculo = (await api.get(f"{URL}/{pedido.id}")).json()["calculo"]

    assert calculo["al_dia"] is True
    assert calculo["desglose"] == (
        "2026-10-01 (ETA_DECLARADA) + 7 d de lead time + 3 d de ajuste manual = 2026-10-11"
    )


@pytest.mark.integration
async def test_un_pedido_cerrado_no_se_reproyecta(api, sesion, umbral_dos) -> None:
    pedido = await _pedido(
        sesion,
        eta_utilizada=_medianoche(dt.date(2026, 9, 1)),
        lead_time_destino_dias=7,
        fecha_proyectada_disponible=dt.date(2026, 9, 8),
        estado_calculado="CERRADO",
        motivo_cierre="CIERRE_FORZADO",
    )

    cuerpo = (await api.get(f"{URL}/{pedido.id}")).json()

    assert cuerpo["cierre"]["motivo_cierre"] == "CIERRE_FORZADO"
    assert cuerpo["calculo"]["al_dia"] is True
    assert "RN-13" in cuerpo["calculo"]["desglose"]


async def test_los_endpoints_aparecen_en_openapi(client) -> None:
    """`TASK-04`: documentados sin escribir el esquema a mano."""
    rutas = (await client.get("/openapi.json")).json()["paths"]

    assert f"{URL}" in rutas
    assert f"{URL}/{{id_pedido}}" in rutas
