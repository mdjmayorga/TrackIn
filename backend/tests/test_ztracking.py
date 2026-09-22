"""Pruebas de `app.services.ingesta.ztracking` — `US-31`.

**Por qué los libros son sintéticos.** El Z-tracking real
(`docs/analisis/2026-Agosto-WK36.xlsx`) trae nombres de proveedores, usuarios
compradores y precios, y **no está versionado**: el repositorio solo guarda la
muestra anonimizada. Las pruebas construyen libros a medida que **reproducen los
defectos medidos** sobre el archivo real del 03/09/2026, igual que hace la
semilla de `TASK-03`.

Los defectos que se reproducen, con su medición:

- `PRODUCCION` trae `81` —un número— en la celda del rótulo `Documento Compra`.
- `Posición` aparece dos veces en el encabezado (orden y solicitud).
- Las fechas vienen como `datetime` **y** como serial de Excel en la misma
  columna: en `IDA`, 49 de cada tipo y 3 vacías.
- La orden de compra es texto en 269 filas y número en 59.
- Las dos hojas terminan con filas completamente vacías (12 y 10).
- La columna de la vía trae `PENDIENTE`, `N/A`, `INDIA`, `Terrestre` y
  `AEREO\\nMARITIMO`, que esta capa **no** normaliza a propósito (RN-17).

Hay además una prueba contra el archivo real, que se salta sola si no está.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook

from app.services.ingesta.base import FuentePedidos
from app.services.ingesta.ztracking import (
    COLUMNAS,
    HOJAS_EN_ALCANCE,
    ILEGIBLE_SIN_CLAVE,
    ILEGIBLE_SIN_DATOS_MINIMOS,
    ILEGIBLE_SIN_FECHA,
    FuenteZTracking,
    HojaInesperada,
    _a_decimal,
    _a_entero,
    _a_fecha,
    _a_texto,
)

#: Ancho real de las hojas del alcance.
_COLUMNAS_TOTALES = 42


def _encabezado(primera_celda: Any = "Documento Compra") -> list[Any]:
    """Encabezado con los rótulos en su posición real.

    `primera_celda` permite reproducir el de `PRODUCCION`, que trae `81`.
    """
    fila: list[Any] = [None] * _COLUMNAS_TOTALES
    for indice, rotulo in COLUMNAS.values():
        fila[indice] = rotulo
    fila[0] = primera_celda
    # `Posición` repetida: la de la orden y la de la solicitud de pedido.
    fila[8] = "Posición"
    # Rótulos reales, con su paréntesis y su salto de línea.
    fila[33] = "Tipo de proveedor (LOCAL O INTERNACIONAL)"
    fila[36] = "Tipo de transporte (AEREO, MARITIMO, TERRESTRE)"
    return fila


def _linea(**valores: Any) -> list[Any]:
    """Una fila de datos completa, con lo mínimo para ser legible."""
    base: dict[str, Any] = {
        "oc_numero": "4500016171",
        "posicion_oc": "90",
        "proveedor_codigo": "1007052",
        "proveedor_nombre": "ROUSSELOT GELATINAS",
        "material_codigo": "11000371",
        "material_descripcion": "Colágeno hidrolizado bovino",
        "fecha_entrega_pedido": dt.datetime(2026, 5, 29),
        "cantidad": 6000000,
        "unidad_medida": "G",
        "incoterm": "CIF LIMON",
        "pais_origen": "BRASIL",
        "via_transporte": "MARITIMO",
    }
    base.update(valores)
    fila: list[Any] = [None] * _COLUMNAS_TOTALES
    for campo, valor in base.items():
        fila[COLUMNAS[campo][0]] = valor
    return fila


def _libro(tmp_path: Path, hojas: dict[str, list[list[Any]]], nombre: str = "zt.xlsx") -> Path:
    """Escribe un libro con las hojas indicadas y devuelve su ruta."""
    wb = Workbook()
    wb.remove(wb.active)
    for hoja, filas in hojas.items():
        ws = wb.create_sheet(hoja)
        for fila in filas:
            ws.append(fila)
    ruta = tmp_path / nombre
    wb.save(ruta)
    return ruta


def _fuente(tmp_path: Path, hojas: dict[str, list[list[Any]]]) -> FuenteZTracking:
    return FuenteZTracking(ruta=_libro(tmp_path, hojas))


# --- Conversión de tipos ---------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (None, None),
        ("  4500016171  ", "4500016171"),
        (4500009651, "4500009651"),
        # Sin la cola `.0`: una celda numérica no convierte una orden en float.
        (4500009651.0, "4500009651"),
        (12.5, "12.5"),
        ("", None),
        ("   ", None),
        (True, None),  # un booleano no es un identificador
    ],
)
def test_a_texto(entrada: Any, esperado: str | None) -> None:
    assert _a_texto(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("90", 90), (20, 20), (20.0, 20), (20.5, None), ("", None), (None, None), ("x", None)],
)
def test_a_entero(entrada: Any, esperado: int | None) -> None:
    """`'90'` de PRODUCCION y `20` de IDA son la misma clase de dato."""
    assert _a_entero(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(6000000, 6000000.0), ("3,900", 3900.0), ("12.5", 12.5), (None, None), ("N/A", None)],
)
def test_a_decimal(entrada: Any, esperado: float | None) -> None:
    assert _a_decimal(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (dt.datetime(2026, 5, 29), dt.date(2026, 5, 29)),
        (dt.date(2026, 5, 29), dt.date(2026, 5, 29)),
        # El serial de Excel, que es la mitad de la columna en IDA.
        (45779, dt.date(2025, 5, 2)),
        ("2026-05-29", dt.date(2026, 5, 29)),
        (None, None),
        (0, None),  # dos líneas reales de IDA traen 0, que no es una fecha
        (-5, None),
        ("PENDIENTE", None),
    ],
)
def test_a_fecha(entrada: Any, esperado: dt.date | None) -> None:
    assert _a_fecha(entrada) == esperado


async def test_las_dos_formas_de_fecha_conviven_en_la_misma_columna(tmp_path: Path) -> None:
    """El defecto central del archivo real: `IDA` mezcla los dos formatos."""
    hojas = {
        "IDA": [
            _encabezado(),
            _linea(oc_numero=4500009651, posicion_oc=20, fecha_entrega_pedido=45779),
            _linea(
                oc_numero="4500009652",
                posicion_oc=30,
                fecha_entrega_pedido=dt.datetime(2026, 5, 29),
            ),
        ]
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert [p.fecha_entrega_pedido for p in pedidos] == [
        dt.date(2025, 5, 2),
        dt.date(2026, 5, 29),
    ]


# --- Alcance de hojas ------------------------------------------------------


async def test_solo_lee_produccion_e_ida(tmp_path: Path) -> None:
    """Decisión del 03/09: las otras cinco hojas no son compras de producción."""
    hojas = {
        "PRODUCCION": [_encabezado(81), _linea(oc_numero="4500000001")],
        "IDA": [_encabezado(), _linea(oc_numero="4500000002")],
        "CC-MICRO": [_encabezado(), _linea(oc_numero="4500000003")],
        "SERVICIOS": [_encabezado(), _linea(oc_numero="4500000004")],
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert {p.oc_numero for p in pedidos} == {"4500000001", "4500000002"}


async def test_una_hoja_del_alcance_que_no_existe_no_rompe(tmp_path: Path, caplog) -> None:
    """Un libro sin `IDA` se lee igual: se avisa y se sigue con lo que hay."""
    hojas = {"PRODUCCION": [_encabezado(81), _linea()]}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len(pedidos) == 1
    assert "IDA" in caplog.text


def test_el_alcance_son_exactamente_dos_hojas() -> None:
    assert HOJAS_EN_ALCANCE == ("PRODUCCION", "IDA")


# --- Forma del encabezado --------------------------------------------------


async def test_el_encabezado_roto_de_produccion_no_impide_leer(tmp_path: Path) -> None:
    """`PRODUCCION` trae `81` donde `IDA` trae `Documento Compra`.

    Por eso el mapeo va por posición: si dependiera del rótulo, la hoja con más
    líneas del archivo real sería ilegible.
    """
    hojas = {"PRODUCCION": [_encabezado(81), _linea()]}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len(pedidos) == 1
    assert pedidos[0].oc_numero == "4500016171"


async def test_un_libro_con_otra_estructura_falla_en_vez_de_leer_mal(tmp_path: Path) -> None:
    """Columnas desplazadas producirían datos plausibles pero equivocados.

    Es la peor clase de fallo: nada revienta y todo queda mal. Mejor detenerse.
    """
    hojas = {"PRODUCCION": [["a", "b", "c", "d"], ["1", "2", "3", "4"]]}
    with pytest.raises(HojaInesperada, match="no parece un Z-tracking"):
        await _fuente(tmp_path, hojas).obtener_pedidos()


async def test_una_hoja_vacia_no_rompe(tmp_path: Path) -> None:
    pedidos = await _fuente(tmp_path, {"PRODUCCION": []}).obtener_pedidos()
    assert pedidos == []


# --- Filas que no llegan a línea -------------------------------------------


async def test_las_filas_vacias_del_final_se_omiten_sin_reportarse(tmp_path: Path) -> None:
    """Las dos hojas reales terminan con 12 y 10 filas vacías. No son errores."""
    hojas = {
        "PRODUCCION": [
            _encabezado(81),
            _linea(),
            [None] * _COLUMNAS_TOTALES,
            [None] * _COLUMNAS_TOTALES,
        ]
    }
    fuente = _fuente(tmp_path, hojas)
    pedidos = await fuente.obtener_pedidos()

    assert len(pedidos) == 1
    assert fuente.ilegibles == []


async def test_sin_clave_natural_se_anota_y_se_sigue(tmp_path: Path) -> None:
    hojas = {
        "PRODUCCION": [
            _encabezado(81),
            _linea(oc_numero=None),
            _linea(oc_numero="4500000002"),
        ]
    }
    fuente = _fuente(tmp_path, hojas)
    pedidos = await fuente.obtener_pedidos()

    assert [p.oc_numero for p in pedidos] == ["4500000002"]
    assert [i.motivo for i in fuente.ilegibles] == [ILEGIBLE_SIN_CLAVE]


async def test_sin_datos_minimos_se_anota_con_lo_que_falta(tmp_path: Path) -> None:
    hojas = {"PRODUCCION": [_encabezado(81), _linea(material_codigo=None, unidad_medida=None)]}
    fuente = _fuente(tmp_path, hojas)

    assert await fuente.obtener_pedidos() == []
    (ilegible,) = fuente.ilegibles
    assert ilegible.motivo == ILEGIBLE_SIN_DATOS_MINIMOS
    assert "material" in ilegible.detalle
    assert "unidad de medida" in ilegible.detalle


@pytest.mark.parametrize("vacia", [None, 0, "PENDIENTE"])
async def test_sin_fecha_comprometida_se_rechaza(tmp_path: Path, vacia: Any) -> None:
    """Es la fecha de RN-01: sin ella no hay contra qué comparar la proyectada.

    Cinco líneas del archivo real caen acá — tres con `None` y dos con `0`.
    """
    hojas = {"IDA": [_encabezado(), _linea(fecha_entrega_pedido=vacia)]}
    fuente = _fuente(tmp_path, hojas)

    assert await fuente.obtener_pedidos() == []
    assert fuente.ilegibles[0].motivo == ILEGIBLE_SIN_FECHA


async def test_la_ilegible_dice_hoja_y_fila(tmp_path: Path) -> None:
    """Sin coordenada, corregir el archivo obliga a adivinar cuál línea era."""
    hojas = {
        "IDA": [_encabezado(), _linea(), _linea(oc_numero=None)],
    }
    fuente = _fuente(tmp_path, hojas)
    await fuente.obtener_pedidos()

    (ilegible,) = fuente.ilegibles
    assert ilegible.hoja == "IDA"
    assert ilegible.fila == 3  # encabezado en 1, primera línea en 2
    assert str(ilegible).startswith("IDA!3:")


async def test_cada_lectura_reinicia_las_ilegibles(tmp_path: Path) -> None:
    """Releer el mismo archivo no debe acumular el informe de la vez anterior."""
    hojas = {"PRODUCCION": [_encabezado(81), _linea(oc_numero=None)]}
    fuente = _fuente(tmp_path, hojas)

    await fuente.obtener_pedidos()
    await fuente.obtener_pedidos()

    assert len(fuente.ilegibles) == 1


# --- Lo que NO se normaliza acá --------------------------------------------


@pytest.mark.parametrize("sucia", ["PENDIENTE", "N/A", "INDIA", "Terrestre", "AEREO\nMARITIMO"])
async def test_la_via_sucia_pasa_tal_cual(tmp_path: Path, sucia: str) -> None:
    """RN-17 vive en la normalización (`US-32`), no en el lector.

    Si esta capa decidiera, cada fuente nueva tendría que reimplementar las
    reglas y se dispersarían. El DTO es texto crudo a propósito.
    """
    hojas = {"PRODUCCION": [_encabezado(81), _linea(via_transporte=sucia)]}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedidos[0].via_transporte == sucia


async def test_el_incoterm_y_el_pais_pasan_sin_tocar(tmp_path: Path) -> None:
    hojas = {
        "PRODUCCION": [_encabezado(81), _linea(incoterm="CIF LIMON", pais_origen="Estados Unidos")]
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedidos[0].incoterm == "CIF LIMON"
    assert pedidos[0].pais_origen == "Estados Unidos"


async def test_la_referencia_de_embarque_llega_vacia(tmp_path: Path) -> None:
    """El contrato de `TASK-30` pidió tres columnas que el archivo aún no trae.

    En la muestra del 03/09 **ninguna** de las 429 líneas traía referencia. Es
    el caso mayoritario, no un error: el pedido nace `SIN_TRACKING` (RN-02).
    """
    hojas = {"PRODUCCION": [_encabezado(81), _linea()]}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedidos[0].tipo_referencia is None
    assert pedidos[0].numero_referencia is None
    assert pedidos[0].destino_codigo is None


# --- El puerto -------------------------------------------------------------


def test_cumple_el_puerto(tmp_path: Path) -> None:
    fuente = FuenteZTracking(ruta=tmp_path / "x.xlsx")
    assert isinstance(fuente, FuentePedidos)
    assert fuente.nombre == "ztracking"
    assert "Z-tracking" in fuente.descripcion


async def test_un_archivo_que_no_existe_lo_dice_claro(tmp_path: Path) -> None:
    fuente = FuenteZTracking(ruta=tmp_path / "no-esta.xlsx")
    with pytest.raises(FileNotFoundError, match="Z-tracking"):
        await fuente.obtener_pedidos()


async def test_obtener_no_persiste(tmp_path: Path) -> None:
    """Segundo criterio del puerto: leer no escribe. Corre sin base a propósito."""
    hojas = {"PRODUCCION": [_encabezado(81), _linea()]}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()
    assert len(pedidos) == 1


async def test_la_clave_natural_sale_igual_de_las_dos_hojas(tmp_path: Path) -> None:
    """`'4500016171'` y `4500016171` son la misma orden; `'90'` y `90`, la misma
    posición. Sin esto, la idempotencia de `carga` fallaría entre hojas."""
    hojas = {
        "PRODUCCION": [_encabezado(81), _linea(oc_numero="4500016171", posicion_oc="90")],
        "IDA": [_encabezado(), _linea(oc_numero=4500016171, posicion_oc=90)],
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len({p.clave for p in pedidos}) == 1
    assert pedidos[0].clave == ("4500016171", 90)


# --- Contra el archivo real, si está ---------------------------------------

_ARCHIVO_REAL = Path(__file__).resolve().parents[2] / "docs/analisis/2026-Agosto-WK36.xlsx"


@pytest.mark.skipif(not _ARCHIVO_REAL.exists(), reason="el Z-tracking real no está versionado")
async def test_contra_la_muestra_real() -> None:
    """Las cifras medidas el 22/09/2026 sobre la muestra del 03/09.

    Si el archivo cambia, esta prueba se cae y hay que volver a medir — que es
    justo lo que uno quiere saber antes de una carga.
    """
    fuente = FuenteZTracking(ruta=_ARCHIVO_REAL)
    pedidos = await fuente.obtener_pedidos()

    assert len(pedidos) == 424
    assert len(fuente.ilegibles) == 5
    assert {i.motivo for i in fuente.ilegibles} == {ILEGIBLE_SIN_FECHA}
    # La vía sucia llega entera hasta la normalización.
    assert {"PENDIENTE", "N/A", "INDIA"} <= {p.via_transporte for p in pedidos}
