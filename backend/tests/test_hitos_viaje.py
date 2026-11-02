"""Pruebas de los hitos del viaje en la línea de tiempo — `US-29`.

Tres capas: lo que el colector guarda en `hitos_viaje` (con la guía grabada
PEK → FRA → SJO), cómo `hitos_viaje.describir` lo dice en castellano, y que la
bitácora del detalle los intercala con las intervenciones.
"""

from __future__ import annotations

import datetime as dt

import pytest

import test_intervenciones as base
from app.models.elemento_rastreado import ElementoRastreado
from app.services import hitos_viaje
from app.services.rastreo import colector_shipsgo
from app.services.rastreo.shipsgo import VIA_MARITIMA, Hito, LecturaEmbarque, interpretar
from test_shipsgo_aereo import _aereo

api = base.api
_url = base._url

CR = dt.timezone(dt.timedelta(hours=-6))
FINALES = frozenset({"MROC", "CRMOB", "CRCAL", "CRLIO"})


def _hito(evento: str, puerto: str, dia: int, *, ocurrido: bool = True, pais: str = "CO") -> Hito:
    return Hito(
        evento=evento,
        ocurrido=ocurrido,
        instante=dt.datetime(2026, 9, dia, 12, tzinfo=CR),
        puerto=puerto,
        puerto_nombre=puerto,
        buque="MAERSK NACALA",
        imo=None,
        pais=pais,
    )


# --- Lo que guarda el colector -------------------------------------------------


def test_de_la_guia_grabada_quedan_las_salidas_y_las_llegadas_con_el_destino_marcado() -> None:
    hitos = colector_shipsgo.hitos_del_viaje(interpretar(*_aereo()), FINALES)

    # Lo previo a la salida (`RCS`, `MAN`) queda fuera: el primer hito es la salida.
    assert hitos[0]["evento"] == "DEP"
    assert hitos[0]["puerto"] == "PEK"
    assert {h["evento"] for h in hitos} <= {"DEP", "ARR", "RCF", "DLV"}
    # Las llegadas a Fráncfort son transbordo; las de San José, destino final.
    assert {h["puerto"] for h in hitos if h["destino_final"]} == {"SJO"}
    assert all(h["pais"] for h in hitos)
    assert [h["instante"] for h in hitos] == sorted(h["instante"] for h in hitos)


def test_un_bl_con_varios_contenedores_no_repite_los_hitos() -> None:
    """ShipsGo repite cada movimiento por contenedor."""
    zarpe = _hito("DEPA", "COCTG", 7)
    lectura = LecturaEmbarque(hitos=[zarpe, zarpe, _hito("ARRV", "CRPMN", 18, pais="CR")])
    lectura.via = VIA_MARITIMA

    hitos = colector_shipsgo.hitos_del_viaje(lectura, FINALES)

    assert [h["evento"] for h in hitos] == ["DEPA", "ARRV"]
    # `CRPMN` es Moín (`CRMOB`) en el maestro.
    assert hitos[1]["destino_final"] is True


def test_los_hitos_previstos_no_entran() -> None:
    lectura = LecturaEmbarque(
        hitos=[_hito("DEPA", "COCTG", 7), _hito("ARRV", "CRPMN", 18, ocurrido=False)]
    )
    lectura.via = VIA_MARITIMA

    assert [h["evento"] for h in colector_shipsgo.hitos_del_viaje(lectura, FINALES)] == ["DEPA"]


# --- Cómo se dicen -------------------------------------------------------------

_PAISES = {"CN": "China", "DE": "Alemania", "CR": "Costa Rica"}


def _guardado(evento: str, puerto: str, nombre: str, pais: str, **extra) -> dict:
    return {
        "evento": evento,
        "instante": "2026-10-30T14:33:00+01:00",
        "puerto": puerto,
        "puerto_nombre": nombre,
        "pais": pais,
        "pais_nombre": extra.pop("pais_nombre", None),
        "vehiculo": "LH518",
        "destino_final": False,
        **extra,
    }


def test_la_primera_salida_es_la_salida_del_origen_y_la_llegada_final_se_destaca() -> None:
    descritos = hitos_viaje.describir(
        [
            _guardado("DEP", "PVG", "Shanghai Pudong International Airport", "CN"),
            _guardado("ARR", "FRA", "Frankfurt Airport", "DE"),
            _guardado("DEP", "FRA", "Frankfurt Airport", "DE"),
            _guardado("ARR", "SJO", "Juan Santamaría", "CR", destino_final=True),
            _guardado("RCF", "SJO", "Juan Santamaría", "CR", destino_final=True),
        ],
        _PAISES,
    )

    assert [d.texto for d in descritos] == [
        "Salida del origen: despegó de Shanghai Pudong International Airport (PVG), China",
        "Aterrizó en Frankfurt Airport (FRA), Alemania",
        "Despegó de Frankfurt Airport (FRA), Alemania",
        "Llegada a destino: aterrizó en Juan Santamaría (SJO), Costa Rica",
        "Recibido del vuelo en Juan Santamaría (SJO), Costa Rica",
    ]
    assert descritos[0].vehiculo == "Vuelo LH518"


def test_el_puerto_maritimo_se_dice_sin_mayusculas_ni_el_pais_repetido() -> None:
    (descrito,) = hitos_viaje.describir(
        [_guardado("DEPA", "COCTG", "CARTAGENA (COLOMBIA)", "CO", pais_nombre="Colombia")],
        _PAISES,
    )

    # El maestro no tiene Colombia: se usa el nombre de ShipsGo.
    assert descrito.texto == "Salida del origen: zarpó de Cartagena (COCTG), Colombia"
    assert descrito.vehiculo == "Nave LH518"


def test_un_hito_sin_fecha_o_desconocido_no_se_dice() -> None:
    sin_fecha = {**_guardado("DEP", "PVG", "PVG", "CN"), "instante": None}
    desconocido = _guardado("MAN", "PVG", "PVG", "CN")

    assert hitos_viaje.describir([sin_fecha, desconocido], _PAISES) == []


# --- En la línea de tiempo del detalle -------------------------------------------


async def test_la_linea_de_tiempo_intercala_los_hitos_con_las_intervenciones(api, sesion) -> None:
    cliente, _ = api
    guia = ElementoRastreado(
        tipo_tracking_externo="MAWB",
        tracking_externo="020-55557777",
        via_transporte="AEREO",
        hitos_viaje=[
            _guardado("DEP", "PVG", "Shanghai Pudong International Airport", "CN"),
            {
                **_guardado("ARR", "SJO", "Juan Santamaría", "CR", destino_final=True),
                "instante": "2026-10-31T01:09:00+00:00",
            },
        ],
    )
    sesion.add(guia)
    await sesion.flush()
    pedido = await base._pedido(sesion, id_elemento_rastreado=guia.id, etapa_viaje="EN_TRANSITO")

    bitacora = (await cliente.get(_url(pedido, "bitacora"))).json()

    hitos = [a for a in bitacora if a["tipo"] == "HITO_VIAJE"]
    assert [a["motivo"].split(":")[0] for a in hitos] == ["Salida del origen", "Llegada a destino"]
    assert {(a["usuario"], a["rol"]) for a in hitos} == {("shipsgo", "SISTEMA")}
    fechas = [a["fecha_hora"] for a in bitacora]
    assert fechas == sorted(fechas, key=dt.datetime.fromisoformat)


async def test_sin_rastreo_la_linea_de_tiempo_solo_trae_intervenciones(api, sesion) -> None:
    cliente, _ = api
    pedido = await base._pedido(sesion)

    bitacora = (await cliente.get(_url(pedido, "bitacora"))).json()

    assert all(a["tipo"] != "HITO_VIAJE" for a in bitacora)


@pytest.mark.parametrize("vuelta", [1, 2])
async def test_un_hito_que_la_fuente_retira_no_queda(sesion, vuelta: int) -> None:
    """Segundo criterio de `US-29`: la lista se reemplaza en cada lectura."""
    guia = ElementoRastreado(
        tipo_tracking_externo="MAWB",
        tracking_externo=f"020-5555888{vuelta}",
        via_transporte="AEREO",
    )
    sesion.add(guia)
    await sesion.flush()
    shipment = _aereo()[0]

    await colector_shipsgo.procesar(sesion, guia, shipment)
    antes = len(guia.hitos_viaje or [])
    sin_el_ultimo = {**shipment, "movements": shipment["movements"][:-1]}
    await colector_shipsgo.procesar(sesion, guia, sin_el_ultimo)

    assert len(guia.hitos_viaje or []) == antes - 1
