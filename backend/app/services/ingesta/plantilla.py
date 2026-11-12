"""La plantilla vacía del Z-tracking — `US-59`.

    «Como usuario de Compras, quiero descargar la plantilla vacía del Z-tracking
    […] para preparar el archivo con la estructura correcta.»

Las hojas `PRODUCCION` e `IDA`, cada una con **solo el encabezado** de
`ztracking.PLANTILLA`: las columnas que el sistema usa, con `(opcional)` en las
que no son obligatorias (decisión del 02/11/2026). Una tercera hoja,
`INSTRUCCIONES`, dice qué lleva cada columna; el lector no la mira, porque solo
lee las hojas del alcance. Llenada sin cambiarle la estructura, la carga la
acepta sin avisos.

Las listas desplegables de la vía y del tipo de documento no son decoración:
WK43 trajo 274 líneas sin una vía utilizable (vacía, `#N/A`, `PENDIENTE`), y es
el motivo número uno de que una línea no entre.
"""

from __future__ import annotations

import io
from typing import Final

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.services.ingesta.ztracking import HOJAS_EN_ALCANCE, PLANTILLA, SUFIJO_OPCIONAL

NOMBRE_ARCHIVO: Final = "Plantilla Z-tracking.xlsx"
TIPO_XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

#: Hasta qué fila llegan las listas desplegables y el formato de fecha. Las
#: entregas reales rondan las 300 líneas por hoja.
_FILAS_CON_FORMATO: Final = 2000

#: Las columnas que se llenan con una lista cerrada, por campo.
_LISTAS: Final[dict[str, tuple[str, ...]]] = {
    "via_transporte": ("AEREO", "MARITIMO"),
    "tipo_referencia": ("BL", "AWB", "CONTENEDOR", "BOOKING"),
}

#: Las fechas que TrackIn lee, con el formato con que se escriben en Costa Rica.
_FECHAS: Final = ("fecha_entrega_pedido", "eta_declarada")

#: Qué lleva cada columna, para la hoja de instrucciones: formato y para qué la
#: usa el sistema. El orden es el de `PLANTILLA`.
_AYUDA: Final[dict[str, tuple[str, str]]] = {
    "oc_numero": ("10 dígitos, como 4500016172", "Identifica el pedido, junto con la posición"),
    "posicion_oc": ("Entero positivo, como 10", "Identifica el pedido, junto con la OC"),
    "proveedor_codigo": ("Código de SAP", "Proveedor del pedido"),
    "proveedor_nombre": ("Texto", "Se muestra en el panel y el detalle"),
    "material_codigo": ("Código numérico de SAP", "Material del pedido"),
    "material_descripcion": ("Texto", "Se muestra en el panel y el detalle"),
    "cantidad": ("Número mayor que cero", "Cantidad pedida; la recepción se compara con ella"),
    "unidad_medida": ("KG, G, UN…", "Unidad de la cantidad"),
    "fecha_entrega_pedido": (
        "Fecha, como 30/11/2026",
        "Fecha comprometida de llegada a Gutis: contra ella se mide si va a tiempo",
    ),
    "via_transporte": ("AEREO o MARITIMO", "Decide cómo se rastrea y a qué destino llega"),
    "incoterm": (
        "Con el puerto de llegada, como CIF LIMON",
        "Si es marítimo y no trae BL, de aquí sale el puerto. Con EXW, FCA o FOB no lo hay",
    ),
    # `US-44` lo lleva al detalle; hasta entonces se guarda normalizado.
    "pais_origen": ("Nombre del país, como BRASIL", "País de origen del pedido"),
    "eta_declarada": (
        "Fecha, como 30/11/2026, o PENDIENTE",
        "Se usa para proyectar la llegada cuando no hay rastreo",
    ),
    "solicitud_pedido": ("Número de la SOLPED", "Se muestra en la pantalla de planta"),
    "tipo_referencia": (
        "BL, AWB, CONTENEDOR o BOOKING",
        "Con el número, permite rastrear el envío. Sin referencia la línea no entra "
        "(puede ir en Comentarios)",
    ),
    "numero_referencia": (
        "El número tal cual el documento, como MAEU274029064",
        "Lo que se da de alta en ShipsGo. Un número mal escrito gasta un crédito",
    ),
    "comentario": (
        "Texto libre",
        "Si las columnas de documento están vacías, se busca aquí el BL o la guía",
    ),
}

#: Columnas obligatorias cuya celda puede venir en blanco (02/11/2026). Las del
#: documento salieron de aquí el 04/11/2026: sin referencia de embarque la línea
#: ya no entra (`ingesta.carga`), salvo que la traiga en Comentarios.
_PUEDEN_IR_VACIAS: Final = frozenset({"material_descripcion", "solicitud_pedido"})

#: La fila de títulos de la tabla de instrucciones, debajo de las dos notas.
_FILA_TITULOS: Final = 4

_OBLIGATORIA: Final = Font(bold=True, color="FFFFFF")
_FONDO_OBLIGATORIA: Final = PatternFill("solid", fgColor="1F4E78")
_OPCIONAL: Final = Font(bold=True, color="1F1F1F")
_FONDO_OPCIONAL: Final = PatternFill("solid", fgColor="D9E1F2")


def _es_opcional(rotulo: str) -> bool:
    return rotulo.endswith(SUFIJO_OPCIONAL)


def _hoja_de_datos(libro: Workbook, nombre: str) -> None:
    hoja = libro.create_sheet(nombre)
    hoja.append([rotulo for _, rotulo in PLANTILLA])
    hoja.freeze_panes = "A2"
    for indice, (campo, rotulo) in enumerate(PLANTILLA, start=1):
        letra = get_column_letter(indice)
        celda = hoja.cell(row=1, column=indice)
        opcional = _es_opcional(rotulo)
        celda.font = _OPCIONAL if opcional else _OBLIGATORIA
        celda.fill = _FONDO_OPCIONAL if opcional else _FONDO_OBLIGATORIA
        hoja.column_dimensions[letra].width = max(14, min(len(rotulo) + 2, 40))
        rango = f"{letra}2:{letra}{_FILAS_CON_FORMATO}"
        if campo in _LISTAS:
            lista = DataValidation(
                type="list",
                formula1=f'"{",".join(_LISTAS[campo])}"',
                allow_blank=True,
                showErrorMessage=True,
                errorTitle=rotulo,
                error=f"Elija uno de: {', '.join(_LISTAS[campo])}.",
            )
            lista.add(rango)
            hoja.add_data_validation(lista)
        if campo in _FECHAS:
            for (fecha,) in hoja[rango]:
                fecha.number_format = "dd/mm/yyyy"


def _hoja_de_instrucciones(libro: Workbook) -> None:
    hoja = libro.create_sheet("INSTRUCCIONES")
    hoja.append(
        ["Llene las hojas PRODUCCION e IDA. No cambie el nombre ni el orden de las columnas."]
    )
    hoja.append(
        [
            "Las columnas en azul oscuro son obligatorias: tienen que estar en el archivo, "
            "o no se carga nada."
        ]
    )
    hoja.append(
        [
            "En las marcadas «Sí, puede ir vacía» la celda puede quedar en blanco; en las "
            "demás obligatorias, una celda vacía deja la línea fuera."
        ]
    )
    hoja.append(["Columna", "Obligatoria", "Formato", "Para qué la usa TrackIn"])
    for celda in hoja[_FILA_TITULOS]:
        celda.font = Font(bold=True)
    for campo, rotulo in PLANTILLA:
        formato, uso = _AYUDA[campo]
        if campo == "incoterm":
            obligatoria = "Si es marítimo"
        elif _es_opcional(rotulo):
            obligatoria = "No"
        else:
            obligatoria = "Sí, puede ir vacía" if campo in _PUEDEN_IR_VACIAS else "Sí"
        hoja.append([rotulo, obligatoria, formato, uso])
    for letra, ancho in zip("ABCD", (40, 14, 48, 80), strict=True):
        hoja.column_dimensions[letra].width = ancho


def libro_plantilla() -> Workbook:
    """El libro de la plantilla, vacío. La exportación de pedidos (`US-68`) lo llena."""
    libro = Workbook()
    libro.remove(libro.active)
    for nombre in HOJAS_EN_ALCANCE:
        _hoja_de_datos(libro, nombre)
    _hoja_de_instrucciones(libro)
    return libro


def generar_plantilla() -> bytes:
    """El libro de la plantilla, listo para devolver como descarga."""
    salida = io.BytesIO()
    libro_plantilla().save(salida)
    return salida.getvalue()


__all__ = ["NOMBRE_ARCHIVO", "TIPO_XLSX", "generar_plantilla", "libro_plantilla"]
