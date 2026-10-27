"""La posición estimada de un embarque aéreo — `US-26`.

ShipsGo no da la posición del avión; da los vuelos con su horario y su trazado.
Las pruebas usan un trayecto de dos tramos como el del MAWB de Lufthansa del
spike (PEK → FRA → SJO), con trazados rectos para poder afirmar el punto exacto.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from app.services.posicion_aerea import EN_TIERRA, EN_VUELO, FINALIZADO, estimar
from app.services.rastreo.shipsgo import leer_tramos_aereos

UTC = dt.UTC
SALIDA_1 = dt.datetime(2026, 9, 4, 0, 0, tzinfo=UTC)
LLEGADA_1 = dt.datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
SALIDA_2 = dt.datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
LLEGADA_2 = dt.datetime(2026, 9, 5, 22, 0, tzinfo=UTC)

TRAYECTO: list[dict[str, Any]] = [
    {
        "vuelo": "LH8431",
        "origen": "PEK",
        "destino": "FRA",
        "salida": SALIDA_1.isoformat(),
        "llegada": LLEGADA_1.isoformat(),
        "ruta": [[116.0, 40.0], [62.0, 45.0], [8.0, 50.0]],
    },
    {
        "vuelo": "LH518",
        "origen": "FRA",
        "destino": "SJO",
        "salida": SALIDA_2.isoformat(),
        "llegada": LLEGADA_2.isoformat(),
        "ruta": [[8.0, 50.0], [-84.0, 10.0]],
    },
]


def test_antes_de_salir_esta_en_tierra_en_el_origen() -> None:
    estimacion = estimar(TRAYECTO, SALIDA_1 - dt.timedelta(hours=3))

    assert estimacion is not None
    assert (estimacion.situacion, estimacion.lugar) == (EN_TIERRA, "PEK")
    assert (estimacion.longitud, estimacion.latitud) == (116.0, 40.0)
    assert estimacion.ruta is None


def test_en_vuelo_avanza_sobre_el_trazado_segun_el_tiempo() -> None:
    # A la mitad del segundo vuelo, a la mitad de su trazado recto.
    estimacion = estimar(TRAYECTO, SALIDA_2 + (LLEGADA_2 - SALIDA_2) / 2)

    assert estimacion is not None
    assert (estimacion.situacion, estimacion.vuelo) == (EN_VUELO, "LH518")
    assert estimacion.longitud == pytest.approx(-38.0)
    assert estimacion.latitud == pytest.approx(30.0)
    assert estimacion.ruta == [(8.0, 50.0), (-84.0, 10.0)]


def test_la_fraccion_se_reparte_por_el_largo_de_los_segmentos() -> None:
    # El primer trazado tiene dos segmentos casi iguales: a la mitad del tiempo,
    # cerca del punto del medio.
    estimacion = estimar(TRAYECTO, SALIDA_1 + (LLEGADA_1 - SALIDA_1) / 2)

    assert estimacion is not None
    assert estimacion.longitud == pytest.approx(62.0, abs=0.5)


def test_en_el_transbordo_espera_en_tierra_donde_aterrizo() -> None:
    estimacion = estimar(TRAYECTO, LLEGADA_1 + dt.timedelta(hours=5))

    assert estimacion is not None
    assert (estimacion.situacion, estimacion.lugar, estimacion.vuelo) == (
        EN_TIERRA,
        "FRA",
        "LH8431",
    )
    assert (estimacion.longitud, estimacion.latitud) == (8.0, 50.0)


def test_despues_del_ultimo_vuelo_concluyo_en_el_destino() -> None:
    estimacion = estimar(TRAYECTO, LLEGADA_2 + dt.timedelta(days=2))

    assert estimacion is not None
    assert (estimacion.situacion, estimacion.lugar) == (FINALIZADO, "SJO")
    assert (estimacion.longitud, estimacion.latitud) == (-84.0, 10.0)


@pytest.mark.parametrize(
    "trayecto",
    [None, [], [{"vuelo": "X", "ruta": [[1.0, 2.0]]}], [{"salida": "x", "llegada": "y"}]],
)
def test_sin_horario_o_sin_trazado_no_se_estima(trayecto) -> None:
    assert estimar(trayecto, SALIDA_1) is None


def test_lee_los_tramos_del_geojson_de_shipsgo() -> None:
    """La forma del `geojson` aéreo medida en el spike `TASK-28`."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [116.58, 40.08]}},
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[116.58, 40.08], [8.55, 50.04]]},
                "properties": {
                    "status": "PAST",
                    "flight": "LH8431",
                    "events": {
                        "DEP": {
                            "location": {"iata": "PEK"},
                            "timestamp": "2026-09-04T07:05:00+08:00",
                        },
                        "ARR": {
                            "location": {"iata": "FRA"},
                            "timestamp": "2026-09-04T13:07:00+02:00",
                        },
                    },
                    "current": None,
                },
            },
        ],
    }

    (tramo,) = leer_tramos_aereos(geojson)

    assert (tramo.vuelo, tramo.origen, tramo.destino) == ("LH8431", "PEK", "FRA")
    assert tramo.salida == dt.datetime(2026, 9, 3, 23, 5, tzinfo=UTC)
    assert tramo.ruta == ((116.58, 40.08), (8.55, 50.04))
    assert tramo.como_dict()["llegada"] == "2026-09-04T13:07:00+02:00"
    # Lo que guarda el colector se vuelve a leer igual.
    estimacion = estimar([tramo.como_dict()], dt.datetime(2026, 9, 10, tzinfo=UTC))
    assert estimacion is not None and estimacion.situacion == FINALIZADO
