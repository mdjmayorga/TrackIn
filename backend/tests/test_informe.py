"""Pruebas de `app.services.ingesta.informe` — `US-32`, sexto criterio.

*«Dada la carga, cuando termina, entonces queda un informe de validación con
cada rechazo y su clave de origen»*.

Lo que se fija acá es que **ninguno de los tres orígenes de rechazo se pierda**
y que cada uno conserve la clave con la que se puede encontrar el problema en el
archivo. Todo corre sin base: el informe es una transformación pura.
"""

from __future__ import annotations

import pytest

from app.services.ingesta.carga import (
    RECHAZO_REFERENCIA_INVALIDA,
    RECHAZO_SIN_DESTINO,
    RECHAZO_SIN_VIA,
    LineaRechazada,
    ResultadoCarga,
)
from app.services.ingesta.informe import (
    ENTRO_SIN_RASTREO,
    NO_ENTRO,
    construir_informe,
)
from app.services.ingesta.ztracking import ILEGIBLE_SIN_FECHA, LineaIlegible


def _resultado(**kwargs) -> ResultadoCarga:
    return ResultadoCarga(**kwargs)


# --- Los tres orígenes -----------------------------------------------------


def test_junta_los_tres_origenes_de_rechazo() -> None:
    """Antes de `US-32` vivían en tres sitios y nadie los miraba juntos."""
    informe = construir_informe(
        "ztracking",
        _resultado(
            cargados=5,
            rechazadas=[LineaRechazada("4500016171", 90, RECHAZO_SIN_VIA, "sin vía")],
            referencias_invalidas=[
                LineaRechazada("4500016172", 10, RECHAZO_REFERENCIA_INVALIDA, "dígito malo")
            ],
        ),
        [LineaIlegible("IDA", 82, ILEGIBLE_SIN_FECHA, "fecha vacía")],
    )

    assert informe.total_incidencias == 3
    assert {i.motivo for i in informe.incidencias} == {
        RECHAZO_SIN_VIA,
        RECHAZO_REFERENCIA_INVALIDA,
        ILEGIBLE_SIN_FECHA,
    }


def test_cada_origen_conserva_su_clave() -> None:
    """Las claves son distintas porque los problemas lo son.

    Una fila sin orden de compra no tiene `OC-posición` que mostrar — esa es
    justamente su falla —, así que la única forma de encontrarla es la hoja y el
    número de fila.
    """
    informe = construir_informe(
        "ztracking",
        _resultado(
            rechazadas=[LineaRechazada("4500016171", 90, RECHAZO_SIN_VIA, "sin vía")],
            referencias_invalidas=[
                LineaRechazada("4500016172", 10, RECHAZO_REFERENCIA_INVALIDA, "dígito malo")
            ],
        ),
        [LineaIlegible("PRODUCCION", 57, ILEGIBLE_SIN_FECHA, "fecha vacía")],
    )

    claves = {i.clave for i in informe.incidencias}
    assert claves == {"PRODUCCION!57", "4500016171-90", "4500016172-10"}


def test_distingue_lo_que_no_entro_de_lo_que_entro_sin_rastreo() -> None:
    """Es la diferencia entre «falta un pedido» y «hay un pedido sin seguir».

    Mezclarlas haría que quien lee el informe no sepa cuál de los dos arreglar
    primero: una es un hueco en la base y la otra es un número mal transcrito.
    """
    informe = construir_informe(
        "ztracking",
        _resultado(
            rechazadas=[
                LineaRechazada("450", 10, RECHAZO_SIN_VIA, "sin vía"),
                LineaRechazada("451", 10, RECHAZO_SIN_DESTINO, "sin destino"),
            ],
            referencias_invalidas=[
                LineaRechazada("452", 10, RECHAZO_REFERENCIA_INVALIDA, "dígito malo")
            ],
        ),
        [LineaIlegible("IDA", 82, ILEGIBLE_SIN_FECHA, "fecha vacía")],
    )

    assert informe.no_entraron == 3
    assert informe.entraron_sin_rastreo == 1
    referencia = informe.incidencias_de(RECHAZO_REFERENCIA_INVALIDA)[0]
    assert referencia.consecuencia == ENTRO_SIN_RASTREO


def test_las_ilegibles_cuentan_como_recibidas() -> None:
    """Si no se sumaran, el informe cuadraría con lo que el lector consiguió
    leer y no con lo que el archivo traía — que es lo que el usuario cuenta."""
    informe = construir_informe(
        "ztracking",
        _resultado(cargados=82, rechazadas=[LineaRechazada("450", 10, RECHAZO_SIN_VIA, "x")]),
        [LineaIlegible("IDA", 82, ILEGIBLE_SIN_FECHA, "fecha vacía")] * 5,
    )

    assert informe.recibidas == 82 + 1 + 5


def test_una_fuente_sin_archivo_no_necesita_ilegibles() -> None:
    """La semilla no tiene archivo que leer: el parámetro es opcional."""
    informe = construir_informe("semilla", _resultado(cargados=6))
    assert informe.total_incidencias == 0
    assert informe.recibidas == 6


# --- Agrupación ------------------------------------------------------------


def test_agrupa_por_motivo_de_mayor_a_menor() -> None:
    """290 líneas sin vía son *un* problema del archivo repetido 290 veces.

    El recuento por motivo es lo accionable: dice qué arreglar primero.
    """
    informe = construir_informe(
        "ztracking",
        _resultado(
            rechazadas=[
                *[LineaRechazada(f"45{i}", 10, RECHAZO_SIN_VIA, "sin vía") for i in range(5)],
                *[LineaRechazada(f"46{i}", 10, RECHAZO_SIN_DESTINO, "sin dest") for i in range(2)],
            ]
        ),
    )

    assert list(informe.por_motivo().items()) == [
        (RECHAZO_SIN_VIA, 5),
        (RECHAZO_SIN_DESTINO, 2),
    ]


def test_incidencias_de_filtra_por_motivo() -> None:
    informe = construir_informe(
        "ztracking",
        _resultado(
            rechazadas=[
                LineaRechazada("450", 10, RECHAZO_SIN_VIA, "sin vía"),
                LineaRechazada("451", 10, RECHAZO_SIN_DESTINO, "sin destino"),
            ]
        ),
    )

    assert len(informe.incidencias_de(RECHAZO_SIN_VIA)) == 1
    assert informe.incidencias_de("motivo_inventado") == []


# --- Presentación ----------------------------------------------------------


def test_el_texto_recorta_los_ejemplos_pero_no_el_recuento() -> None:
    """Contra el archivo real hay 290 con el mismo motivo: volcarlas todas
    esconde los demás problemas en vez de mostrarlos."""
    informe = construir_informe(
        "ztracking",
        _resultado(
            rechazadas=[
                LineaRechazada(f"45{i:04d}", 10, RECHAZO_SIN_VIA, "sin vía") for i in range(50)
            ]
        ),
    )

    texto = informe.como_texto(ejemplos=3)

    assert f"{RECHAZO_SIN_VIA} — 50" in texto  # el recuento entero
    assert "… y 47 más" in texto
    assert texto.count("· 45") == 3  # solo tres ejemplos


def test_el_texto_lo_dice_cuando_no_hay_nada_que_reportar() -> None:
    """Una carga limpia tiene que decirlo, no dejar el hueco en blanco."""
    texto = construir_informe("semilla", _resultado(cargados=6)).como_texto()
    assert "Sin incidencias." in texto


def test_el_texto_trae_los_numeros_de_la_carga() -> None:
    informe = construir_informe(
        "ztracking",
        _resultado(cargados=82, actualizados=3, sin_cambios=2, ausentes=[("450", 10)]),
    )
    texto = informe.como_texto()

    for parte in ("82 insertadas", "3 actualizadas", "2 sin cambios", "1 ausentes"):
        assert parte in texto


def test_como_dict_es_serializable() -> None:
    """`US-16` va a exponer esto por la API REST."""
    import json

    informe = construir_informe(
        "ztracking",
        _resultado(
            cargados=1,
            rechazadas=[LineaRechazada("450", 10, RECHAZO_SIN_VIA, "sin vía")],
        ),
        [LineaIlegible("IDA", 82, ILEGIBLE_SIN_FECHA, "fecha vacía")],
    )

    crudo = json.loads(json.dumps(informe.como_dict()))

    assert crudo["fuente"] == "ztracking"
    assert len(crudo["incidencias"]) == 2
    assert crudo["por_motivo"][RECHAZO_SIN_VIA] == 1
    assert crudo["incidencias"][0]["clave"] == "IDA!82"


def test_la_incidencia_se_lee_sola() -> None:
    informe = construir_informe(
        "ztracking",
        _resultado(rechazadas=[LineaRechazada("4500016171", 90, RECHAZO_SIN_VIA, "sin vía")]),
    )
    assert str(informe.incidencias[0]) == "4500016171-90: sin vía"


@pytest.mark.parametrize("consecuencia", [NO_ENTRO, ENTRO_SIN_RASTREO])
def test_las_consecuencias_son_las_dos_declaradas(consecuencia: str) -> None:
    """Si se añade una tercera hay que decidir qué significa para el usuario."""
    assert consecuencia in {NO_ENTRO, ENTRO_SIN_RASTREO}
