"""Pruebas de `app.services.ingesta.plantilla` — `US-59`, la plantilla vacía.

La propiedad que importa es la tercera del criterio: **la plantilla llenada,
sin tocarle la estructura, se carga sin errores de encabezado**. Por eso la
prueba central la llena y la pasa por el mismo lector de la carga real.
"""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.services.ingesta.plantilla import generar_plantilla
from app.services.ingesta.ztracking import (
    COLUMNAS,
    HOJAS_EN_ALCANCE,
    PLANTILLA,
    ROTULOS_PLANTILLA,
    FuenteZTracking,
)

#: Una línea con solo las columnas obligatorias, por campo.
_OBLIGATORIAS = {
    "oc_numero": "4500016172",
    "posicion_oc": 10,
    "proveedor_codigo": "1007052",
    "material_codigo": "11000371",
    "cantidad": 6000,
    "unidad_medida": "KG",
    "fecha_entrega_pedido": dt.datetime(2026, 11, 30),
    "via_transporte": "MARITIMO",
}


def _abrir():
    return load_workbook(io.BytesIO(generar_plantilla()))


def _llenar(tmp_path: Path, valores: dict[str, object]) -> Path:
    libro = _abrir()
    for nombre in HOJAS_EN_ALCANCE:
        for indice, (campo, _) in enumerate(PLANTILLA, start=1):
            if campo in valores:
                libro[nombre].cell(row=2, column=indice, value=valores[campo])
    ruta = tmp_path / "llenada.xlsx"
    libro.save(ruta)
    return ruta


def test_las_hojas_de_datos_traen_solo_el_encabezado() -> None:
    libro = _abrir()

    assert libro.sheetnames == [*HOJAS_EN_ALCANCE, "INSTRUCCIONES"]
    for nombre in HOJAS_EN_ALCANCE:
        filas = list(libro[nombre].iter_rows(values_only=True))
        assert list(filas[0]) == list(ROTULOS_PLANTILLA)
        # Las celdas con formato de fecha no son datos: ninguna trae un valor.
        assert all(celda is None for fila in filas[1:] for celda in fila)


def test_las_obligatorias_van_sin_sufijo_y_las_demas_dicen_opcional() -> None:
    """Las obligatorias son exactamente las que el lector exige."""
    requeridas = {c.campo for c in COLUMNAS if c.requerido}
    sin_sufijo = {campo for campo, rotulo in PLANTILLA if "(" not in rotulo or "AEREO" in rotulo}

    assert sin_sufijo == requeridas
    assert all(
        rotulo.endswith(" (opcional)") or campo in requeridas or campo == "incoterm"
        for campo, rotulo in PLANTILLA
    )


def test_solo_trae_lo_que_el_sistema_usa() -> None:
    """Decisión del 02/11/2026: fuera lo que TrackIn no lee o no usa."""
    for fuera in ("Temperatura", "Fabricante", "Centro", "Usuario", "Carga arribo"):
        assert not any(r.startswith(fuera) for r in ROTULOS_PLANTILLA)


def test_la_via_y_el_tipo_de_documento_tienen_lista_desplegable() -> None:
    hoja = _abrir()["PRODUCCION"]

    listas = {v.formula1 for v in hoja.data_validations.dataValidation}

    assert listas == {'"AEREO,MARITIMO"', '"BL,AWB,CONTENEDOR,BOOKING"'}


def test_las_instrucciones_explican_cada_columna() -> None:
    hoja = _abrir()["INSTRUCCIONES"]
    filas = {fila[0]: fila for fila in hoja.iter_rows(min_row=5, values_only=True)}

    assert set(filas) == set(ROTULOS_PLANTILLA)
    assert filas["Documento Compra"][1] == "Sí"
    assert filas["Comentarios (opcional)"][1] == "No"
    # 02/11/2026: columna obligatoria, celda que puede ir en blanco.
    assert filas["Solicitud de pedido"][1] == "Sí, puede ir vacía"
    # 04/11/2026: sin referencia la línea no entra; la celda ya no puede ir vacía.
    for rotulo in ("# DE DOCUMENTO", "TIPO DE DOCUMENTO AWB / BL"):
        assert filas[rotulo][1] == "Sí"
    assert filas["Incoterm (obligatorio si es marítimo)"][1] == "Si es marítimo"


async def test_llenada_completa_se_lee_sin_errores_ni_avisos(tmp_path: Path) -> None:
    ruta = _llenar(
        tmp_path,
        {
            **_OBLIGATORIAS,
            "proveedor_nombre": "ROUSSELOT GELATINAS",
            "material_descripcion": "Colágeno hidrolizado bovino",
            "incoterm": "CIF LIMON",
            "pais_origen": "BRASIL",
            "eta_declarada": "PENDIENTE",
            "solicitud_pedido": "1000012345",
            "tipo_referencia": "BL",
            "numero_referencia": "MAEU274029064",
            "comentario": "zarpó el 20/10",
        },
    )

    fuente = FuenteZTracking(ruta)
    pedidos = await fuente.obtener_pedidos()

    assert len(pedidos) == 2  # una por hoja
    assert fuente.ilegibles == []
    assert fuente.diferencias == {}
    pedido = pedidos[0]
    assert (pedido.tipo_referencia, pedido.numero_referencia) == ("BL", "MAEU274029064")
    # Los rótulos con «(opcional)» se leen como su columna.
    assert pedido.solicitud_pedido == "1000012345"
    assert pedido.proveedor_nombre == "ROUSSELOT GELATINAS"
    assert pedido.incoterm == "CIF LIMON"


async def test_con_solo_las_obligatorias_la_linea_entra(tmp_path: Path) -> None:
    fuente = FuenteZTracking(_llenar(tmp_path, _OBLIGATORIAS))

    pedidos = await fuente.obtener_pedidos()

    assert len(pedidos) == 2
    assert fuente.ilegibles == []


@pytest.mark.parametrize("campo", sorted(_OBLIGATORIAS))
async def test_sin_una_obligatoria_la_linea_no_entra(tmp_path: Path, campo: str) -> None:
    valores = {c: v for c, v in _OBLIGATORIAS.items() if c != campo}
    fuente = FuenteZTracking(_llenar(tmp_path, valores))

    pedidos = await fuente.obtener_pedidos()

    # La vía vacía la deja pasar el lector; la rechaza la carga (`sin_via_transporte`).
    if campo == "via_transporte":
        assert all(p.via_transporte is None for p in pedidos)
    else:
        assert pedidos == []
        assert len(fuente.ilegibles) == 2
