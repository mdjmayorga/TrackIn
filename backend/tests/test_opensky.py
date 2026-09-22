"""Pruebas de `app.services.rastreo.opensky` — `US-05` / RF-07.

Sin base y sin red. Los casos borde **no son hipotéticos**: los capturó TG-11
con tráfico real sobre Costa Rica el 18/08/2026, y son justo los que un parser
escrito de memoria trata mal.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from app.services.rastreo.opensky import (
    INDICE,
    parsear_estado,
    parsear_estados,
    por_callsign,
    por_icao24,
)

#: Hora del servidor de la muestra real.
HORA_SERVIDOR = 1787066777


def _vector(**campos: Any) -> list[Any]:
    """Un vector de estado con la forma real: 17 posiciones, no un objeto."""
    base: dict[str, Any] = {
        "icao24": "0ac9e1",
        "callsign": "AVA072  ",  # OpenSky rellena con espacios a la derecha
        "pais_origen": "Colombia",
        "instante_posicion": HORA_SERVIDOR - 1,
        "ultimo_contacto": HORA_SERVIDOR - 1,
        "longitud": -85.333,
        "latitud": 10.9489,
        "altitud_baro": 10972.8,
        "en_tierra": False,
        "velocidad": 240.82,
        "rumbo": 318.5,
        "razon_ascenso": -0.33,
        "sensores": None,
        "altitud_geo": 11000.0,
        "squawk": None,
        "spi": False,
        "origen_posicion": 0,
    }
    base.update(campos)
    vector: list[Any] = [None] * 17
    for nombre, valor in base.items():
        vector[INDICE[nombre]] = valor
    return vector


# --- El vector posicional --------------------------------------------------


def test_el_indice_tiene_las_diecisiete_posiciones() -> None:
    """La API entrega arreglos, no objetos: un índice mal puesto cambia la
    latitud por la longitud sin que nada falle."""
    assert len(INDICE) == 17
    assert INDICE["longitud"] == 5
    assert INDICE["latitud"] == 6


def test_extrae_los_campos_que_pide_el_criterio() -> None:
    """*«Extraigo latitud, longitud, altitud, velocidad y rumbo»*."""
    posicion = parsear_estado(_vector(), HORA_SERVIDOR)

    assert posicion is not None
    assert posicion.icao24 == "0ac9e1"
    assert posicion.latitud == 10.9489
    assert posicion.longitud == -85.333
    assert posicion.altitud_m == 10972.8
    assert posicion.rumbo_grados == 318.5
    assert posicion.velocidad_nudos is not None


def test_la_velocidad_se_convierte_a_nudos() -> None:
    """OpenSky entrega m/s; `historial_tracking` guarda nudos, como AIS.

    Que las dos fuentes usen la misma unidad es lo que permite compararlas en
    la misma columna.
    """
    posicion = parsear_estado(_vector(velocidad=100.0), HORA_SERVIDOR)

    assert posicion is not None
    assert posicion.velocidad_nudos == pytest.approx(194.38, abs=0.01)


def test_el_callsign_conserva_su_texto_sin_relleno() -> None:
    posicion = parsear_estado(_vector(), HORA_SERVIDOR)
    assert posicion is not None
    assert posicion.callsign == "AVA072"


def test_el_icao24_se_normaliza_a_minusculas() -> None:
    """Es la clave de comparación entre lecturas; la caja no puede variarla."""
    posicion = parsear_estado(_vector(icao24="0AC9E1"), HORA_SERVIDOR)
    assert posicion is not None
    assert posicion.icao24 == "0ac9e1"


def test_el_instante_llega_con_zona() -> None:
    posicion = parsear_estado(_vector(), HORA_SERVIDOR)
    assert posicion is not None
    assert posicion.instante.tzinfo is not None


# --- Los casos borde medidos -----------------------------------------------


def test_la_altitud_nula_en_tierra_no_invalida_la_lectura() -> None:
    """Con `on_ground: true`, `baro_altitude` vino `null` en el **100 %** de
    los casos. Es correcto por diseño y el modelo tiene que admitirlo."""
    posicion = parsear_estado(
        _vector(en_tierra=True, altitud_baro=None, altitud_geo=None), HORA_SERVIDOR
    )

    assert posicion is not None
    assert posicion.altitud_m is None
    assert posicion.en_tierra is True


def test_la_altitud_geometrica_sirve_de_respaldo() -> None:
    posicion = parsear_estado(_vector(altitud_baro=None, altitud_geo=9000.0), HORA_SERVIDOR)
    assert posicion is not None
    assert posicion.altitud_m == 9000.0


def test_un_callsign_nulo_no_descarta_la_lectura() -> None:
    """`0ae105` reportó `null` y `TIAGO` **tres minutos después**.

    El `icao24` es el identificador estable; el callsign no es confiable de
    inmediato. Descartar la lectura perdería la posición por un nombre.
    """
    posicion = parsear_estado(_vector(callsign=None), HORA_SERVIDOR)

    assert posicion is not None
    assert posicion.callsign is None
    assert posicion.icao24 == "0ac9e1"


def test_un_squawk_nulo_no_molesta() -> None:
    """Vino nulo en las 14 aeronaves de la muestra: descartado como vía de
    identificación, pero no puede romper el parseo."""
    assert parsear_estado(_vector(squawk=None), HORA_SERVIDOR) is not None


def test_la_antiguedad_se_calcula_contra_la_hora_del_servidor() -> None:
    """Lo honesto es decir «última posición hace N minutos».

    La API deja de listar una aeronave sin decir por qué: salió del área,
    aterrizó o se perdió la señal llegan iguales.
    """
    posicion = parsear_estado(_vector(ultimo_contacto=HORA_SERVIDOR - 207), HORA_SERVIDOR)

    assert posicion is not None
    assert posicion.antiguedad_s == 207


def test_sin_hora_del_servidor_no_se_inventa_la_antiguedad() -> None:
    posicion = parsear_estado(_vector(), None)
    assert posicion is not None
    assert posicion.antiguedad_s is None


# --- Lo que sí descarta una lectura ----------------------------------------


@pytest.mark.parametrize("campo", ["icao24", "latitud", "longitud"])
def test_sin_lo_imprescindible_la_lectura_se_descarta(campo: str) -> None:
    """Sin `icao24` no hay a qué atribuirla; sin coordenadas no hay posición."""
    assert parsear_estado(_vector(**{campo: None}), HORA_SERVIDOR) is None


def test_un_vector_corto_no_revienta() -> None:
    assert parsear_estado(["0ac9e1"], HORA_SERVIDOR) is None


def test_algo_que_no_es_un_vector_no_revienta() -> None:
    assert parsear_estado({"icao24": "0ac9e1"}, HORA_SERVIDOR) is None  # type: ignore[arg-type]


# --- La trampa del `states: null` ------------------------------------------


def test_states_null_se_normaliza_a_lista_vacia() -> None:
    """**La trampa que cuesta un `TypeError`.**

    Cuando no hay aeronaves la API devuelve `states: null`, no `[]`. Y no es
    excepcional: pasa con un `icao24` inexistente y con un *bounding box* sin
    tráfico, que es lo normal de madrugada.
    """
    assert parsear_estados({"time": HORA_SERVIDOR, "states": None}) == []


def test_una_respuesta_sin_la_clave_tampoco_revienta() -> None:
    assert parsear_estados({"time": HORA_SERVIDOR}) == []


@pytest.mark.parametrize("cuerpo", [None, [], "texto"])
def test_un_cuerpo_que_no_es_un_objeto_da_lista_vacia(cuerpo: Any) -> None:
    assert parsear_estados(cuerpo) == []


def test_states_que_no_es_lista_se_descarta_con_aviso(caplog) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        assert parsear_estados({"states": {"a": 1}}) == []

    assert "no es una lista" in caplog.text


def test_parsea_varias_aeronaves_y_salta_las_inservibles() -> None:
    cuerpo = {
        "time": HORA_SERVIDOR,
        "states": [
            _vector(icao24="0ac9e1"),
            _vector(icao24=None),  # sin identificador: se salta
            _vector(icao24="a12750", callsign="CMP884"),
        ],
    }

    posiciones = parsear_estados(cuerpo)

    assert [p.icao24 for p in posiciones] == ["0ac9e1", "a12750"]


# --- Búsqueda --------------------------------------------------------------


def test_busca_por_callsign_ignorando_relleno_y_caja() -> None:
    """OpenSky rellena con espacios: comparar sin normalizar no encuentra nada."""
    posiciones = parsear_estados({"time": HORA_SERVIDOR, "states": [_vector()]})

    assert por_callsign(posiciones, "ava072") is not None
    assert por_callsign(posiciones, "  AVA072 ") is not None
    assert por_callsign(posiciones, "AVA999") is None


def test_una_aeronave_sin_callsign_no_estorba_la_busqueda() -> None:
    posiciones = parsear_estados(
        {"time": HORA_SERVIDOR, "states": [_vector(icao24="aaaaaa", callsign=None), _vector()]}
    )

    encontrada = por_callsign(posiciones, "AVA072")

    assert encontrada is not None
    assert encontrada.icao24 == "0ac9e1"


def test_busca_por_icao24() -> None:
    posiciones = parsear_estados({"time": HORA_SERVIDOR, "states": [_vector()]})

    assert por_icao24(posiciones, "0AC9E1") is not None
    assert por_icao24(posiciones, "ffffff") is None


# --- Aterrizaje contra pérdida de señal ------------------------------------


def test_en_tierra_es_la_unica_senal_de_aterrizaje() -> None:
    """TG-11 midió el caso contrario: `LRS1018` bajando a -4,88 m/s con 207 s
    de antigüedad. Se pierde la línea de vista justo cuando se quiere confirmar
    el aterrizaje, y afirmarlo con esa lectura sería inventar."""
    descendiendo = parsear_estado(
        _vector(razon_ascenso=-4.88, altitud_baro=2256.0, ultimo_contacto=HORA_SERVIDOR - 207),
        HORA_SERVIDOR,
    )
    aterrizado = parsear_estado(_vector(en_tierra=True, altitud_baro=None), HORA_SERVIDOR)

    assert descendiendo is not None and aterrizado is not None
    assert descendiendo.aterrizando is False
    assert aterrizado.aterrizando is True


def test_el_instante_se_apoya_en_el_ultimo_contacto_si_falta_el_de_posicion() -> None:
    posicion = parsear_estado(
        _vector(instante_posicion=None, ultimo_contacto=HORA_SERVIDOR), HORA_SERVIDOR
    )

    assert posicion is not None
    assert posicion.instante == dt.datetime.fromtimestamp(HORA_SERVIDOR, tz=dt.UTC)
