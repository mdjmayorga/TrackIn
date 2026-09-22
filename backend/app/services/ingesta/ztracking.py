"""Lectura del archivo Z-tracking de Logística — `US-31` / RF-31, RF-01.

La vía **oficial** de entrada de pedidos desde la decisión del 03/09/2026, que
formalizó la carga manual y dejó la sincronización con SAP como evolución
futura. Implementa el puerto `FuentePedidos` de `TASK-03`, así que enchufarla no
obliga a tocar el motor de cálculo ni la API.

**Esta clase lee; no normaliza ni persiste.** Entrega `PedidoCrudo` con el texto
tal cual venía, porque quien normaliza es `app.services.normalizacion` en el
paso de `US-32` y quien escribe es `ingesta.carga`. Lo único que sí resuelve acá
es la **forma** del dato —serial de Excel a fecha, celda numérica a texto—,
porque eso es un problema del formato del archivo y no una regla de negocio.

Lo que el archivo real obliga a tratar
--------------------------------------

Medido sobre la muestra del 03/09/2026 (`2026-Agosto-WK36.xlsx`, 429 líneas
útiles en las dos hojas del alcance):

- **Las fechas llegan en dos formatos a la vez.** `PRODUCCION` las trae como
  `datetime` y `IDA` mezcla 49 `datetime` con 49 **seriales de Excel** (`45779`)
  en la misma columna. Un lector que asuma uno de los dos pierde la mitad.
- **Los números llegan como texto o como número, sin criterio.** La orden de
  compra es `str` en 269 filas de `PRODUCCION` y `int` en 59; en `IDA` es
  siempre `int`. La clave natural tiene que salir igual de las dos.
- **El encabezado de `PRODUCCION` está roto:** su primera celda contiene `81`,
  un número, en vez del rótulo `Documento Compra` que sí trae `IDA`. Por eso el
  mapeo va **por posición** y el encabezado solo se usa para verificar que la
  hoja tenga la forma esperada.
- **`Posición` aparece dos veces** —la de la orden y la de la solicitud—, lo que
  vuelve ambiguo cualquier mapeo por nombre.
- **Hay filas completamente vacías al final** de las dos hojas (12 y 10).

Qué se descarta acá y qué se deja pasar
---------------------------------------

Solo se descarta lo que **impide construir la línea**: sin orden, sin posición o
sin los datos que `PedidoCrudo` exige no hay registro que entregar. Todo lo
demás pasa sucio a propósito —`PENDIENTE`, `N/A`, `INDIA` en la columna de la
vía, `AEREO\\nMARITIMO`— porque decidir qué hacer con eso es RN-17, y vive en la
normalización, no acá.

Las líneas descartadas **no se pierden ni abortan la lectura**: quedan en
`ilegibles` con su motivo, para el informe de validación que pide `US-32`.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

from app.services.ingesta.dto import PedidoCrudo

logger = logging.getLogger(__name__)

#: Las dos únicas hojas del alcance (decisión del 03/09/2026). El libro trae
#: otras cinco —`CC-MICRO`, `SERVICIOS`, `RH`, `MTT`, `CONSUMIBLES`— que no son
#: compras de producción y quedan fuera.
HOJAS_EN_ALCANCE: Final[tuple[str, ...]] = ("PRODUCCION", "IDA")

#: Mapeo **por posición**, con el rótulo que se espera encontrar al lado.
#: El rótulo no se usa para mapear —`PRODUCCION` trae `81` en la primera celda
#: y `Posición` está repetida—, solo para verificar que la hoja no cambió de
#: forma. Índices base 0.
COLUMNAS: Final[dict[str, tuple[int, str]]] = {
    "oc_numero": (0, "Documento Compra"),
    "posicion_oc": (1, "Posición"),
    "proveedor_codigo": (3, "Proveedor"),
    "proveedor_nombre": (4, "Nombre del Proveedor"),
    "material_codigo": (5, "Material"),
    "material_descripcion": (6, "Texto breve Material"),
    # Decisión de Planeación del 04/09/2026: la fecha comprometida es la de
    # entrega de la solicitud de pedido, no la del lead time de SAP.
    "fecha_entrega_pedido": (10, "Fecha Entrega Solped"),
    "cantidad": (12, "Cantidad reparto"),
    "unidad_medida": (13, "UMP"),
    "fabricante": (25, "Fabricante"),
    "incoterm": (27, "Incoterm"),
    "tipo_proveedor": (33, "Tipo de proveedor"),
    "temperatura": (34, "Temperatura"),
    "pais_origen": (35, "Pais de Origen"),
    "via_transporte": (36, "Tipo de transporte"),
}

#: Cuántos rótulos reconocibles bastan para dar la hoja por válida. No se exigen
#: todos porque el archivo real ya demostró que uno puede venir roto; se exige
#: una mayoría para que un libro con otra estructura falle en vez de leer
#: columnas equivocadas en silencio.
_MINIMO_ROTULOS_RECONOCIDOS: Final[int] = 10

#: Motivos por los que una línea no llega a existir.
ILEGIBLE_SIN_CLAVE = "sin_clave_natural"
ILEGIBLE_SIN_DATOS_MINIMOS = "sin_datos_minimos"
ILEGIBLE_SIN_FECHA = "sin_fecha_de_entrega"


@dataclass(frozen=True, slots=True)
class LineaIlegible:
    """Una fila que no llegó a `PedidoCrudo`, con dónde estaba y por qué.

    Lleva hoja y número de fila porque el usuario que corrige el archivo
    necesita poder abrirlo y buscar la celda; un motivo sin coordenada obliga a
    adivinar cuál de las 429 líneas era.
    """

    hoja: str
    fila: int
    motivo: str
    detalle: str

    def __str__(self) -> str:
        return f"{self.hoja}!{self.fila}: {self.detalle}"


def _a_texto(valor: Any) -> str | None:
    """Celda a texto, sin decidir nada sobre su contenido.

    Un entero de Excel se convierte sin la cola `.0` que produciría `str()`
    sobre el float: `4500009651.0` no es una orden de compra, es un accidente
    del tipo de celda.
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else str(valor)
    texto = str(valor).strip()
    return texto or None


def _a_entero(valor: Any) -> int | None:
    """Celda a entero. `'90'` e `90` son la misma posición de orden."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor) if valor.is_integer() else None
    try:
        return int(str(valor).strip())
    except ValueError:
        return None


def _a_decimal(valor: Any) -> float | None:
    """Celda a número. La cantidad puede venir con separadores de miles."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        return float(valor)
    texto = str(valor).strip().replace(",", "")
    try:
        return float(texto)
    except ValueError:
        return None


def _a_fecha(valor: Any) -> dt.date | None:
    """Celda a fecha, venga como fecha o como serial de Excel.

    El archivo real trae las dos cosas **en la misma columna**: `PRODUCCION` la
    entrega como `datetime` y `IDA` mezcla mitad y mitad. La conversión del
    serial se delega en `openpyxl`, que ya contempla la peculiaridad del
    calendario de Excel —el año 1900 bisiesto que nunca existió— en vez de
    reimplementarla acá con un `timedelta` y equivocarse por un día.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    if isinstance(valor, int | float):
        # Un serial plausible: Excel cuenta desde 1899-12-30 y los seriales del
        # archivo rondan los 45 000. Un 0 o un negativo no son una fecha.
        if valor <= 0:
            return None
        convertido = from_excel(valor)
        if isinstance(convertido, dt.datetime):
            return convertido.date()
        return convertido if isinstance(convertido, dt.date) else None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return dt.date.fromisoformat(texto)
    except ValueError:
        return None


def _rotulos_reconocidos(encabezado: tuple[Any, ...]) -> int:
    """Cuántas columnas esperadas aparecen donde deberían.

    La comparación es laxa a propósito —sin tildes ni mayúsculas, por prefijo—
    porque los rótulos del archivo llevan saltos de línea y paréntesis
    explicativos: `'Tipo de proveedor (LOCAL O INTERNACIONAL)'`.
    """
    aciertos = 0
    for indice, esperado in COLUMNAS.values():
        if indice >= len(encabezado):
            continue
        celda = encabezado[indice]
        if not isinstance(celda, str):
            continue
        real = _sin_tildes(celda)
        if real.startswith(_sin_tildes(esperado)):
            aciertos += 1
    return aciertos


def _sin_tildes(texto: str) -> str:
    """Minúsculas y vocales sin tilde, para comparar rótulos sin sorpresas."""
    tabla = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(tabla).strip().lower()


class HojaInesperada(ValueError):
    """El libro no tiene la forma del Z-tracking.

    Es un error y no una línea rechazada: si el encabezado no coincide, todas
    las columnas están desplazadas y seguir leyendo produciría datos plausibles
    pero equivocados, que es la peor clase de fallo.
    """


@dataclass(slots=True)
class FuenteZTracking:
    """El archivo de seguimiento de Logística como fuente de pedidos."""

    ruta: Path
    hojas: tuple[str, ...] = HOJAS_EN_ALCANCE
    #: Filas que no llegaron a línea, con su motivo. Se llena en cada lectura.
    ilegibles: list[LineaIlegible] = field(default_factory=list)

    @property
    def nombre(self) -> str:
        return "ztracking"

    @property
    def descripcion(self) -> str:
        return f"Archivo Z-tracking de Logística ({self.ruta.name}), hojas {', '.join(self.hojas)}"

    async def obtener_pedidos(self) -> list[PedidoCrudo]:
        """Lee las hojas del alcance y entrega las líneas legibles.

        No persiste nada, conforme al segundo criterio del puerto. Una fila
        ilegible no detiene la lectura: se anota en `ilegibles` y se sigue, que
        es RN-17 aplicada ya en el borde de entrada.
        """
        if not self.ruta.exists():
            raise FileNotFoundError(f"No existe el archivo Z-tracking: {self.ruta}")

        self.ilegibles = []
        pedidos: list[PedidoCrudo] = []

        # `read_only` para no cargar 1 400 filas en memoria; `data_only` para
        # recibir el **valor calculado** y no el texto de la fórmula: la mitad
        # de las columnas de `PRODUCCION` son XLOOKUP contra otro libro.
        libro = load_workbook(self.ruta, read_only=True, data_only=True)
        try:
            for hoja in self.hojas:
                if hoja not in libro.sheetnames:
                    logger.warning(
                        "Z-tracking: la hoja %r no está en %s; se omite.", hoja, self.ruta.name
                    )
                    continue
                pedidos.extend(self._leer_hoja(libro[hoja], hoja))
        finally:
            libro.close()

        logger.info(
            "Z-tracking: %d líneas leídas de %s, %d ilegibles.",
            len(pedidos),
            self.ruta.name,
            len(self.ilegibles),
        )
        return pedidos

    def _leer_hoja(self, hoja: Any, nombre: str) -> list[PedidoCrudo]:
        filas = hoja.iter_rows(values_only=True)
        try:
            encabezado = next(filas)
        except StopIteration:
            logger.warning("Z-tracking: la hoja %r está vacía.", nombre)
            return []

        reconocidos = _rotulos_reconocidos(encabezado)
        if reconocidos < _MINIMO_ROTULOS_RECONOCIDOS:
            raise HojaInesperada(
                f"La hoja {nombre!r} de {self.ruta.name} no parece un Z-tracking: "
                f"solo {reconocidos} de {len(COLUMNAS)} rótulos esperados están en su sitio."
            )

        leidas: list[PedidoCrudo] = []
        # El encabezado es la fila 1, así que la primera de datos es la 2.
        for numero, fila in enumerate(filas, start=2):
            if all(celda is None for celda in fila):
                continue  # cola de filas vacías; no es un error ni se reporta
            linea = self._construir(fila, nombre, numero)
            if linea is not None:
                leidas.append(linea)
        return leidas

    def _construir(self, fila: tuple[Any, ...], hoja: str, numero: int) -> PedidoCrudo | None:
        """Una fila a `PedidoCrudo`, o `None` anotando por qué no se pudo."""

        def celda(campo: str) -> Any:
            indice = COLUMNAS[campo][0]
            return fila[indice] if indice < len(fila) else None

        oc_numero = _a_texto(celda("oc_numero"))
        posicion = _a_entero(celda("posicion_oc"))
        if not oc_numero or posicion is None:
            self._anotar(
                hoja,
                numero,
                ILEGIBLE_SIN_CLAVE,
                f"sin clave natural: orden={celda('oc_numero')!r}, "
                f"posición={celda('posicion_oc')!r}",
            )
            return None

        material_codigo = _a_texto(celda("material_codigo"))
        proveedor_codigo = _a_texto(celda("proveedor_codigo"))
        cantidad = _a_decimal(celda("cantidad"))
        unidad = _a_texto(celda("unidad_medida"))

        faltantes = [
            rotulo
            for rotulo, presente in (
                ("material", material_codigo),
                ("proveedor", proveedor_codigo),
                ("cantidad", cantidad),
                ("unidad de medida", unidad),
            )
            if not presente
        ]
        if faltantes:
            self._anotar(
                hoja,
                numero,
                ILEGIBLE_SIN_DATOS_MINIMOS,
                f"{oc_numero}-{posicion}: falta {', '.join(faltantes)}",
            )
            return None

        fecha = _a_fecha(celda("fecha_entrega_pedido"))
        if fecha is None:
            # Tres líneas de `IDA` la traen vacía en la muestra real. Es la
            # fecha comprometida de RN-01: sin ella no hay contra qué comparar
            # la proyectada, y el pedido no tiene estado que calcular.
            self._anotar(
                hoja,
                numero,
                ILEGIBLE_SIN_FECHA,
                f"{oc_numero}-{posicion}: 'Fecha Entrega Solped' vacía o ilegible "
                f"({celda('fecha_entrega_pedido')!r})",
            )
            return None

        return PedidoCrudo(
            oc_numero=oc_numero,
            posicion_oc=posicion,
            proveedor_codigo=proveedor_codigo or "",
            proveedor_nombre=_a_texto(celda("proveedor_nombre")) or proveedor_codigo or "",
            material_codigo=material_codigo or "",
            material_descripcion=_a_texto(celda("material_descripcion")) or "",
            cantidad=cantidad or 0.0,
            unidad_medida=unidad or "",
            fecha_entrega_pedido=fecha,
            # El archivo no trae columna de destino. El contrato de `TASK-30`
            # se lo pidió a Planeación y todavía no llega, así que hoy el
            # destino se infiere de la vía en `carga.resolver_destino`.
            destino_codigo=None,
            # Todo lo de abajo va **sin normalizar**, a propósito (RN-17).
            via_transporte=_a_texto(celda("via_transporte")),
            pais_origen=_a_texto(celda("pais_origen")),
            incoterm=_a_texto(celda("incoterm")),
            temperatura=_a_texto(celda("temperatura")),
            tipo_proveedor=_a_texto(celda("tipo_proveedor")),
            fabricante=_a_texto(celda("fabricante")),
            # El contrato de `TASK-30` define tres columnas de referencia que
            # Planeación aún no añadió al archivo: en la muestra del 03/09
            # **ninguna** de las 429 líneas la traía. Ausente es el caso normal,
            # no un error, y el pedido nace `SIN_TRACKING` (RN-02).
            tipo_referencia=None,
            numero_referencia=None,
            transportista=None,
        )

    def _anotar(self, hoja: str, fila: int, motivo: str, detalle: str) -> None:
        self.ilegibles.append(LineaIlegible(hoja=hoja, fila=fila, motivo=motivo, detalle=detalle))
        logger.debug("Z-tracking: %s!%s ilegible — %s", hoja, fila, detalle)


__all__ = [
    "COLUMNAS",
    "HOJAS_EN_ALCANCE",
    "ILEGIBLE_SIN_CLAVE",
    "ILEGIBLE_SIN_DATOS_MINIMOS",
    "ILEGIBLE_SIN_FECHA",
    "FuenteZTracking",
    "HojaInesperada",
    "LineaIlegible",
]
