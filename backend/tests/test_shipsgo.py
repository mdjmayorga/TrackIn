"""Pruebas de `app.services.rastreo.shipsgo` — `US-45` / RF-06, RF-20.

**Contra los payloads reales grabados**, no contra dobles escritos a mano. Los
capturó `TASK-28` el 14/09/2026 con referencias de Gutis y viven en
`scripts/spikes/task28/output/`. No quedan créditos para repetir las consultas,
así que estos archivos **son** el contrato medido: si alguien cambia el
intérprete y estas pruebas pasan, sigue leyendo lo que ShipsGo devuelve.

Las cuatro cargas cubren lo que hay que cubrir:

| Embarque | Qué aporta |
|---|---|
| `MRSU8507472` | Transbordo de 2 naves, **con** posición |
| `MRSU8132490` | Transbordo de **3** naves |
| `TGBU4872990` | Caldera y **sin** posición (`current: null`) |
| `020-50685434` | La vía aérea: misma forma, otros códigos |

Corren sin base y sin red.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from app.services.rastreo.shipsgo import (
    ETAPA_POR_EVENTO,
    EVENTOS_DE_ARRIBO,
    Hito,
    LecturaEmbarque,
    Vehiculo,
    es_arribo,
    esta_maduro,
    interpretar,
)

_SALIDA = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
_MADUROS = _SALIDA / "06_payload_personal.json"
_PENDIENTES = _SALIDA / "07_pendientes_personal.json"

pytestmark = pytest.mark.skipif(
    not (_MADUROS.exists() and _PENDIENTES.exists()),
    reason="faltan los payloads grabados del spike TASK-28",
)


def _cargar() -> dict[str, tuple[dict[str, Any], dict[str, Any] | None]]:
    """Los cuatro embarques, por su referencia."""
    casos: dict[str, tuple[dict[str, Any], dict[str, Any] | None]] = {}
    maduros = json.loads(_MADUROS.read_text(encoding="utf-8"))
    for embarque in maduros["embarques"]:
        casos[embarque["contenedor"]] = (
            embarque["payload_shipment"],
            embarque.get("payload_geojson"),
        )
    pendientes = json.loads(_PENDIENTES.read_text(encoding="utf-8"))
    for embarque in pendientes["embarques"]:
        payload = embarque["payload_shipment"]
        clave = payload.get("container_number") or payload.get("awb_number")
        casos[clave] = (payload, embarque.get("payload_geojson"))
    return casos


CASOS = _cargar() if _MADUROS.exists() and _PENDIENTES.exists() else {}

MAERSK_2_NAVES = "MRSU8507472"
MAERSK_3_NAVES = "MRSU8132490"
COSCO_SIN_POSICION = "TGBU4872990"
LUFTHANSA_AEREO = "020-50685434"


def _lectura(referencia: str) -> LecturaEmbarque:
    shipment, geojson = CASOS[referencia]
    return interpretar(shipment, geojson)


# --- Que los cuatro embarques grabados siguen ahí --------------------------


def test_estan_los_cuatro_embarques_medidos() -> None:
    """Si alguien borra un payload, las pruebas de abajo se saltarían en
    silencio y nadie lo notaría hasta que fallara en producción."""
    assert set(CASOS) == {
        MAERSK_2_NAVES,
        MAERSK_3_NAVES,
        COSCO_SIN_POSICION,
        LUFTHANSA_AEREO,
    }


# --- Los campos que `US-45` necesita ---------------------------------------


def test_la_eta_sale_de_la_fecha_predicha_de_descarga() -> None:
    """`route.port_of_discharge.date_of_discharge_predicted`.

    La predicha y no `date_of_discharge`: esta última puede traer el plan
    original y no lo que la naviera espera hoy.
    """
    lectura = _lectura(MAERSK_2_NAVES)
    assert lectura.eta is not None
    assert lectura.eta.date() == dt.date(2026, 9, 15)


def test_el_etd_sale_de_la_fecha_de_carga() -> None:
    """Lo que `US-43` necesita para la vista completa."""
    assert _lectura(MAERSK_2_NAVES).etd is not None


def test_el_puerto_de_destino_llega_normalizado() -> None:
    """Códigos UN/LOCODE, que es lo que se puede cruzar con el maestro."""
    assert _lectura(MAERSK_2_NAVES).puerto_destino == "CRPMN"
    assert _lectura(COSCO_SIN_POSICION).puerto_destino == "CRCAL"


def test_cierra_el_hueco_que_dejo_la_medicion_de_ais() -> None:
    """El AIS gratuito no ve Caldera; la fuente comercial sí la cubre.

    Es el argumento que cerró `TASK-28`: por eso `US-11` pasa a apoyarse en los
    hitos y no en la geocerca.
    """
    assert _lectura(COSCO_SIN_POSICION).puerto_destino_nombre == "PUERTO CALDERA"


def test_la_naviera_llega_con_nombre() -> None:
    assert _lectura(MAERSK_2_NAVES).naviera == "MAERSK LINE"
    assert _lectura(COSCO_SIN_POSICION).naviera == "COSCO"


def test_los_hitos_distinguen_lo_ocurrido_de_lo_estimado() -> None:
    """`ACT` contra `EST`: la separación exacta que RN-14 necesita."""
    lectura = _lectura(MAERSK_2_NAVES)

    assert len(lectura.hitos) == 8
    assert sum(1 for h in lectura.hitos if h.ocurrido) == 6
    assert sum(1 for h in lectura.hitos if not h.ocurrido) == 2


def test_el_buque_y_su_imo_llegan_en_los_hitos() -> None:
    """Lo que `elementos_rastreados` necesita: nombre e IMO."""
    lectura = _lectura(MAERSK_2_NAVES)
    con_buque = [h for h in lectura.hitos if h.buque]

    assert con_buque[0].buque == "MAERSK CHACHAI"
    assert con_buque[0].imo == 9525388


# --- El transbordo, que viene gratis (`US-30`) -----------------------------


def test_detecta_el_transbordo_de_dos_naves() -> None:
    lectura = _lectura(MAERSK_2_NAVES)

    assert [n.nombre for n in lectura.vehiculos] == ["MAERSK CHACHAI", "POLAR BRASIL"]
    assert lectura.hay_transbordo is True


def test_detecta_el_transbordo_de_tres_naves() -> None:
    """`US-30` está especificada como captura **manual**.

    Con esto puede pasar a detección automática: conviene reestimarla.
    """
    lectura = _lectura(MAERSK_3_NAVES)

    assert [n.nombre for n in lectura.vehiculos] == [
        "MAERSK CHACHAI",
        "MAERSK NACALA",
        "MAERSK MONTE PASCOAL",
    ]
    assert lectura.hay_transbordo is True


def test_las_naves_no_se_repiten_aunque_los_hitos_si() -> None:
    """Varios movimientos seguidos van en la misma nave: es un tramo, no dos."""
    lectura = _lectura(MAERSK_2_NAVES)
    hitos_con_buque = [h for h in lectura.hitos if h.buque]

    assert len(hitos_con_buque) > len(lectura.vehiculos)


# --- La etapa: la trampa del transbordo ------------------------------------


@pytest.mark.parametrize("referencia", [MAERSK_2_NAVES, MAERSK_3_NAVES, COSCO_SIN_POSICION])
def test_un_arrv_en_puerto_de_transbordo_no_da_por_llegado(referencia: str) -> None:
    """Los tres marítimos siguen `SAILING` y traen `ARRV ACT` intermedios.

    `MRSU8507472` arribó a Cartagena y `MRSU8132490` a Cartagena y Manzanillo.
    Mapear `ARRV` a `EN_DESTINO` sin mirar el puerto los daba por llegados a los
    tres mientras navegaban, y el estado ya no retrocedía.
    """
    lectura = _lectura(referencia)

    assert lectura.estado_fuente == "SAILING"
    assert lectura.etapa == "EN_TRANSITO"
    assert lectura.arribado is False
    assert lectura.ata is None


def test_hay_arrv_ocurridos_en_puertos_intermedios() -> None:
    """Fija el hecho del que depende la prueba anterior.

    Sin esto, aquella pasaría por vacuidad si el payload cambiara.
    """
    lectura = _lectura(MAERSK_3_NAVES)
    intermedios = [
        h
        for h in lectura.hitos
        if h.ocurrido and es_arribo(h, lectura.via) and h.puerto != lectura.puerto_destino
    ]

    assert len(intermedios) >= 2
    assert {h.puerto for h in intermedios} == {"COCTG", "PAMIT"}


def test_un_arrv_en_el_destino_si_da_por_llegado() -> None:
    """El mecanismo primario de arribo de `US-11`."""
    shipment, geojson = CASOS[MAERSK_2_NAVES]
    llegado = json.loads(json.dumps(shipment))
    for contenedor in llegado["containers"]:
        for movimiento in contenedor["movements"]:
            if movimiento["location"]["code"] == "CRPMN":
                movimiento["status"] = "ACT"

    lectura = interpretar(llegado, geojson)

    assert lectura.etapa == "EN_DESTINO"
    assert lectura.arribado is True
    assert lectura.ata is not None


def test_los_movimientos_de_patio_no_mueven_la_etapa() -> None:
    """`EMSH` y `GTIN` ocurren antes de que la carga navegue."""
    assert "EMSH" not in ETAPA_POR_EVENTO
    assert "GTIN" not in ETAPA_POR_EVENTO


def test_solo_arrv_y_disc_significan_llegada() -> None:
    assert set(EVENTOS_DE_ARRIBO) == {"ARRV", "DISC"}


# --- La posición, que NO está garantizada ----------------------------------


def test_la_posicion_sale_del_tramo_marcado_current() -> None:
    """El trayecto viene partido en `PAST`, `CURRENT` y `FUTURE`."""
    lectura = _lectura(MAERSK_2_NAVES)

    assert lectura.posicion == (-79.885643, 9.36328)
    assert lectura.vehiculo_actual is not None
    assert lectura.vehiculo_actual.nombre == "POLAR BRASIL"


def test_un_embarque_sin_posicion_se_lee_igual() -> None:
    """Medido en el BL de COSCO: `current: null` en todas sus *features*.

    Los hitos son obligatorios y la posición opcional. Es la razón de que
    `US-02` —AIS como respaldo del mapa— recupere sentido.
    """
    lectura = _lectura(COSCO_SIN_POSICION)

    assert lectura.posicion is None
    assert lectura.hitos, "sin posición, pero con hitos"
    assert lectura.eta is not None


def test_sin_posicion_la_vehiculo_actual_cae_a_la_ultima_del_trayecto() -> None:
    """Se sabe en qué nave va aunque no se sepa dónde está."""
    lectura = _lectura(COSCO_SIN_POSICION)

    assert lectura.vehiculo_actual is not None
    assert lectura.vehiculo_actual.nombre == "MEDKON ZOE"


def test_la_posicion_va_en_orden_geojson() -> None:
    """`(longitud, latitud)`, no al revés.

    Invertirlas colocaría el buque en el océano equivocado sin que nada falle:
    9,36 N / 79,88 O es el Caribe panameño; al revés cae en Somalia.
    """
    longitud, latitud = _lectura(MAERSK_2_NAVES).posicion  # type: ignore[misc]

    assert -85 < longitud < -75
    assert 5 < latitud < 15


# --- El auto-archivado -----------------------------------------------------


def test_un_embarque_entregado_llega_archivado() -> None:
    """ShipsGo archiva solo lo terminado, en la **misma** respuesta.

    El adaptador no puede asumir que siga consultable después del `DLV`: es un
    motivo más para que `historial_tracking` guarde el payload completo (RNF-13).
    """
    lectura = _lectura(LUFTHANSA_AEREO)

    assert lectura.estado_fuente == "DELIVERED"
    assert lectura.archivado_en is not None


def test_un_embarque_en_curso_no_llega_archivado() -> None:
    assert _lectura(MAERSK_2_NAVES).archivado_en is None


# --- El tercer estado: dado de alta pero sin datos -------------------------


def test_los_cuatro_embarques_grabados_estan_maduros() -> None:
    for referencia in CASOS:
        shipment, _ = CASOS[referencia]
        assert esta_maduro(shipment), referencia


def test_un_embarque_recien_dado_de_alta_no_esta_maduro() -> None:
    """A los 45 s del alta: `status: NEW`, `route: null`, `containers: []`.

    No es un fallo ni una respuesta vacía definitiva. Tratarlo como cualquiera
    de las dos da un falso negativo, y por eso `US-07` tiene que contemplarlo.
    """
    recien = {"id": 1, "status": "NEW", "route": None, "containers": []}

    assert esta_maduro(recien) is False
    lectura = interpretar(recien)
    assert lectura.hitos == []
    assert lectura.etapa == "SIN_TRACKING"


@pytest.mark.parametrize("vacio", [None, {}])
def test_un_payload_vacio_no_revienta(vacio: dict[str, Any] | None) -> None:
    assert esta_maduro(vacio) is False
    assert interpretar(vacio).id_embarque is None


# --- Robustez ante payloads incompletos ------------------------------------


def test_un_payload_sin_ruta_se_lee_a_medias_sin_fallar() -> None:
    """Un campo ausente es un embarque que todavía madura, no un error."""
    lectura = interpretar({"id": 7, "status": "SAILING", "containers": []})

    assert lectura.id_embarque == 7
    assert lectura.eta is None
    assert lectura.puerto_destino is None


def test_un_instante_ilegible_se_descarta_sin_tumbar_la_lectura() -> None:
    shipment = {
        "id": 7,
        "status": "SAILING",
        "containers": [{"movements": [{"event": "DEPA", "status": "ACT", "timestamp": "ayer"}]}],
    }

    lectura = interpretar(shipment)

    assert lectura.hitos[0].instante is None
    assert lectura.etapa == "EN_TRANSITO"  # el evento sigue contando


def test_el_geojson_ausente_no_impide_leer_el_resto() -> None:
    shipment, _ = CASOS[MAERSK_2_NAVES]
    lectura = interpretar(shipment, None)

    assert lectura.posicion is None
    assert lectura.eta is not None
    assert lectura.hay_transbordo is True


# --- La vía aérea comparte la forma, no el mapeo ---------------------------


def test_el_aereo_comparte_la_forma_del_payload() -> None:
    """Sus movimientos cuelgan de la raíz y no de `containers[]`.

    Tratarlo acá es lo que evita que `US-46` duplique el recorrido.
    """
    lectura = _lectura(LUFTHANSA_AEREO)

    assert len(lectura.hitos) == 10
    assert all(h.ocurrido for h in lectura.hitos)


def test_el_aereo_ya_mapea_sus_codigos() -> None:
    """`US-46` mapeó los códigos IATA CIMP.

    Esta prueba fijaba el estado anterior —`SIN_TRACKING`— como recordatorio, y
    falló en cuanto `US-46` hizo su trabajo. El detalle vive ahora en
    `test_shipsgo_aereo.py`; aquí solo queda constancia de que las dos vías
    conviven en el mismo intérprete.
    """
    lectura = _lectura(LUFTHANSA_AEREO)

    assert {h.evento for h in lectura.hitos} & {"RCS", "DEP", "RCF", "DLV"}
    assert lectura.etapa == "EN_DESTINO"


# --- Piezas sueltas --------------------------------------------------------


def test_la_nave_compara_por_valor() -> None:
    """De eso depende que no se dupliquen tramos de la misma nave."""
    assert Vehiculo("POLAR BRASIL", 9797216) == Vehiculo("POLAR BRASIL", 9797216)


def test_el_hito_es_inmutable() -> None:
    hito = Hito("DEPA", True, None, "BRSSZ", "SANTOS", None, None)
    with pytest.raises(AttributeError):
        hito.evento = "ARRV"  # type: ignore[misc]
