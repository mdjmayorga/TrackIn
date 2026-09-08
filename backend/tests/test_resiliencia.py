"""Pruebas de `app.services.resiliencia` — RF-09 / RNF-12 (`US-03`).

Ninguna toca la red ni la base: el módulo es política pura, y esa es la razón de
haberlo separado del transporte. Las mismas pruebas valen para AISStream por
WebSocket y para Vizion o Portcast por REST.
"""

from __future__ import annotations

import datetime as dt
import random

import pytest

from app.services.resiliencia import (
    MOTIVOS_PERMANENTES,
    ClaseFallo,
    EstadoFuente,
    PoliticaReintento,
    clasificar,
)

T0 = dt.datetime(2026, 9, 8, 12, 0, 0, tzinfo=dt.UTC)


def _en(segundos: int) -> dt.datetime:
    return T0 + dt.timedelta(seconds=segundos)


def _fuente(**kwargs) -> EstadoFuente:
    kwargs.setdefault("nombre", "prueba")
    return EstadoFuente(**kwargs)


# --- Clasificación ---------------------------------------------------------


@pytest.mark.parametrize("motivo", sorted(MOTIVOS_PERMANENTES))
def test_los_motivos_del_catalogo_son_permanentes(motivo: str) -> None:
    assert clasificar(motivo) is ClaseFallo.PERMANENTE


@pytest.mark.parametrize("motivo", ["  CREDENCIAL_INVALIDA  ", "Cuota_Agotada"])
def test_la_clasificacion_normaliza_el_motivo(motivo: str) -> None:
    assert clasificar(motivo) is ClaseFallo.PERMANENTE


@pytest.mark.parametrize(
    "motivo",
    ["tiempo_agotado", "error_servidor", "conexion_rechazada", "algo_nunca_visto"],
)
def test_lo_no_catalogado_es_transitorio(motivo: str) -> None:
    """Equivocarse hacia el reintento cuesta cuota; hacia lo permanente cuesta
    datos y apaga una fuente que servía. Se elige el error barato."""
    assert clasificar(motivo) is ClaseFallo.TRANSITORIO


# --- Espera creciente ------------------------------------------------------


def test_la_espera_crece_de_forma_geometrica() -> None:
    politica = PoliticaReintento(espera_inicial_s=5, factor=2, ruido=0)
    assert [politica.espera(n) for n in (1, 2, 3, 4)] == [5, 10, 20, 40]


def test_la_espera_tiene_tope() -> None:
    """Sin tope, una caída larga deja el reintento a horas de distancia."""
    politica = PoliticaReintento(espera_inicial_s=5, factor=2, espera_maxima_s=60, ruido=0)
    assert politica.espera(10) == 60


def test_el_ruido_dispersa_los_reintentos() -> None:
    """Sin ruido, todos los elementos reintentan en el mismo instante y la
    recuperación de la fuente coincide con una avalancha nuestra."""
    politica = PoliticaReintento(espera_inicial_s=100, factor=1, ruido=0.2)
    rng = random.Random(1234)
    esperas = {politica.espera(1, aleatorio=rng) for _ in range(20)}
    assert len(esperas) > 1
    assert all(80 <= e <= 120 for e in esperas)


def test_el_primer_intento_es_el_uno() -> None:
    with pytest.raises(ValueError, match="empieza en 1"):
        PoliticaReintento().espera(0)


def test_la_politica_sabe_cuando_se_agoto() -> None:
    politica = PoliticaReintento(intentos_maximos=3)
    assert not politica.agotada(2)
    assert politica.agotada(3)


# --- Principio 1: el silencio no es una caída -----------------------------


def test_una_respuesta_sin_datos_es_un_exito() -> None:
    """El error que hizo parecer roto al spike TG-10: en el Caribe no había
    tráfico que reportar, y eso no es que la fuente esté caída."""
    fuente = _fuente()
    fuente.registrar_fallo(instante=_en(0), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado")
    assert fuente.fallos_consecutivos == 1

    fuente.registrar_exito(instante=_en(60), con_datos=False)

    assert fuente.fallos_consecutivos == 0
    assert fuente.clase_ultimo_fallo is ClaseFallo.NINGUNO
    assert not fuente.degradada
    assert fuente.ultimo_contacto_ok == _en(60)


def test_el_exito_borra_el_motivo_del_fallo_anterior() -> None:
    fuente = _fuente()
    fuente.registrar_fallo(instante=_en(0), clase=ClaseFallo.TRANSITORIO, motivo="error_servidor")
    fuente.registrar_exito(instante=_en(10))
    assert fuente.motivo_ultimo_fallo is None


# --- Principio 2: un fallo permanente no se reintenta ---------------------


def test_un_fallo_permanente_degrada_de_inmediato() -> None:
    fuente = _fuente()
    fuente.registrar_fallo(
        instante=_en(0), clase=ClaseFallo.PERMANENTE, motivo="credencial_invalida"
    )
    assert fuente.degradada
    assert not fuente.debe_reintentar
    assert fuente.espera_hasta_el_proximo_intento() is None


def test_un_permanente_no_se_reintenta_aunque_queden_intentos() -> None:
    """Insistir con una credencial inválida solo gasta cuota y llena el log."""
    fuente = _fuente(politica=PoliticaReintento(intentos_maximos=10))
    fuente.registrar_fallo(instante=_en(0), clase=ClaseFallo.PERMANENTE, motivo="cuota_agotada")
    assert fuente.fallos_consecutivos == 1  # quedan nueve
    assert not fuente.debe_reintentar  # y aun así no se reintenta


def test_un_permanente_se_recupera_si_la_fuente_vuelve() -> None:
    """Cambiar la credencial arregla el caso: no queda apagada para siempre."""
    fuente = _fuente()
    fuente.registrar_fallo(
        instante=_en(0), clase=ClaseFallo.PERMANENTE, motivo="credencial_invalida"
    )
    fuente.registrar_exito(instante=_en(3600))
    assert not fuente.degradada
    assert fuente.debe_reintentar


# --- Principio 3: transitorio con espera creciente y tope -----------------


def test_los_fallos_transitorios_se_acumulan() -> None:
    fuente = _fuente(politica=PoliticaReintento(intentos_maximos=3))
    for n in range(2):
        fuente.registrar_fallo(
            instante=_en(n), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado"
        )
    assert fuente.fallos_consecutivos == 2
    assert not fuente.degradada
    assert fuente.debe_reintentar


def test_agotados_los_intentos_la_fuente_queda_degradada() -> None:
    fuente = _fuente(politica=PoliticaReintento(intentos_maximos=3))
    for n in range(3):
        fuente.registrar_fallo(
            instante=_en(n), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado"
        )
    assert fuente.degradada
    assert not fuente.debe_reintentar


def test_la_espera_crece_con_cada_fallo() -> None:
    fuente = _fuente(
        politica=PoliticaReintento(espera_inicial_s=5, factor=2, ruido=0, intentos_maximos=9)
    )
    esperas = []
    for n in range(3):
        fuente.registrar_fallo(
            instante=_en(n), clase=ClaseFallo.TRANSITORIO, motivo="error_servidor"
        )
        esperas.append(fuente.espera_hasta_el_proximo_intento())
    assert esperas == [5, 10, 20]


def test_sin_fallos_no_hay_que_esperar() -> None:
    assert _fuente().espera_hasta_el_proximo_intento() == 0.0


def test_nunca_hay_bucle_cerrado() -> None:
    """La espera nunca es cero mientras haya un fallo pendiente."""
    fuente = _fuente(politica=PoliticaReintento(intentos_maximos=9))
    fuente.registrar_fallo(
        instante=_en(0), clase=ClaseFallo.TRANSITORIO, motivo="conexion_rechazada"
    )
    espera = fuente.espera_hasta_el_proximo_intento()
    assert espera is not None and espera > 0


# --- Principios 4 y 5: antigüedad y exposición ----------------------------


def test_la_antiguedad_se_mide_desde_el_ultimo_exito() -> None:
    """RNF-12: no basta con enseñar la última posición, hay que decir de cuándo es."""
    fuente = _fuente()
    fuente.registrar_exito(instante=_en(0))
    assert fuente.antiguedad_s(ahora=_en(600)) == 600


def test_un_fallo_no_cambia_la_antiguedad_del_ultimo_dato_bueno() -> None:
    """El dato viejo sigue siendo del mismo momento aunque la fuente se caiga."""
    fuente = _fuente()
    fuente.registrar_exito(instante=_en(0))
    fuente.registrar_fallo(instante=_en(300), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado")
    assert fuente.ultimo_contacto_ok == _en(0)
    assert fuente.antiguedad_s(ahora=_en(600)) == 600


def test_sin_contacto_previo_la_antiguedad_es_desconocida() -> None:
    """`None` es «nunca hubo dato», que no es lo mismo que «dato viejo»."""
    assert _fuente().antiguedad_s(ahora=T0) is None


def test_el_resumen_expone_lo_que_el_dashboard_necesita() -> None:
    fuente = _fuente(nombre="vizion")
    fuente.registrar_exito(instante=_en(0))
    fuente.registrar_fallo(instante=_en(60), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado")
    resumen = fuente.resumen(ahora=_en(300))

    assert resumen["fuente"] == "vizion"
    assert resumen["degradada"] is False
    assert resumen["fallos_consecutivos"] == 1
    assert resumen["clase_ultimo_fallo"] == "transitorio"
    assert resumen["motivo_ultimo_fallo"] == "tiempo_agotado"
    assert resumen["antiguedad_s"] == 300


def test_el_resumen_es_serializable_a_json() -> None:
    """Va al healthcheck y al encabezado del dashboard: tiene que viajar."""
    import json

    fuente = _fuente()
    fuente.registrar_exito(instante=_en(0))
    json.dumps(fuente.resumen(ahora=_en(10)))


# --- Invariantes -----------------------------------------------------------


def test_no_se_puede_registrar_un_fallo_de_clase_ninguno() -> None:
    with pytest.raises(ValueError, match="NINGUNO"):
        _fuente().registrar_fallo(instante=T0, clase=ClaseFallo.NINGUNO, motivo="lo que sea")


def test_una_fuente_nueva_esta_sana_y_lista() -> None:
    fuente = _fuente()
    assert not fuente.degradada
    assert fuente.debe_reintentar
    assert fuente.fallos_consecutivos == 0
    assert fuente.clase_ultimo_fallo is ClaseFallo.NINGUNO


def test_cada_fuente_lleva_su_propio_estado() -> None:
    """Que Vizion esté caída no puede degradar a Portcast."""
    una, otra = _fuente(nombre="vizion"), _fuente(nombre="portcast")
    una.registrar_fallo(instante=T0, clase=ClaseFallo.PERMANENTE, motivo="credencial_invalida")
    assert una.degradada
    assert not otra.degradada


def test_la_politica_por_defecto_no_es_compartida() -> None:
    """`field(default_factory=...)`: dos fuentes no comparten el mismo objeto."""
    assert _fuente().politica is not _fuente().politica
