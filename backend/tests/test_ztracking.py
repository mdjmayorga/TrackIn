"""Pruebas de `app.services.ingesta.ztracking` — `US-31`.

**Por qué los libros son sintéticos.** El Z-tracking real trae nombres de
proveedores, usuarios compradores y precios, y **no está versionado**: el
repositorio solo guarda la muestra anonimizada. Las pruebas construyen libros a
medida que **reproducen los defectos medidos** sobre los archivos reales, igual
que hace la semilla de `TASK-03`.

Las dos entregas reales, y por qué importan las dos
----------------------------------------------------

`WK36` (03/09/2026) y `WK38` (23/09/2026) tienen **formas distintas**, y el
lector tiene que leer las dos: la carga histórica no se rehace cada vez que
Logística reacomoda una columna.

| | WK36 | WK38 |
|---|---|---|
| Encabezado de `PRODUCCION` | fila 1, con `81` en vez del rótulo | fila 2, bajo una banda de agrupación |
| `Cantidad reparto` | columna 12 | columna 14 |
| `Tipo de transporte` | columna 36 | 42 en `PRODUCCION`, 40 en `IDA` |
| Referencia de embarque | no existe | cuatro columnas, solo en `IDA` |
| Indicador de arribo | `Carga arribo a Costa Rica (SI - NO)` | `ATA CR`, mismo contenido |

Por eso los diseños de abajo son **datos del archivo**, no del lector: el lector
ya no conoce ninguna posición salvo el respaldo del rótulo roto.

Los demás defectos que se reproducen, con su medición sobre WK36:

- `Posición` aparece dos veces en el encabezado (orden y solicitud).
- Las fechas vienen como `datetime` **y** como serial de Excel en la misma
  columna: en `IDA`, 49 de cada tipo y 3 vacías.
- La orden de compra es texto en 269 filas y número en 59.
- Las dos hojas terminan con filas completamente vacías (12 y 10).
- La columna de la vía trae `PENDIENTE`, `N/A`, `INDIA`, `Terrestre` y
  `AEREO\\nMARITIMO`, que esta capa **no** normaliza a propósito (RN-17).
- WK38 trae un número de orden en una celda con formato de fecha.

Hay además una prueba contra cada archivo real, que se salta sola si no está.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

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

#: Los rótulos tal como aparecen en el archivo, con su paréntesis explicativo y
#: su salto de línea. Un diseño puede sobreescribir alguno.
_ROTULOS: Final[dict[str, str]] = {
    "oc_numero": "Documento Compra",
    "posicion_oc": "Posición",
    "proveedor_codigo": "Proveedor",
    "proveedor_nombre": "Nombre del Proveedor",
    "material_codigo": "Material",
    "material_descripcion": "Texto breve Material",
    "fecha_entrega_pedido": "Fecha Entrega Solped",
    "cantidad": "Cantidad reparto",
    "unidad_medida": "UMP",
    "fabricante": "Fabricante",
    "incoterm": "Incoterm",
    "tipo_proveedor": "Tipo de proveedor (LOCAL O INTERNACIONAL)",
    "temperatura": "Temperatura",
    "pais_origen": "Pais de Origen",
    "via_transporte": "Tipo de transporte (AEREO, MARITIMO, TERRESTRE)",
    "eta_declarada": "ETA CR (fecha)",
    "arribo_declarado": "Carga arribo a Costa Rica (SI - NO)",
    "tipo_referencia": "Tipo de referencia",
    "numero_referencia": "Número de referencia",
    "transportista": "Transportista",
    "fecha_referencia": "Fecha de obtención de la referencia",
}


#: Centinela para distinguir "no toques la primera celda" de "ponela en `None`".
_SIN_TOCAR: Final[Any] = object()


@dataclass(frozen=True)
class Diseno:
    """Cómo viene una hoja en una entrega concreta del archivo real.

    Reproduce el libro, no el lector: si mañana el lector cambia de estrategia,
    estas posiciones siguen siendo las que Logística entregó.
    """

    ancho: int
    columnas: dict[str, int]
    #: Rótulos que esta entrega escribe distinto (`ATA CR` en WK38).
    rotulos: dict[str, str] = field(default_factory=dict)
    #: Fila de agrupación por área encima del encabezado, como en WK38.
    banda: dict[int, str] | None = None

    def encabezado(self, primera_celda: Any = _SIN_TOCAR) -> list[Any]:
        """El encabezado de la hoja. `primera_celda` reproduce el `81` de WK36."""
        fila: list[Any] = [None] * self.ancho
        for campo, indice in self.columnas.items():
            fila[indice] = self.rotulos.get(campo, _ROTULOS[campo])
        # `Posición` repetida: la de la orden y la de la solicitud de pedido.
        fila[8] = "Posición"
        if primera_celda is not _SIN_TOCAR:
            fila[0] = primera_celda
        return fila

    def linea(self, **valores: Any) -> list[Any]:
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
        fila: list[Any] = [None] * self.ancho
        for campo, valor in base.items():
            indice = self.columnas.get(campo)
            if indice is None:
                raise AssertionError(f"{campo!r} no existe en este diseño del archivo")
            fila[indice] = valor
        return fila

    def hoja(self, *lineas: list[Any], primera_celda: Any = _SIN_TOCAR) -> list[list[Any]]:
        """La hoja entera: banda si la hay, encabezado y datos."""
        filas: list[list[Any]] = []
        if self.banda:
            fila: list[Any] = [None] * self.ancho
            for indice, texto in self.banda.items():
                fila[indice] = texto
            filas.append(fila)
        filas.append(self.encabezado(primera_celda))
        filas.extend(lineas)
        return filas

    def vacia(self) -> list[Any]:
        return [None] * self.ancho


#: La entrega del 03/09/2026: las dos hojas con la misma forma, 42 columnas.
_WK36 = Diseno(
    ancho=42,
    columnas={
        "oc_numero": 0,
        "posicion_oc": 1,
        "proveedor_codigo": 3,
        "proveedor_nombre": 4,
        "material_codigo": 5,
        "material_descripcion": 6,
        "fecha_entrega_pedido": 10,
        "cantidad": 12,
        "unidad_medida": 13,
        "fabricante": 25,
        "incoterm": 27,
        "tipo_proveedor": 33,
        "temperatura": 34,
        "pais_origen": 35,
        "via_transporte": 36,
        "eta_declarada": 37,
        "arribo_declarado": 38,
    },
)

#: La entrega del 23/09/2026, hoja `PRODUCCION`: seis columnas insertadas en
#: medio, una banda de agrupación encima y `ATA CR` en lugar de `Carga arribo`.
_WK38_PRODUCCION = Diseno(
    ancho=47,
    columnas={
        **_WK36.columnas,
        "cantidad": 14,
        "unidad_medida": 15,
        "fabricante": 31,
        "incoterm": 33,
        "tipo_proveedor": 39,
        "temperatura": 40,
        "pais_origen": 41,
        "via_transporte": 42,
        "eta_declarada": 43,
        "arribo_declarado": 44,
    },
    rotulos={"arribo_declarado": "ATA CR"},
    banda={0: "Compras", 7: "Planificación", 11: "Compras"},
)

#: La misma entrega, hoja `IDA`: encabezado en la fila 1 y las cuatro columnas
#: de referencia del contrato de `TASK-30` insertadas antes de la vía.
_WK38_IDA = Diseno(
    ancho=45,
    columnas={
        **_WK36.columnas,
        "tipo_referencia": 36,
        "numero_referencia": 37,
        "transportista": 38,
        "fecha_referencia": 39,
        "via_transporte": 40,
        "eta_declarada": 41,
        "arribo_declarado": 42,
    },
)


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
        # Un número de orden en una celda de fecha. Sin el tope, `from_excel`
        # levanta `OverflowError` y tumba la carga entera. WK38 trae uno.
        (4500018608, None),
        # Una hora suelta tampoco es una fecha: es lo que openpyxl devuelve
        # para las celdas que marca como error de fecha.
        (dt.time(0, 0), None),
    ],
)
def test_a_fecha(entrada: Any, esperado: dt.date | None) -> None:
    assert _a_fecha(entrada) == esperado


async def test_las_dos_formas_de_fecha_conviven_en_la_misma_columna(tmp_path: Path) -> None:
    """El defecto central del archivo real: `IDA` mezcla los dos formatos."""
    hojas = {
        "IDA": _WK36.hoja(
            _WK36.linea(oc_numero=4500009651, posicion_oc=20, fecha_entrega_pedido=45779),
            _WK36.linea(
                oc_numero="4500009652",
                posicion_oc=30,
                fecha_entrega_pedido=dt.datetime(2026, 5, 29),
            ),
        )
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
        "PRODUCCION": _WK36.hoja(_WK36.linea(oc_numero="4500000001"), primera_celda=81),
        "IDA": _WK36.hoja(_WK36.linea(oc_numero="4500000002")),
        "CC-MICRO": _WK36.hoja(_WK36.linea(oc_numero="4500000003")),
        "SERVICIOS": _WK36.hoja(_WK36.linea(oc_numero="4500000004")),
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert {p.oc_numero for p in pedidos} == {"4500000001", "4500000002"}


async def test_una_hoja_del_alcance_que_no_existe_no_rompe(tmp_path: Path, caplog) -> None:
    """Un libro sin `IDA` se lee igual: se avisa y se sigue con lo que hay."""
    hojas = {"PRODUCCION": _WK36.hoja(_WK36.linea(), primera_celda=81)}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len(pedidos) == 1
    assert "IDA" in caplog.text


def test_el_alcance_son_exactamente_dos_hojas() -> None:
    assert HOJAS_EN_ALCANCE == ("PRODUCCION", "IDA")


# --- Forma del encabezado --------------------------------------------------


async def test_el_encabezado_roto_de_produccion_no_impide_leer(tmp_path: Path) -> None:
    """`PRODUCCION` de WK36 trae `81` donde `IDA` trae `Documento Compra`.

    Es la única columna con respaldo por posición. Sin él, la hoja con más
    líneas del archivo de septiembre sería ilegible entera por una celda.
    """
    hojas = {"PRODUCCION": _WK36.hoja(_WK36.linea(), primera_celda=81)}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len(pedidos) == 1
    assert pedidos[0].oc_numero == "4500016171"


async def test_el_encabezado_de_wk38_no_esta_en_la_primera_fila(tmp_path: Path) -> None:
    """WK38 puso una banda de agrupación por área encima del encabezado.

    La fila 1 solo trae `Compras` y `Planificación`. Si el lector asumiera que
    el encabezado es la primera fila, no reconocería ni una columna.
    """
    hojas = {"PRODUCCION": _WK38_PRODUCCION.hoja(_WK38_PRODUCCION.linea())}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len(pedidos) == 1
    assert pedidos[0].oc_numero == "4500016171"


async def test_las_columnas_corridas_de_wk38_se_encuentran_por_nombre(tmp_path: Path) -> None:
    """La razón de ser del cambio de estrategia.

    WK38 insertó seis columnas en medio de `PRODUCCION`: `Cantidad reparto`
    pasó de la 12 a la 14 y la vía de la 36 a la 42. Ninguna cambió de nombre.
    Un mapeo por posición leería la cantidad de `Estado de conversión de PO`.
    """
    hojas = {
        "PRODUCCION": _WK38_PRODUCCION.hoja(
            _WK38_PRODUCCION.linea(cantidad=3900, unidad_medida="UN", via_transporte="AEREO")
        )
    }
    (pedido,) = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedido.cantidad == 3900.0
    assert pedido.unidad_medida == "UN"
    assert pedido.via_transporte == "AEREO"


async def test_las_dos_hojas_pueden_tener_formas_distintas(tmp_path: Path) -> None:
    """En WK38 ya no la tienen: `IDA` trae referencia y `PRODUCCION` no.

    Buscar por nombre resuelve las dos con un solo mapa. Un mapa por hoja
    habría que corregirlo con cada entrega, que es el trabajo que se evita.
    """
    hojas = {
        "PRODUCCION": _WK38_PRODUCCION.hoja(
            _WK38_PRODUCCION.linea(oc_numero="4500000001", arribo_declarado="SI")
        ),
        "IDA": _WK38_IDA.hoja(
            _WK38_IDA.linea(oc_numero="4500000002", numero_referencia="MSKU1234565")
        ),
    }
    produccion, ida = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert produccion.arribo_declarado == "SI"
    assert produccion.numero_referencia is None
    assert ida.numero_referencia == "MSKU1234565"
    assert ida.arribo_declarado is None


async def test_un_libro_con_otra_estructura_falla_en_vez_de_leer_mal(tmp_path: Path) -> None:
    """Columnas desplazadas producirían datos plausibles pero equivocados.

    Es la peor clase de fallo: nada revienta y todo queda mal. Mejor detenerse.
    """
    hojas = {"PRODUCCION": [["a", "b", "c", "d"], ["1", "2", "3", "4"]]}
    with pytest.raises(HojaInesperada, match="no parece un Z-tracking"):
        await _fuente(tmp_path, hojas).obtener_pedidos()


async def test_sin_una_columna_obligatoria_la_hoja_se_rechaza_entera(tmp_path: Path) -> None:
    """Reconocer casi todo no basta si falta algo que `PedidoCrudo` exige.

    Una hoja sin `Cantidad reparto` no produce líneas incompletas: no produce
    ninguna, y el error dice cuál columna falta para poder arreglar el archivo.
    """
    encabezado = _WK36.encabezado()
    encabezado[_WK36.columnas["cantidad"]] = "Otra cosa"
    hojas = {"IDA": [encabezado, _WK36.linea()]}

    with pytest.raises(HojaInesperada, match="Cantidad reparto"):
        await _fuente(tmp_path, hojas).obtener_pedidos()


async def test_una_columna_ausente_no_se_lee_de_otra(tmp_path: Path) -> None:
    """`PRODUCCION` de WK38 no trae las columnas de referencia.

    Ausente tiene que llegar como `None`, no como el contenido de la columna
    vecina. Es lo que evita que ningún campo opcional tenga respaldo posicional.
    """
    hojas = {"PRODUCCION": _WK38_PRODUCCION.hoja(_WK38_PRODUCCION.linea())}
    (pedido,) = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedido.tipo_referencia is None
    assert pedido.numero_referencia is None
    assert pedido.transportista is None
    assert pedido.fecha_referencia is None


async def test_una_hoja_vacia_no_rompe(tmp_path: Path) -> None:
    pedidos = await _fuente(tmp_path, {"PRODUCCION": []}).obtener_pedidos()
    assert pedidos == []


# --- Filas que no llegan a línea -------------------------------------------


async def test_las_filas_vacias_del_final_se_omiten_sin_reportarse(tmp_path: Path) -> None:
    """Las dos hojas reales terminan con 12 y 10 filas vacías. No son errores."""
    hojas = {
        "PRODUCCION": _WK36.hoja(_WK36.linea(), _WK36.vacia(), _WK36.vacia(), primera_celda=81)
    }
    fuente = _fuente(tmp_path, hojas)
    pedidos = await fuente.obtener_pedidos()

    assert len(pedidos) == 1
    assert fuente.ilegibles == []


async def test_sin_clave_natural_se_anota_y_se_sigue(tmp_path: Path) -> None:
    hojas = {
        "PRODUCCION": _WK36.hoja(
            _WK36.linea(oc_numero=None),
            _WK36.linea(oc_numero="4500000002"),
            primera_celda=81,
        )
    }
    fuente = _fuente(tmp_path, hojas)
    pedidos = await fuente.obtener_pedidos()

    assert [p.oc_numero for p in pedidos] == ["4500000002"]
    assert [i.motivo for i in fuente.ilegibles] == [ILEGIBLE_SIN_CLAVE]


async def test_sin_datos_minimos_se_anota_con_lo_que_falta(tmp_path: Path) -> None:
    hojas = {
        "PRODUCCION": _WK36.hoja(
            _WK36.linea(material_codigo=None, unidad_medida=None), primera_celda=81
        )
    }
    fuente = _fuente(tmp_path, hojas)

    assert await fuente.obtener_pedidos() == []
    (ilegible,) = fuente.ilegibles
    assert ilegible.motivo == ILEGIBLE_SIN_DATOS_MINIMOS
    assert "material" in ilegible.detalle
    assert "unidad de medida" in ilegible.detalle


@pytest.mark.parametrize("vacia", [None, 0, "PENDIENTE", dt.time(0, 0)])
async def test_sin_fecha_comprometida_se_rechaza(tmp_path: Path, vacia: Any) -> None:
    """Es la fecha de RN-01: sin ella no hay contra qué comparar la proyectada.

    Cinco líneas de cada archivo real caen acá: en WK36 tres con `None` y dos
    con `0`; en WK38 las cinco con celdas que openpyxl marca como error.
    """
    hojas = {"IDA": _WK36.hoja(_WK36.linea(fecha_entrega_pedido=vacia))}
    fuente = _fuente(tmp_path, hojas)

    assert await fuente.obtener_pedidos() == []
    assert fuente.ilegibles[0].motivo == ILEGIBLE_SIN_FECHA


async def test_la_ilegible_dice_hoja_y_fila(tmp_path: Path) -> None:
    """Sin coordenada, corregir el archivo obliga a adivinar cuál línea era."""
    hojas = {"IDA": _WK36.hoja(_WK36.linea(), _WK36.linea(oc_numero=None))}
    fuente = _fuente(tmp_path, hojas)
    await fuente.obtener_pedidos()

    (ilegible,) = fuente.ilegibles
    assert ilegible.hoja == "IDA"
    assert ilegible.fila == 3  # encabezado en 1, primera línea en 2
    assert str(ilegible).startswith("IDA!3:")


async def test_la_fila_de_la_ilegible_cuenta_la_banda_de_wk38(tmp_path: Path) -> None:
    """El número tiene que ser el que muestra Excel, no el de la línea de datos.

    Con el encabezado en la fila 2, la primera línea es la 3. Restar mal por uno
    manda a quien corrige el archivo a la celda equivocada.
    """
    hojas = {
        "PRODUCCION": _WK38_PRODUCCION.hoja(
            _WK38_PRODUCCION.linea(), _WK38_PRODUCCION.linea(oc_numero=None)
        )
    }
    fuente = _fuente(tmp_path, hojas)
    await fuente.obtener_pedidos()

    (ilegible,) = fuente.ilegibles
    assert ilegible.fila == 4  # banda en 1, encabezado en 2, primera línea en 3


async def test_cada_lectura_reinicia_las_ilegibles(tmp_path: Path) -> None:
    """Releer el mismo archivo no debe acumular el informe de la vez anterior."""
    hojas = {"PRODUCCION": _WK36.hoja(_WK36.linea(oc_numero=None), primera_celda=81)}
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
    hojas = {"PRODUCCION": _WK36.hoja(_WK36.linea(via_transporte=sucia), primera_celda=81)}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedidos[0].via_transporte == sucia


async def test_el_incoterm_y_el_pais_pasan_sin_tocar(tmp_path: Path) -> None:
    hojas = {
        "PRODUCCION": _WK36.hoja(
            _WK36.linea(incoterm="CIF LIMON", pais_origen="Estados Unidos"), primera_celda=81
        )
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedidos[0].incoterm == "CIF LIMON"
    assert pedidos[0].pais_origen == "Estados Unidos"


@pytest.mark.parametrize("diseno", [_WK36, _WK38_PRODUCCION], ids=["WK36", "WK38"])
@pytest.mark.parametrize("valor", ["SI", "NO", "PENDIENTE", "N/A"])
async def test_ata_cr_es_el_indicador_de_arribo_renombrado(
    tmp_path: Path, diseno: Diseno, valor: str
) -> None:
    """WK38 llamó `ATA CR` a `Carga arribo a Costa Rica (SI - NO)`.

    El nombre sugiere una fecha y **no lo es**: de las 369 líneas de WK38, 143
    dicen `NO`, 67 `PENDIENTE`, 12 `N/A` y 10 `SI`. Los dos rótulos tienen que
    llevar al mismo campo, o un archivo viejo pierde la columna en silencio.
    """
    hojas = {"PRODUCCION": diseno.hoja(diseno.linea(arribo_declarado=valor), primera_celda=81)}
    (pedido,) = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedido.arribo_declarado == valor


async def test_la_referencia_de_ida_llega_cuando_el_archivo_la_trae(tmp_path: Path) -> None:
    """Las cuatro columnas del contrato de `TASK-30`, añadidas a `IDA` en WK38.

    Vienen vacías en las 96 líneas de esa entrega, pero se mapean ya: el día que
    Logística empiece a llenarlas, el dato fluye sin tocar código.
    """
    hojas = {
        "IDA": _WK38_IDA.hoja(
            _WK38_IDA.linea(
                tipo_referencia="BL",
                numero_referencia="MSKU1234565",
                transportista="MAERSK",
                fecha_referencia=dt.datetime(2026, 9, 18),
            )
        )
    }
    (pedido,) = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedido.tipo_referencia == "BL"
    assert pedido.numero_referencia == "MSKU1234565"
    assert pedido.transportista == "MAERSK"
    assert pedido.fecha_referencia == dt.date(2026, 9, 18)


async def test_la_referencia_llega_vacia_cuando_la_columna_no_esta(tmp_path: Path) -> None:
    """Es el caso mayoritario: el pedido nace `SIN_TRACKING` (RN-02).

    En WK36 la columna no existía; en WK38 existe en `IDA` y llega vacía. Las
    dos situaciones tienen que verse igual desde el DTO.
    """
    hojas = {"PRODUCCION": _WK36.hoja(_WK36.linea(), primera_celda=81)}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert pedidos[0].tipo_referencia is None
    assert pedidos[0].numero_referencia is None
    assert pedidos[0].destino_codigo is None


async def test_un_numero_de_orden_en_la_celda_de_la_eta_no_mata_la_linea(tmp_path: Path) -> None:
    """WK38 trae `4500018608` en una celda `ETA CR`.

    Como serial de Excel ese número levanta `OverflowError`. Una celda mal
    tecleada no puede tumbar la carga de las otras 464 líneas: se descarta el
    valor —que es lo que significa— y la línea sigue viva.
    """
    hojas = {"PRODUCCION": _WK38_PRODUCCION.hoja(_WK38_PRODUCCION.linea(eta_declarada=4500018608))}
    fuente = _fuente(tmp_path, hojas)
    (pedido,) = await fuente.obtener_pedidos()

    assert pedido.eta_declarada is None
    assert fuente.ilegibles == []


# --- El puerto -------------------------------------------------------------


def test_cumple_el_puerto(tmp_path: Path) -> None:
    fuente = FuenteZTracking(ruta=tmp_path / "x.xlsx")
    assert isinstance(fuente, FuentePedidos)
    assert fuente.nombre == "ztracking"
    assert "Z-tracking" in fuente.descripcion


def test_solo_la_orden_de_compra_tiene_respaldo_por_posicion() -> None:
    """El respaldo es una excepción documentada, no una red de seguridad.

    Darle uno a una columna opcional haría que su ausencia se leyera de la
    vecina: el fallo silencioso que el mapeo por nombre vino a eliminar.
    """
    con_respaldo = {c.campo for c in COLUMNAS if c.respaldo is not None}
    assert con_respaldo == {"oc_numero"}


async def test_un_archivo_que_no_existe_lo_dice_claro(tmp_path: Path) -> None:
    fuente = FuenteZTracking(ruta=tmp_path / "no-esta.xlsx")
    with pytest.raises(FileNotFoundError, match="Z-tracking"):
        await fuente.obtener_pedidos()


async def test_obtener_no_persiste(tmp_path: Path) -> None:
    """Segundo criterio del puerto: leer no escribe. Corre sin base a propósito."""
    hojas = {"PRODUCCION": _WK36.hoja(_WK36.linea(), primera_celda=81)}
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()
    assert len(pedidos) == 1


async def test_la_clave_natural_sale_igual_de_las_dos_hojas(tmp_path: Path) -> None:
    """`'4500016171'` y `4500016171` son la misma orden; `'90'` y `90`, la misma
    posición. Sin esto, la idempotencia de `carga` fallaría entre hojas."""
    hojas = {
        "PRODUCCION": _WK38_PRODUCCION.hoja(
            _WK38_PRODUCCION.linea(oc_numero="4500016171", posicion_oc="90")
        ),
        "IDA": _WK38_IDA.hoja(_WK38_IDA.linea(oc_numero=4500016171, posicion_oc=90)),
    }
    pedidos = await _fuente(tmp_path, hojas).obtener_pedidos()

    assert len({p.clave for p in pedidos}) == 1
    assert pedidos[0].clave == ("4500016171", 90)


# --- Contra los archivos reales, si están ----------------------------------

_ANALISIS = Path(__file__).resolve().parents[2] / "docs/analisis"

#: Cifras medidas el 24/09/2026 sobre cada entrega: líneas leídas e ilegibles.
#: Si un archivo cambia, la prueba se cae y hay que volver a medir — que es
#: justo lo que uno quiere saber **antes** de una carga, no después.
_MUESTRAS_REALES = [
    ("2026-Agosto-WK36.xlsx", 424, 5),
    ("2026 - SEPTIEMBRE - WK38 MOD.xlsx", 460, 5),
]


@pytest.mark.parametrize(("nombre", "leidas", "ilegibles"), _MUESTRAS_REALES)
async def test_contra_las_muestras_reales(nombre: str, leidas: int, ilegibles: int) -> None:
    """El lector tiene que leer **las dos** entregas, no solo la última.

    La carga histórica no se rehace cada vez que Logística mueve una columna.
    """
    ruta = _ANALISIS / nombre
    if not ruta.exists():
        pytest.skip(f"{nombre} no está versionado")

    fuente = FuenteZTracking(ruta=ruta)
    pedidos = await fuente.obtener_pedidos()

    assert len(pedidos) == leidas
    assert len(fuente.ilegibles) == ilegibles
    assert {i.motivo for i in fuente.ilegibles} == {ILEGIBLE_SIN_FECHA}
    # La vía sucia llega entera hasta la normalización.
    assert {"PENDIENTE", "N/A"} <= {p.via_transporte for p in pedidos}
