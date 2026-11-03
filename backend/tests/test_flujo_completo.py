"""El flujo completo, de punta a punta — `TASK-06` (RNF-18, criterios §10 del SRS).

Un solo recorrido, por las mismas puertas que usa la gente y el worker:

1. **Ingesta.** Compras descarga la plantilla del Z-tracking (`US-59`), la llena
   con dos líneas —una con contenedor, otra sin referencia— y la sube.
2. **Rastreo en viaje.** Un ciclo del worker lee el contenedor en ShipsGo (el
   payload grabado del spike `TASK-28`: Santos → Cartagena → Moín, navegando).
   El pedido pasa a «En tránsito», con la ETA de la fuente y su posición.
3. **Llegada y cálculo.** Otro ciclo, cuando ShipsGo confirma el arribo a Moín:
   «En destino», y la fecha proyectada pasa a salir de la ATA más el lead time
   del destino (RN-01, RN-14). El cumplimiento sale de compararla con la fecha
   de entrega.
4. **Consulta.** La grilla, los indicadores, el detalle con su desglose, el mapa
   y la línea de tiempo dicen lo mismo.
5. **Cierre.** Paso a aduana, recepción en planta y liberación de Calidad lo
   cierran (RN-10, RN-13), y el worker deja de consultarlo.

Las piezas se prueban una por una en sus propios archivos; esta prueba existe
para demostrar que **encajan**: que lo que deja una etapa es lo que la siguiente
espera. ShipsGo no se llama: el doble sirve el embarque grabado.
"""

from __future__ import annotations

import datetime as dt
import io
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from sqlalchemy import delete, select

from app.api.cargas import resolutor_de_destinos
from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import get_db
from app.main import app
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.pedido_transito import PedidoTransito
from app.models.sesion import Sesion
from app.services.ingesta.ztracking import PLANTILLA
from app.workers import rastreo
from conftest import vaciar_auditoria
from test_cargas_api import XLSX, _SesionDePrueba, _usuario
from test_worker_rastreo import CONTENEDOR, MEDIODIA, ShipsGoFalso, fabrica, salud_limpia

pytestmark = pytest.mark.integration

# Las fixtures del worker, prestadas: la fábrica de sesiones sobre la de la prueba
# y el registro de salud limpio.
__all__ = ["fabrica", "salud_limpia"]

OC = "4500099001"
ENTREGA = dt.date(2026, 10, 30)
CR = dt.timezone(dt.timedelta(hours=-6))


@pytest.fixture
async def compras(sesion) -> AsyncGenerator[AsyncClient, None]:
    """El cliente de Compras, que carga el archivo e interviene (decisión del 21/10)."""
    await vaciar_auditoria(sesion)
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    usuario = await _usuario(sesion, "COMPRAS")
    prestada = await _SesionDePrueba(sesion).abrir()

    async def _misma_sesion():
        yield prestada

    app.dependency_overrides[get_db] = _misma_sesion
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=usuario, sesion=Sesion(id=0, id_usuario=usuario.id)
    )
    # La carga no consulta ShipsGo: el destino sale del incoterm.
    app.dependency_overrides[resolutor_de_destinos] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        for dependencia in (get_db, usuario_actual, resolutor_de_destinos):
            app.dependency_overrides.pop(dependencia, None)


def _linea(posicion: str, **valores: Any) -> dict[str, Any]:
    return {
        "oc_numero": OC,
        "posicion_oc": posicion,
        "proveedor_codigo": "1007052",
        "proveedor_nombre": "ROUSSELOT GELATINAS",
        "material_codigo": "11000371",
        "material_descripcion": "Colágeno hidrolizado bovino",
        "cantidad": 1000,
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.datetime(ENTREGA.year, ENTREGA.month, ENTREGA.day),
        "via_transporte": "MARITIMO",
        "incoterm": "CIF LIMON",
        "pais_origen": "BRASIL",
        "solicitud_pedido": "1000123456",
        **valores,
    }


async def _plantilla_llena(cliente: AsyncClient, *lineas: dict[str, Any]) -> bytes:
    """La plantilla que descarga Compras, con las líneas escritas debajo del encabezado."""
    respuesta = await cliente.get("/api/v1/cargas/plantilla")
    assert respuesta.status_code == 200, respuesta.text
    libro = load_workbook(io.BytesIO(respuesta.content))
    hoja = libro["PRODUCCION"]
    for linea in lineas:
        hoja.append([linea.get(campo) for campo, _ in PLANTILLA])
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


async def _detalle(cliente: AsyncClient, id_pedido: int) -> dict[str, Any]:
    respuesta = await cliente.get(f"/api/v1/pedidos/{id_pedido}")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


async def test_un_pedido_va_del_excel_al_cierre(compras, sesion, fabrica) -> None:
    cliente = compras

    # --- 1. Ingesta: la plantilla real, llena y subida ----------------------------
    contenido = await _plantilla_llena(
        cliente,
        _linea("10", tipo_referencia="CONTENEDOR", numero_referencia=CONTENEDOR),
        # Sin referencia: entra, pero no se rastrea (RN-02).
        _linea("20"),
    )
    carga = await cliente.post(
        "/api/v1/cargas", files={"archivo": ("2026 - WK44.xlsx", contenido, XLSX)}
    )

    assert carga.status_code == 201, carga.text
    assert (carga.json()["estado"], carga.json()["insertadas"]) == ("APLICADA", 2)
    rastreado, sin_rastreo = (
        await sesion.scalars(
            select(PedidoTransito)
            .where(PedidoTransito.oc_numero == OC)
            .order_by(PedidoTransito.posicion_oc)
        )
    ).all()
    assert rastreado.etapa_viaje == "EN_ORIGEN"  # RN-03: con referencia, sin salida
    assert sin_rastreo.etapa_viaje == "SIN_TRACKING"  # RN-02
    assert rastreado.fecha_proyectada_disponible is None  # nada que proyectar todavía

    # --- 2. Rastreo en viaje: el worker lee el contenedor en ShipsGo --------------
    shipsgo = ShipsGoFalso()
    fuentes = rastreo.Fuentes(shipsgo=shipsgo)
    en_viaje = await rastreo.ejecutar_ciclo(fabrica, fuentes, instante=MEDIODIA)

    assert en_viaje.consultados == {"shipsgo": 1}
    await sesion.refresh(rastreado)
    elemento = await sesion.get(ElementoRastreado, rastreado.id_elemento_rastreado)
    assert elemento is not None
    assert rastreado.etapa_viaje == "EN_TRANSITO"  # RN-04
    # La ETA es a Moín, uno de nuestros destinos: entra al cálculo.
    assert elemento.eta_api is not None and elemento.ata_api is None
    detalle = await _detalle(cliente, rastreado.id)
    assert detalle["calculo"]["origen"] == "ETA_FUENTE"
    navegando = (await cliente.get("/api/v1/pedidos/mapa/MARITIMO")).json()["marcadores"]
    assert [m["etapa"] for m in navegando] == ["EN_TRANSITO"]

    # --- 3. Llegada: ShipsGo confirma el arribo a Moín ----------------------------
    arribo = None
    for contenedor in shipsgo.shipment["containers"]:
        for movimiento in contenedor["movements"]:
            if movimiento["location"]["code"] == "CRPMN":
                movimiento["status"] = "ACT"
                arribo = arribo or dt.datetime.fromisoformat(movimiento["timestamp"])
    assert arribo is not None
    llegada_ciclo = await rastreo.ejecutar_ciclo(
        fabrica, fuentes, instante=MEDIODIA + dt.timedelta(days=1)
    )

    assert llegada_ciclo.arribos == 1
    await sesion.refresh(rastreado)
    await sesion.refresh(elemento)
    assert elemento.ata_api is not None
    # La llegada a Moín es la de uno de nuestros destinos, no la del transbordo
    # en Cartagena (regla del destino final, 02/11/2026).
    assert {h["puerto"] for h in elemento.hitos_viaje if h["destino_final"]} == {"CRPMN"}

    destino = await sesion.get(MaestroDestino, rastreado.id_destino)
    assert destino is not None
    esperada = elemento.ata_api.date() + dt.timedelta(days=destino.lead_time_dias)
    assert rastreado.etapa_viaje == "EN_DESTINO"  # RN-05
    assert rastreado.fecha_proyectada_disponible == esperada  # RN-01 con la ATA (RN-14)
    # RN-07 a RN-09: el cumplimiento sale de comparar con la fecha de entrega.
    if esperada > ENTREGA:
        assert rastreado.estado_cumplimiento == "RETRASADO"
    else:
        assert rastreado.estado_cumplimiento in {"A_TIEMPO", "EN_RIESGO"}

    # --- 4. Consulta: grilla, indicadores, detalle, mapa y línea de tiempo --------
    grilla = (await cliente.get("/api/v1/pedidos")).json()
    assert grilla["total"] == 2
    filas = {f["posicion_oc"]: f for f in grilla["items"]}
    assert filas[10]["etapa_viaje"] == "EN_DESTINO"
    assert filas[20]["estado_calculado"] == "SIN_TRACKING"

    kpi = (await cliente.get("/api/v1/pedidos/indicadores")).json()
    assert kpi["activos"] == 2
    assert kpi["sin_proyeccion"] == 1  # el de la línea 20

    detalle = await _detalle(cliente, rastreado.id)
    assert detalle["calculo"]["origen"] == "ATA_FUENTE"
    assert detalle["calculo"]["fecha_proyectada"] == esperada.isoformat()
    assert detalle["calculo"]["al_dia"] is True
    assert detalle["rastreo"]["referencia"] == CONTENEDOR

    mapa = (await cliente.get("/api/v1/pedidos/mapa/MARITIMO")).json()
    (marcador,) = mapa["marcadores"]
    assert [p["id"] for p in marcador["pedidos"]] == [rastreado.id]
    assert (marcador["etapa"], marcador["cumplimiento"]) == (
        "EN_DESTINO",
        rastreado.estado_cumplimiento,
    )
    assert marcador["trayecto"]  # la ruta del barco, para dibujarla al elegirlo
    assert mapa["sin_posicion"] == 1  # el de la línea 20

    hitos = [
        a
        for a in (await cliente.get(f"/api/v1/pedidos/{rastreado.id}/bitacora")).json()
        if a["tipo"] == "HITO_VIAJE"
    ]
    assert hitos[0]["motivo"].startswith("Salida del origen")
    assert any(a["motivo"].startswith("Llegada a destino") for a in hitos)

    # --- 5. Cierre: aduana, planta y Calidad ----------------------------------------
    url = f"/api/v1/pedidos/{rastreado.id}"
    llegada = elemento.ata_api.astimezone(CR)
    recibido = llegada + dt.timedelta(days=3)
    liberado = recibido + dt.timedelta(days=2)

    paso = await cliente.post(f"{url}/paso-aduanal", json={"motivo": None})
    assert paso.json()["etapa_viaje"] == "EN_PROCESO_ADUANAL"
    # Ya salió del puerto: deja el mapa (28/10/2026).
    assert (await cliente.get("/api/v1/pedidos/mapa/MARITIMO")).json()["marcadores"] == []

    recepcion = await cliente.post(
        f"{url}/recepcion", json={"fecha": recibido.isoformat(), "cantidad": "1000"}
    )
    assert recepcion.status_code == 200, recepcion.text
    assert recepcion.json()["etapa_viaje"] == "RECIBIDO_EN_PLANTA"

    liberacion = await cliente.post(
        f"{url}/liberacion-calidad", json={"fecha": liberado.isoformat(), "cantidad": "1000"}
    )
    assert liberacion.status_code == 200, liberacion.text
    cerrado = liberacion.json()
    assert cerrado["estado_calculado"] == "CERRADO"  # RN-10
    assert Decimal(cerrado["cierre"]["cantidad_liberada"]) == Decimal("1000")

    # RN-13: terminal. No admite cambios y el worker ya no consulta su contenedor.
    otra = await cliente.post(f"{url}/ajuste-manual", json={"dias": 2})
    assert otra.status_code == 409
    lecturas = len(shipsgo.lecturas)
    await rastreo.ejecutar_ciclo(fabrica, fuentes, instante=MEDIODIA + dt.timedelta(days=30))
    assert len(shipsgo.lecturas) == lecturas

    # Cada intervención quedó en la bitácora, con quién la hizo (RF-14).
    manuales = [
        a["tipo"]
        for a in (await cliente.get(f"{url}/bitacora")).json()
        if a["usuario"] == "carga-compras"
    ]
    assert manuales == ["PASO_A_ADUANAL", "RECEPCION_PLANTA", "LIBERACION_CALIDAD"]
