"""Los embarques en los mapas del panel — `US-25`.

Un marcador por embarque (un BL lleva varias líneas), coloreado por el estado
más urgente de sus pedidos, con los mismos filtros que la grilla y marcado si
su lectura es vieja. Reutiliza los datos de `test_pedidos_api`.
"""

from __future__ import annotations

import datetime as dt

import pytest
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select

import test_pedidos_api as base
from app.models.maestro_destino import MaestroDestino
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


# --- El destino final y la ruta completa (02/11/2026) -------------------------

_HASTA_FRANCFORT = [
    {
        "vuelo": "LH8401",
        "origen": "PVG",
        "destino": "FRA",
        "salida": (AHORA - dt.timedelta(days=6)).isoformat(),
        "llegada": (AHORA - dt.timedelta(days=5)).isoformat(),
        "ruta": [[121.8, 31.1], [8.6, 50.0]],
    }
]


async def _guia_hasta_francfort(sesion, numero: str, oc: str, **kwargs):
    aeropuerto = await _destino(sesion, "MROC")
    guia = await _elemento(
        sesion,
        tipo_tracking_externo="MAWB",
        tracking_externo=numero,
        via_transporte="AEREO",
        ultima_actualizacion_api=AHORA,
        trayecto_aereo=_HASTA_FRANCFORT,
        **kwargs,
    )
    return await _pedido(sesion, oc, 10, destino=aeropuerto, id_elemento_rastreado=guia.id)


async def test_un_trazado_cortado_en_el_transbordo_espera_ahi(api, sesion) -> None:
    """Como la guía `78469391954`: el trazado termina en un transbordo y no llegó."""
    await _guia_hasta_francfort(sesion, "784-11112222", "4588900020")

    (marcador,) = (await api.get(f"{URL}/AEREO")).json()["marcadores"]

    assert (marcador["situacion"], marcador["lugar"]) == ("EN_TIERRA", "FRA")
    assert (marcador["latitud"], marcador["longitud"]) == (50.0, 8.6)


async def test_si_ya_llego_se_dibuja_en_el_destino_del_pedido(api, sesion) -> None:
    """Como la guía `020-05128546`: llegó a SJO, pero el trazado terminaba en Fráncfort."""
    await _guia_hasta_francfort(
        sesion, "020-11113333", "4588900021", ata_api=AHORA - dt.timedelta(days=3)
    )

    (marcador,) = (await api.get(f"{URL}/AEREO")).json()["marcadores"]

    assert (marcador["situacion"], marcador["lugar"]) == ("FINALIZADO", "SJO")
    assert marcador["latitud"] == pytest.approx(10.0, abs=0.1)
    assert marcador["longitud"] == pytest.approx(-84.2, abs=0.1)


async def test_el_marcador_aereo_trae_la_ruta_completa(api, sesion) -> None:
    await _guia_hasta_francfort(sesion, "784-11114444", "4588900022")

    (marcador,) = (await api.get(f"{URL}/AEREO")).json()["marcadores"]

    (tramo,) = marcador["trayecto"]
    assert (tramo["vuelo"], tramo["origen"], tramo["destino"]) == ("LH8401", "PVG", "FRA")
    # En el orden de Leaflet: latitud primero.
    assert tramo["ruta"] == [[31.1, 121.8], [50.0, 8.6]]


async def test_el_detalle_aereo_trae_la_ruta_y_donde_esta(api, sesion) -> None:
    pedido = await _guia_hasta_francfort(sesion, "784-11115555", "4588900023")

    rastreo = (await api.get(f"/api/v1/pedidos/{pedido.id}")).json()["rastreo"]

    assert [t["destino"] for t in rastreo["trayecto"]] == ["FRA"]
    assert rastreo["posicion_aerea"]["situacion"] == "EN_TIERRA"
    assert rastreo["posicion_aerea"]["lugar"] == "FRA"


# --- US-27: lo que muestra el recuadro del marcador ---------------------------


async def test_cada_pedido_del_marcador_trae_lo_que_pide_rf_18(api, sesion) -> None:
    """OC, material, proveedor, ETA, fecha proyectada y estado, y el id para el detalle."""
    buque = await _buque(sesion, "BLMAPA0027")
    pedido = await _pedido(
        sesion,
        "4588902700",
        10,
        id_elemento_rastreado=buque.id,
        estado_calculado="A_TIEMPO",
        eta_utilizada=dt.datetime(2026, 11, 5, tzinfo=dt.UTC),
        fecha_proyectada_disponible=dt.date(2026, 11, 7),
    )

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    (linea,) = marcador["pedidos"]
    assert linea["id"] == pedido.id
    assert linea["material"] == "Material uno"
    assert linea["proveedor"] == "Proveedor Uno"
    assert (linea["eta"], linea["fecha_proyectada"]) == ("2026-11-05", "2026-11-07")
    assert linea["estado_calculado"] == "A_TIEMPO"


async def test_sin_fechas_el_recuadro_las_trae_vacias(api, sesion) -> None:
    buque = await _buque(sesion, "BLMAPA0028")
    await _pedido(sesion, "4588902800", 10, id_elemento_rastreado=buque.id)

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    assert (marcador["pedidos"][0]["eta"], marcador["pedidos"][0]["fecha_proyectada"]) == (
        None,
        None,
    )


async def test_el_marcador_maritimo_trae_la_ruta_del_barco(api, sesion) -> None:
    """03/11/2026: elegir un embarque en el mapa dibuja su ruta, también en el marítimo."""
    buque = await _buque(
        sesion,
        "BLMAPA0029",
        trayecto_maritimo=[
            {
                "vuelo": "POLAR BRASIL · viaje 637N",
                "origen": "COCTG",
                "destino": "CRPMN",
                "salida": "2026-10-28T12:00:00-05:00",
                "llegada": "2026-11-04T12:00:00-06:00",
                "ruta": [[-75.5, 10.4], [-79.5, 9.3], [-83.0, 10.0]],
            }
        ],
    )
    await _pedido(sesion, "4588902900", 10, id_elemento_rastreado=buque.id)

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    (tramo,) = marcador["trayecto"]
    assert (tramo["vuelo"], tramo["origen"], tramo["destino"]) == (
        "POLAR BRASIL · viaje 637N",
        "COCTG",
        "CRPMN",
    )
    # En `(latitud, longitud)`, como la espera Leaflet; la posición sigue siendo la leída.
    assert tramo["ruta"][0] == [10.4, -75.5]
    assert (marcador["latitud"], marcador["longitud"]) == (9.3, -79.5)


async def test_relleno_por_etapa_y_anillo_por_el_peor_cumplimiento(api, sesion) -> None:
    """`wireframes.md` §2.2 y el Figma de los mapas (03/11/2026): el relleno y la ruta
    van con la etapa menos avanzada; el anillo, con el peor cumplimiento a bordo."""
    buque = await _buque(sesion, "BLMAPA0030")
    await _pedido(
        sesion,
        "4588903000",
        10,
        id_elemento_rastreado=buque.id,
        etapa_viaje="EN_DESTINO",
        estado_calculado="A_TIEMPO",
    )
    await _pedido(
        sesion,
        "4588903000",
        20,
        id_elemento_rastreado=buque.id,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="RETRASADO",
    )

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    assert (marcador["etapa"], marcador["cumplimiento"]) == ("EN_TRANSITO", "RETRASADO")
    # Cada pedido trae las dos dimensiones por separado, para el recuadro.
    assert [(p["etapa_viaje"], p["estado_cumplimiento"]) for p in marcador["pedidos"]] == [
        ("EN_DESTINO", "A_TIEMPO"),
        ("EN_TRANSITO", "RETRASADO"),
    ]


async def test_sin_fecha_proyectada_no_hay_anillo(api, sesion) -> None:
    buque = await _buque(sesion, "BLMAPA0031")
    await _pedido(sesion, "4588903100", 10, id_elemento_rastreado=buque.id)

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    assert (marcador["etapa"], marcador["cumplimiento"]) == ("EN_TRANSITO", None)


async def test_un_barco_que_llego_se_dibuja_en_el_puerto_de_destino(api, sesion) -> None:
    """03/11/2026: ShipsGo deja de dar la posición al terminar el embarque, y el mapa
    marítimo quedaba vacío con pedidos todavía «En destino». Como el aéreo, se dibuja
    en nuestro puerto hasta que pase a aduana."""
    buque = await _buque(
        sesion,
        "BLMAPA0032",
        posicion_actual=None,
        activo=False,
        ata_api=AHORA - dt.timedelta(days=30),
    )
    await _pedido(
        sesion,
        "4588903200",
        10,
        id_elemento_rastreado=buque.id,
        etapa_viaje="EN_DESTINO",
        estado_calculado="EN_DESTINO",
    )

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    (marcador,) = cuerpo["marcadores"]
    punto = cast(MaestroDestino.ubicacion, Geometry)
    moin = (
        await sesion.execute(
            select(func.ST_Y(punto), func.ST_X(punto)).where(MaestroDestino.codigo == "CRMOB")
        )
    ).one()
    assert (marcador["latitud"], marcador["longitud"]) == pytest.approx(tuple(moin))
    assert marcador["etapa"] == "EN_DESTINO"
    # Ya arribó: su lectura vieja no es un problema.
    assert marcador["desactualizada"] is False
    assert cuerpo["sin_posicion"] == 0


async def test_un_barco_sin_posicion_ni_llegada_no_se_dibuja(api, sesion) -> None:
    buque = await _buque(sesion, "BLMAPA0033", posicion_actual=None)
    await _pedido(sesion, "4588903300", 10, id_elemento_rastreado=buque.id)

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    assert cuerpo["marcadores"] == []
    assert cuerpo["sin_posicion"] == 1


# --- Un barco sin posición leída, ubicado con su itinerario (11/11/2026) ----------


def _itinerario(ahora: dt.datetime, *, zarpa_en: dt.timedelta) -> list[dict]:
    """Como `MAEU275293678`: Cartagena → Manzanillo (Panamá), y de ahí a Moín."""
    return [
        {
            "vuelo": "VARAMO · viaje 645W",
            "origen": "COCTG",
            "destino": "PAMIT",
            "salida": (ahora - dt.timedelta(days=4)).isoformat(),
            "llegada": (ahora - dt.timedelta(days=1)).isoformat(),
            "ruta": [[-75.5, 10.4], [-79.9, 9.4]],
        },
        {
            "vuelo": "MAERSK MONTE ALTO · viaje 643S",
            "origen": "PAMIT",
            "destino": "CRPMN",
            "salida": (ahora + zarpa_en).isoformat(),
            "llegada": (ahora + zarpa_en + dt.timedelta(days=4)).isoformat(),
            "ruta": [[-79.9, 9.4], [-83.1, 10.0]],
        },
    ]


async def test_un_barco_sin_posicion_espera_en_el_puerto_del_transbordo(api, sesion) -> None:
    """La carga de la OC 4500016174: en Manzanillo hasta que zarpe el siguiente buque."""
    ahora = dt.datetime.now(dt.UTC)
    buque = await _buque(
        sesion,
        "BLMAPA0034",
        posicion_actual=None,
        trayecto_maritimo=_itinerario(ahora, zarpa_en=dt.timedelta(days=4)),
    )
    await _pedido(sesion, "4588903400", 10, id_elemento_rastreado=buque.id)

    cuerpo = (await api.get(f"{URL}/MARITIMO")).json()

    (marcador,) = cuerpo["marcadores"]
    assert marcador["posicion_estimada"] is True
    assert (marcador["situacion"], marcador["lugar"]) == ("EN_PUERTO", "PAMIT")
    assert (marcador["latitud"], marcador["longitud"]) == (9.4, -79.9)
    assert cuerpo["sin_posicion"] == 0


async def test_un_barco_sin_posicion_navega_sobre_su_ruta(api, sesion) -> None:
    ahora = dt.datetime.now(dt.UTC)
    buque = await _buque(
        sesion,
        "BLMAPA0035",
        posicion_actual=None,
        trayecto_maritimo=_itinerario(ahora, zarpa_en=-dt.timedelta(days=2)),
    )
    await _pedido(sesion, "4588903500", 10, id_elemento_rastreado=buque.id)

    (marcador,) = (await api.get(f"{URL}/MARITIMO")).json()["marcadores"]

    assert (marcador["situacion"], marcador["vuelo"]) == (
        "NAVEGANDO",
        "MAERSK MONTE ALTO · viaje 643S",
    )
    # A la mitad del tramo de cuatro días.
    assert marcador["longitud"] == pytest.approx(-81.5, abs=0.1)
    assert marcador["ruta"] == [[9.4, -79.9], [10.0, -83.1]]
