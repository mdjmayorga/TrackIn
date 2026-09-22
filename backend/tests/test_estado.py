"""Pruebas de `app.services.estado` — `US-10` / RF-11, RN-07 a RN-13.

Sin base de datos: el semáforo es aritmética de fechas y una tabla de
precedencia. Lo que se fija acá son las **tres decisiones del 26/08** que
cerraron los solapamientos del articulado, porque son justo las que se pierden
si alguien reescribe el módulo sin leer el modelo.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.models.enums import ESTADOS_CALCULADOS, ESTADOS_CUMPLIMIENTO
from app.services.estado import (
    A_TIEMPO,
    CANCELADO,
    CERRADO,
    EN_RIESGO,
    RETRASADO,
    SIN_TRACKING,
    clasificar_cumplimiento,
    derivar_estado_calculado,
)

COMPROMETIDA = dt.date(2026, 10, 10)
UMBRAL = 2  # el valor por defecto de `umbral_riesgo_dias`


def _cumplimiento(margen_dias: int, umbral: int = UMBRAL) -> str | None:
    """Clasifica una proyectada que cae `margen_dias` antes de la comprometida."""
    proyectada = COMPROMETIDA - dt.timedelta(days=margen_dias)
    return clasificar_cumplimiento(proyectada, COMPROMETIDA, umbral)


# --- La frontera del umbral: RN-08 gana a RN-07 ----------------------------


@pytest.mark.parametrize(
    ("margen", "esperado"),
    [
        (10, A_TIEMPO),
        (4, A_TIEMPO),
        (3, A_TIEMPO),  # margen > umbral
        (2, EN_RIESGO),  # margen == umbral: la frontera
        (1, EN_RIESGO),
        (0, EN_RIESGO),  # llega justo el día comprometido
        (-1, RETRASADO),
        (-30, RETRASADO),
    ],
)
def test_la_frontera_del_umbral(margen: int, esperado: str) -> None:
    """Decisión del 26/08: **RN-08 prevalece sobre RN-07**.

    RN-07 dice «anterior o igual» sin calificar y colisiona con RN-08 en la
    ventana previa. Gana la más específica: `A_TIEMPO` exige margen
    **estrictamente mayor** que el umbral, y llegar justo el día comprometido es
    `EN_RIESGO`, no `A_TIEMPO`.
    """
    assert _cumplimiento(margen) == esperado


def test_margen_cero_es_riesgo_y_no_a_tiempo() -> None:
    """El caso que RN-07 leída sola resolvería al revés.

    Se prueba aparte porque es la decisión, no un caso más de la tabla.
    """
    assert _cumplimiento(0) == EN_RIESGO


def test_el_umbral_es_configurable_sin_tocar_codigo() -> None:
    """Quinto criterio de `US-10`: sale de `parametros_sistema`.

    Con umbral 0 solo llegar tarde es riesgo; con 5 la ventana se ensancha.
    """
    assert _cumplimiento(1, umbral=0) == A_TIEMPO
    assert _cumplimiento(1, umbral=5) == EN_RIESGO
    assert _cumplimiento(6, umbral=5) == A_TIEMPO


def test_el_umbral_son_dias_no_horas() -> None:
    """Decisión del 26/08: RN-11 lo escribe en horas, pero ambas fechas son
    `DATE`. Comparar 48 h contra fechas sin hora es fingir una precisión que el
    dato no tiene. 48 h = 2 días."""
    assert _cumplimiento(2, umbral=2) == EN_RIESGO
    assert _cumplimiento(3, umbral=2) == A_TIEMPO


# --- Cuándo no se puede afirmar nada ---------------------------------------


@pytest.mark.parametrize(
    ("proyectada", "comprometida"),
    [
        (None, COMPROMETIDA),
        (COMPROMETIDA, None),
        (None, None),
    ],
)
def test_sin_alguna_de_las_dos_fechas_el_cumplimiento_es_nulo(
    proyectada: dt.date | None, comprometida: dt.date | None
) -> None:
    """`NULL` dice «no se puede afirmar si llega a tiempo», y ningún valor del
    dominio lo dice (§1.4 del modelo). `US-24` lo pinta en gris."""
    assert clasificar_cumplimiento(proyectada, comprometida, UMBRAL) is None


def test_el_dominio_de_cumplimiento_es_el_del_modelo() -> None:
    """Si alguien añade un estado, el `CHECK` de la tabla lo rechazaría."""
    assert {A_TIEMPO, EN_RIESGO, RETRASADO} == set(ESTADOS_CUMPLIMIENTO)


# --- Derivación del estado único (RF-11) -----------------------------------


def test_el_cierre_gana_a_todo() -> None:
    """RN-13. Un pedido cerrado ya no está en riesgo de nada."""
    assert derivar_estado_calculado("EN_TRANSITO", RETRASADO, "RECEPCION_CONFORME") == CERRADO
    assert derivar_estado_calculado("EN_DESTINO", EN_RIESGO, "CIERRE_FORZADO") == CERRADO
    assert derivar_estado_calculado("EN_TRANSITO", A_TIEMPO, "CANCELACION") == CANCELADO


def test_un_motivo_desconocido_se_trata_como_cierre() -> None:
    """El `CHECK` de la tabla exige que motivo y estado terminal vayan juntos.

    Ante un motivo que no está en el catálogo se cierra, no se inventa un
    estado: devolver la etapa violaría la restricción y tumbaría el `INSERT`.
    """
    assert derivar_estado_calculado("EN_TRANSITO", A_TIEMPO, "MOTIVO_NUEVO") == CERRADO


def test_sin_tracking_manda_sobre_el_cumplimiento() -> None:
    """RN-02: sin nave asociada no hay dato con que evaluar nada.

    Es el estado del 100 % de las líneas que hoy entran desde el archivo.
    """
    assert derivar_estado_calculado(SIN_TRACKING, None) == SIN_TRACKING
    assert derivar_estado_calculado(SIN_TRACKING, RETRASADO) == SIN_TRACKING


@pytest.mark.parametrize("etapa", ["EN_ORIGEN", "EN_TRANSITO", "EN_DESTINO", "EN_PROCESO_ADUANAL"])
@pytest.mark.parametrize("riesgo", [RETRASADO, EN_RIESGO])
def test_el_riesgo_manda_sobre_la_etapa(etapa: str, riesgo: str) -> None:
    """Es la información por la que existe el sistema.

    Quien abre el dashboard quiere ver primero lo que exige atención, no dónde
    está cada caja.
    """
    assert derivar_estado_calculado(etapa, riesgo) == riesgo


@pytest.mark.parametrize("etapa", ["EN_ORIGEN", "EN_TRANSITO", "EN_DESTINO", "EN_PROCESO_ADUANAL"])
def test_a_tiempo_deja_ver_la_etapa(etapa: str) -> None:
    """Cuando no hay nada que vigilar, lo útil es dónde está la carga.

    Es la otra mitad de §1.4: Logística pregunta dónde está, Compras pregunta si
    llega a tiempo, y el estado único tiene que servir a las dos.
    """
    assert derivar_estado_calculado(etapa, A_TIEMPO) == etapa


@pytest.mark.parametrize("etapa", ["EN_ORIGEN", "EN_TRANSITO", "EN_DESTINO"])
def test_sin_cumplimiento_tambien_se_ve_la_etapa(etapa: str) -> None:
    """`NULL` no es riesgo: es «no se sabe». La etapa sigue siendo verdad."""
    assert derivar_estado_calculado(etapa, None) == etapa


def test_todo_lo_que_se_deriva_cabe_en_el_dominio_de_la_columna() -> None:
    """Invariante: `estado_calculado` tiene un `CHECK` contra este conjunto.

    Un valor fuera de él no fallaría acá sino al persistir, y el mensaje de
    PostgreSQL no diría qué regla lo produjo.
    """
    etapas = ["SIN_TRACKING", "EN_ORIGEN", "EN_TRANSITO", "EN_DESTINO", "EN_PROCESO_ADUANAL"]
    cumplimientos: list[str | None] = [A_TIEMPO, EN_RIESGO, RETRASADO, None]
    motivos: list[str | None] = [None, "RECEPCION_CONFORME", "CIERRE_FORZADO", "CANCELACION"]

    for etapa in etapas:
        for cumplimiento in cumplimientos:
            for motivo in motivos:
                derivado = derivar_estado_calculado(etapa, cumplimiento, motivo)
                assert derivado in ESTADOS_CALCULADOS, (etapa, cumplimiento, motivo, derivado)


# --- La transición por tiempo que se anuló ---------------------------------


def test_el_modulo_no_mira_el_reloj() -> None:
    """La regla de los 30 minutos quedó **anulada el 04/09**.

    Planeación confirmó que el paso a proceso aduanal es manual **por proceso**,
    no por falta de datos: lo dispara la confirmación de `US-14`. Si alguien
    reintroduce una transición por tiempo, esta prueba lo delata.
    """
    import inspect

    from app.services import estado

    fuente = inspect.getsource(estado)
    for sospechoso in ("datetime.now", "utcnow", "timedelta(minutes", "duracion_en_destino"):
        assert sospechoso not in fuente, f"{sospechoso}: ¿volvió la transición por tiempo?"
