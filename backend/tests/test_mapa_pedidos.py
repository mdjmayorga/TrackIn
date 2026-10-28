"""Los embarques en los mapas del panel — `US-25`.

Un marcador por embarque (un BL lleva varias líneas), coloreado por el estado
más urgente de sus pedidos, con los mismos filtros que la grilla y marcado si
su lectura es vieja. Reutiliza los datos de `test_pedidos_api`.
"""

from __future__ import annotations

import datetime as dt

import pytest

import test_pedidos_api as base
from app.services import historial
from app.services.consulta_pedidos import estado_mas_urgente

pytestmark = pytest.mark.integration

_destino = base._destino
_elemento = base._elemento
_CUMPLIMIENTOS = {"A_TIEMPO", "EN_RIESGO", "RETRASADO"}


async def _pedido(sesion, oc: str, posicion: int = 10, **kwargs):
    """`base._pedido` con una etapa coherente: con embarque no hay `SIN_TRACKING`."""
    if kwargs.get("id_elemento_rastreado") is not None:
        kwargs.setdefault("etapa_viaje", "EN_TRANSITO")
        kwargs.setdefault("estado_calculado", "EN_TRANSITO")
        if kwargs["estado_calculado"] in _CUMPLIMIENTOS:
            kwargs.setdefault("estado_cumplimiento", kwargs["estado_calculado"])
    return await base._pedido(sesion, oc, posicion, **kwargs)


#: El cliente de Compras con los pedidos vaciados, el mismo de las pruebas de la grilla.
api = base.api

URL = "/api/v1/pedidos/mapa"
AHORA = dt.datetime.now(dt.UTC)


async def _buque(sesion, referencia: str, **kwargs):
    base = {
        "tipo_tracking_externo": "BL",
        "tracking_externo": referencia,
        "nombre": "MSC PRUEBA",
        "posicion_actual": historial.punto_wkt(-79.5, 9.3),
        "ultima_actualizacion_api": AHORA - dt.timedelta(hours=1),
    }
    base.update(kwargs)
    return await _elemento(sesion, **base)


async def test_un_marcador_por_embarque_con_el_estado_mas_urgente(api, sesion) -> None:
    buque = await _buque(sesion, "BLMAPA0001")
    await _pedido(
        sesion, "4588900001", 10, id_elemento_rastreado=buque.id, estado_calculado="A_TIEMPO"
    )
    await _pedido(
        sesion, "4588900001", 20, id_elemento_rastreado=buque.id, estado_calculado="EN_RIESGO"
    )

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    assert len(cuerpo["marcadores"]) == 1
    marcador = cuerpo["marcadores"][0]
    assert (marcador["latitud"], marcador["longitud"]) == (9.3, -79.5)
    assert marcador["estado"] == "EN_RIESGO"
    assert marcador["nombre"] == "MSC PRUEBA"
    assert [(p["oc_numero"], p["posicion_oc"]) for p in marcador["pedidos"]] == [
        ("4588900001", 10),
        ("4588900001", 20),
    ]


async def test_cuenta_los_que_no_tienen_posicion(api, sesion) -> None:
    await _buque(sesion, "BLMAPA0002")
    sin_lectura = await _elemento(sesion, tipo_tracking_externo="BL", tracking_externo="BLMAPA03")
    await _pedido(sesion, "4588900002", 10)  # sin referencia
    await _pedido(sesion, "4588900003", 10, id_elemento_rastreado=sin_lectura.id)

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    assert cuerpo["marcadores"] == []
    assert cuerpo["sin_posicion"] == 2


async def test_cada_via_tiene_su_mapa(api, sesion) -> None:
    aeropuerto = await _destino(sesion, "MROC")
    vuelo = await _buque(
        sesion, "020-11112222", tipo_tracking_externo="MAWB", via_transporte="AEREO"
    )
    await _pedido(sesion, "4588900004", 10, destino=aeropuerto, id_elemento_rastreado=vuelo.id)

    maritimo = (await api.get(f"{URL}/MARITIMO")).json()
    aereo = (await api.get(f"{URL}/AEREO")).json()

    assert maritimo["marcadores"] == []
    assert [m["referencia"] for m in aereo["marcadores"]] == ["020-11112222"]


async def test_respeta_los_filtros_de_la_grilla(api, sesion) -> None:
    uno = await _buque(sesion, "BLMAPA0005")
    otro = await _buque(sesion, "BLMAPA0006", posicion_actual=historial.punto_wkt(-83.0, 10.0))
    await _pedido(sesion, "4588900005", 10, id_elemento_rastreado=uno.id)
    await _pedido(sesion, "4588900006", 10, id_elemento_rastreado=otro.id)

    cuerpo = (await api.get(f"{URL}/MARITIMO", params={"oc": "4588900006"})).json()

    assert [m["referencia"] for m in cuerpo["marcadores"]] == ["BLMAPA0006"]


async def test_sin_filtro_de_estado_no_salen_los_terminales(api, sesion) -> None:
    buque = await _buque(sesion, "BLMAPA0007")
    await _pedido(
        sesion,
        "4588900007",
        10,
        id_elemento_rastreado=buque.id,
        estado_calculado="CANCELADO",
        motivo_cierre="CANCELACION",
    )

    assert (await api.get(f"{URL}/MARITIMO")).json()["marcadores"] == []


@pytest.mark.parametrize(
    ("horas", "activo", "desactualizada"),
    [
        (1, True, False),
        (11, True, False),
        (13, True, True),  # frecuencia marítima por omisión: 360 min → umbral de 12 h
        (13, False, False),  # ya arribó: no se consulta más, lo viejo es lo esperado
    ],
)
async def test_marca_la_lectura_vieja(api, sesion, horas, activo, desactualizada) -> None:
    buque = await _buque(
        sesion,
        "BLMAPA0008",
        ultima_actualizacion_api=AHORA - dt.timedelta(hours=horas),
        activo=activo,
    )
    await _pedido(sesion, "4588900008", 10, id_elemento_rastreado=buque.id)

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    assert cuerpo["umbral_desactualizada_h"] == 12
    assert cuerpo["marcadores"][0]["desactualizada"] is desactualizada


async def test_al_pasar_a_proceso_aduanal_sale_del_mapa(api, sesion) -> None:
    """Decisión del 28/10/2026: la carga ya salió del puerto. Las otras líneas del BL siguen."""
    buque = await _buque(sesion, "BLMAPA0030")
    await _pedido(
        sesion,
        "4588900030",
        10,
        id_elemento_rastreado=buque.id,
        etapa_viaje="EN_DESTINO",
        estado_calculado="EN_DESTINO",
    )
    await _pedido(
        sesion,
        "4588900030",
        20,
        id_elemento_rastreado=buque.id,
        etapa_viaje="EN_PROCESO_ADUANAL",
        estado_calculado="EN_PROCESO_ADUANAL",
    )
    otro = await _buque(sesion, "BLMAPA0031")
    await _pedido(
        sesion,
        "4588900031",
        10,
        id_elemento_rastreado=otro.id,
        etapa_viaje="EN_PROCESO_ADUANAL",
        estado_calculado="EN_PROCESO_ADUANAL",
    )

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    (marcador,) = cuerpo["marcadores"]
    assert marcador["referencia"] == "BLMAPA0030"
    assert [p["posicion_oc"] for p in marcador["pedidos"]] == [10]
    # Los que salieron del mapa no cuentan como «sin posición».
    assert cuerpo["sin_posicion"] == 0


async def test_una_via_sin_mapa_se_rechaza(api) -> None:
    assert (await api.get(f"{URL}/TERRESTRE")).status_code == 422


def test_el_orden_de_urgencia() -> None:
    assert estado_mas_urgente(["A_TIEMPO", "RETRASADO", "EN_RIESGO"]) == "RETRASADO"
    assert estado_mas_urgente(["EN_TRANSITO", "A_TIEMPO"]) == "A_TIEMPO"
    assert estado_mas_urgente(["EN_ORIGEN", "EN_DESTINO"]) == "EN_DESTINO"


# --- US-26: el mapa aéreo ----------------------------------------------------------------


def _trayecto(salida: dt.datetime, llegada: dt.datetime) -> list[dict]:
    return [
        {
            "vuelo": "LH518",
            "origen": "FRA",
            "destino": "SJO",
            "salida": salida.isoformat(),
            "llegada": llegada.isoformat(),
            "ruta": [[8.0, 50.0], [-84.0, 10.0]],
        }
    ]


async def test_un_vuelo_en_curso_se_ubica_estimado_sobre_su_ruta(api, sesion) -> None:
    # La hora de ahora y no la del módulo: la suite completa tarda minutos y el
    # avión «a la mitad» ya habría avanzado.
    ahora = dt.datetime.now(dt.UTC)
    aeropuerto = await _destino(sesion, "MROC")
    vuelo = await _elemento(
        sesion,
        tipo_tracking_externo="MAWB",
        tracking_externo="020-33334444",
        via_transporte="AEREO",
        ultima_actualizacion_api=ahora,
        trayecto_aereo=_trayecto(ahora - dt.timedelta(hours=5), ahora + dt.timedelta(hours=5)),
    )
    await _pedido(sesion, "4588900010", 10, destino=aeropuerto, id_elemento_rastreado=vuelo.id)

    (marcador,) = (await api.get(f"{URL}/AEREO")).json()["marcadores"]

    assert marcador["posicion_estimada"] is True
    assert (marcador["situacion"], marcador["vuelo"]) == ("EN_VUELO", "LH518")
    assert marcador["longitud"] == pytest.approx(-38.0, abs=0.1)
    # La ruta va en el orden de Leaflet: latitud primero.
    assert marcador["ruta"] == [[50.0, 8.0], [10.0, -84.0]]


async def test_un_vuelo_concluido_queda_en_el_destino(api, sesion) -> None:
    aeropuerto = await _destino(sesion, "MROC")
    vuelo = await _elemento(
        sesion,
        tipo_tracking_externo="MAWB",
        tracking_externo="020-55556666",
        via_transporte="AEREO",
        ultima_actualizacion_api=AHORA,
        trayecto_aereo=_trayecto(AHORA - dt.timedelta(days=2), AHORA - dt.timedelta(days=1)),
    )
    await _pedido(sesion, "4588900011", 10, destino=aeropuerto, id_elemento_rastreado=vuelo.id)

    (marcador,) = (await api.get(f"{URL}/AEREO")).json()["marcadores"]

    assert (marcador["situacion"], marcador["lugar"]) == ("FINALIZADO", "SJO")
    assert (marcador["latitud"], marcador["longitud"]) == (10.0, -84.0)
    assert marcador["ruta"] is None


async def test_la_lectura_aerea_vieja_se_marca_con_su_propia_frecuencia(api, sesion) -> None:
    aeropuerto = await _destino(sesion, "MROC")
    vuelo = await _elemento(
        sesion,
        tipo_tracking_externo="MAWB",
        tracking_externo="020-77778888",
        via_transporte="AEREO",
        ultima_actualizacion_api=AHORA - dt.timedelta(hours=3),
        trayecto_aereo=_trayecto(AHORA - dt.timedelta(hours=1), AHORA + dt.timedelta(hours=9)),
    )
    await _pedido(sesion, "4588900012", 10, destino=aeropuerto, id_elemento_rastreado=vuelo.id)

    cuerpo = (await api.get(f"{URL}/AEREO")).json()

    # Frecuencia aérea por omisión: 60 min → umbral de 2 h.
    assert cuerpo["umbral_desactualizada_h"] == 2
    assert cuerpo["marcadores"][0]["desactualizada"] is True


async def test_un_marcador_maritimo_no_es_estimado(api, sesion) -> None:
    buque = await _buque(sesion, "BLMAPA0020")
    await _pedido(sesion, "4588900020", 10, id_elemento_rastreado=buque.id)

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    assert marcador["posicion_estimada"] is False
    assert marcador["situacion"] is None
