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

Por qué el mapeo es por rótulo y no por posición
-------------------------------------------------

La primera versión mapeaba **por posición** y usaba el rótulo solo para
verificar. La entrega del 23/09/2026 demostró que esa elección estaba mal:
`WK38` insertó seis columnas en medio de `PRODUCCION`, movió otras cuatro y
puso un renglón de agrupación encima del encabezado. Ninguna columna cambió de
nombre, pero **todos** los índices se corrieron, y el lector —que hacía bien su
trabajo— se negó a leer el libro entero.

Ese archivo lo mantiene gente, a mano, cada semana. Que le agreguen una columna
no es una anomalía: es lo que va a seguir pasando. Así que ahora las columnas se
buscan **por nombre** en el encabezado, y la posición queda como respaldo para
el único rótulo que se sabe roto.

Lo que el archivo real obliga a tratar
--------------------------------------

Medido sobre las dos entregas reales (`2026-Agosto-WK36.xlsx`, 429 líneas, y
`2026 - SEPTIEMBRE - WK38 MOD.xlsx`, 465):

- **El encabezado no siempre está en la fila 1.** En WK38 `PRODUCCION` lo tiene
  en la **fila 2**, debajo de una banda que agrupa las columnas por área
  (`Compras`, `Planificación`). `IDA`, en el mismo libro, lo sigue teniendo en
  la fila 1. Por eso el encabezado se **busca**, no se asume.
- **Las dos hojas ya no tienen la misma forma.** `IDA` trae las cuatro columnas
  de referencia del contrato de `TASK-30` y `PRODUCCION` no; `PRODUCCION`
  renombró `Carga arribo a Costa Rica (SI - NO)` a `ATA CR` e `IDA` la dejó
  como estaba. Buscar por nombre resuelve las dos con un solo mapa: lo que no
  está, no se mapea, y el campo llega en `None`.
- **Las fechas llegan en dos formatos a la vez.** `PRODUCCION` las trae como
  `datetime` e `IDA` mezcla `datetime` con **seriales de Excel** (`45779`) en la
  misma columna. Un lector que asuma uno de los dos pierde la mitad.
- **Los números llegan como texto o como número, sin criterio.** La orden de
  compra es `str` en 269 filas de `PRODUCCION` de WK36 e `int` en 59; en `IDA`
  es siempre `int`. La clave natural tiene que salir igual de las dos.
- **El encabezado de `PRODUCCION` vino roto en WK36:** su primera celda contenía
  `81` en vez de `Documento Compra`. En WK38 ya está corregido, pero el respaldo
  por posición se queda para poder seguir leyendo los archivos viejos.
- **`Posición` aparece dos veces** —la de la orden y la de la solicitud—. Se
  toma la primera, que es la de la orden; la segunda vive más a la derecha.
- **Hay fechas que no son fechas.** WK38 trae un número de orden
  (`4500018608`) en la celda `ETA CR` de una línea, y tres números de entrega
  en celdas con formato de fecha. Una celda mal tecleada no puede tumbar la
  carga: se descarta el valor, no la línea.
- **Hay filas completamente vacías al final** de las dos hojas.

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
from itertools import chain, islice
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


@dataclass(frozen=True, slots=True)
class Columna:
    """Una columna del archivo y cómo encontrarla.

    `rotulo` se compara sin tildes ni mayúsculas, primero exacto y después por
    prefijo, porque varios rótulos arrastran un paréntesis explicativo:
    `'Tipo de proveedor (LOCAL O INTERNACIONAL)'`. El orden importa —exacto
    antes que prefijo— para que `Tipo de referencia`, `Tipo de transporte` y
    `Tipo de proveedor` no se pisen entre sí.

    `alias` son nombres anteriores de la **misma** columna. WK38 renombró
    `Carga arribo a Costa Rica (SI - NO)` a `ATA CR` sin cambiarle el
    contenido; los dos nombres tienen que llevar al mismo campo para que un
    archivo viejo se siga leyendo completo.
    """

    campo: str
    rotulo: str
    alias: tuple[str, ...] = ()
    #: Sin esta columna la hoja no se puede leer: todo `PedidoCrudo` la exige.
    requerido: bool = False
    #: Índice de respaldo cuando el rótulo no aparece. Solo para columnas que
    #: **se sabe** que vienen rotas; poner uno "por si acaso" haría que una
    #: columna ausente se leyera de otra, que es justo el fallo que hay que
    #: evitar: datos plausibles y equivocados.
    respaldo: int | None = None


#: Las columnas que TrackIn necesita del archivo. Los índices aparecen solo en
#: los respaldos; lo demás se resuelve por nombre contra el encabezado real.
COLUMNAS: Final[tuple[Columna, ...]] = (
    # `PRODUCCION` de WK36 traía `81` en esta celda en vez del rótulo. De ahí
    # el respaldo: es la única columna con un defecto conocido y documentado.
    Columna("oc_numero", "Documento Compra", requerido=True, respaldo=0),
    Columna("posicion_oc", "Posición", requerido=True),
    Columna("proveedor_codigo", "Proveedor", requerido=True),
    Columna("proveedor_nombre", "Nombre del Proveedor"),
    Columna("material_codigo", "Material", requerido=True),
    Columna("material_descripcion", "Texto breve Material"),
    # Decisión de Planeación del 04/09/2026: la fecha comprometida es la de
    # entrega de la solicitud de pedido, no la del lead time de SAP.
    Columna("fecha_entrega_pedido", "Fecha Entrega Solped", requerido=True),
    Columna("cantidad", "Cantidad reparto", requerido=True),
    Columna("unidad_medida", "UMP", requerido=True),
    Columna("fabricante", "Fabricante"),
    Columna("incoterm", "Incoterm"),
    Columna("tipo_proveedor", "Tipo de proveedor"),
    Columna("temperatura", "Temperatura"),
    Columna("pais_origen", "Pais de Origen"),
    Columna("via_transporte", "Tipo de transporte"),
    # Llega casi siempre vacía o con `PENDIENTE`: 18 fechas usables en las 429
    # líneas de WK36. Se ingesta igual, porque es la única ETA que el archivo
    # ofrece y `US-09` la usa como último recurso.
    Columna("eta_declarada", "ETA CR"),
    # `ATA CR` **no es una fecha**, aunque el nombre lo sugiera: es la columna
    # `Carga arribo a Costa Rica (SI - NO)` de WK36 renombrada, y sigue trayendo
    # `NO` (143), `PENDIENTE` (67), `N/A` (12) y `SI` (10). Se ingesta como
    # texto y sin normalizar, igual que la vía: decidir qué significa cada valor
    # es RN-17. Para una línea sin referencia es el único indicio de arribo que
    # existe, y no sustituye al ATA confirmado de RN-05.
    Columna("arribo_declarado", "ATA CR", alias=("Carga arribo a Costa Rica",)),
    # Las cuatro del contrato de `TASK-30`, pedidas a Planificación el
    # 23/09/2026 y añadidas a `IDA` en WK38. Vienen vacías en las 96 líneas de
    # esa entrega: la columna existe, el dato todavía no. Se mapean ya para que
    # el día que Logística empiece a llenarlas no haya que tocar código.
    Columna("tipo_referencia", "Tipo de referencia"),
    Columna("numero_referencia", "Número de referencia"),
    Columna("transportista", "Transportista"),
    # Mide la antelación con que se consigue la referencia respecto al zarpe.
    # Es lo que dirá si conviene dar de alta en ShipsGo apenas llega o esperar,
    # que es una decisión de presupuesto: cada alta cuesta un crédito.
    Columna("fecha_referencia", "Fecha de obtención de la referencia"),
)

#: Cuántas filas del principio se inspeccionan buscando el encabezado. WK38 lo
#: tiene en la 2; el margen absorbe que mañana alguien agregue otro título.
_FILAS_INSPECCIONADAS: Final[int] = 5

#: Cuántos rótulos reconocibles bastan para dar la hoja por válida. No se exigen
#: todos —`ATA CR` y las de referencia viven en una sola hoja cada una—, pero sí
#: una mayoría, para que un libro con otra estructura falle en vez de leer
#: columnas equivocadas en silencio.
_MINIMO_ROTULOS_RECONOCIDOS: Final[int] = 10

#: Serial de Excel máximo que se acepta como fecha (≈ año 2173). Por encima de
#: eso no hay fecha posible: es otro dato en la celda equivocada.
_SERIAL_MAXIMO: Final[int] = 100_000

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
    entrega como `datetime` e `IDA` mezcla mitad y mitad. La conversión del
    serial se delega en `openpyxl`, que ya contempla la peculiaridad del
    calendario de Excel —el año 1900 bisiesto que nunca existió— en vez de
    reimplementarla acá con un `timedelta` y equivocarse por un día.

    Un número fuera del rango de seriales plausibles **no es una fecha rara: es
    otra cosa**. WK38 trae `4500018608` —una orden de compra— en una celda
    `ETA CR` con formato de fecha. Ahí openpyxl avisa y devuelve un `time`, pero
    si el mismo número llegara como celda numérica, `from_excel` levantaría
    `OverflowError` y tumbaría la carga entera por una celda mal tecleada. Las
    dos formas devuelven `None`: la línea sigue viva y sin ETA declarada, que es
    exactamente lo que el dato significa.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    if isinstance(valor, int | float):
        # Excel cuenta desde 1899-12-30 y los seriales del archivo rondan los
        # 45 000. Un 0, un negativo o un número de orden no son una fecha.
        if valor <= 0 or valor > _SERIAL_MAXIMO:
            return None
        try:
            convertido = from_excel(valor)
        except (ValueError, OverflowError, OSError):
            return None
        if isinstance(convertido, dt.datetime):
            return convertido.date()
        # Sobre una fracción `from_excel` devuelve una hora, que no es fecha.
        return convertido if isinstance(convertido, dt.date) else None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return dt.date.fromisoformat(texto)
    except ValueError:
        return None


def _sin_tildes(texto: str) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados.

    Lo del espacio no es cosmético: WK38 trae rótulos con espacios dobles
    (`'Diferencia Conversion  SOLED'`) y saltos de línea dentro de la celda.
    """
    tabla = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return " ".join(texto.translate(tabla).lower().split())


def _resolver_columnas(encabezado: tuple[Any, ...]) -> dict[str, int]:
    """Qué columna ocupa cada campo en este encabezado, buscando por nombre.

    Solo por nombre: los respaldos por posición se aplican después, una vez
    decidido cuál de las primeras filas es el encabezado. Mezclarlos acá haría
    que cualquier fila con una celda en la posición 0 puntuara como encabezado.

    Se toma la **primera** coincidencia, que es lo que desambigua la `Posición`
    repetida: la de la orden está a la izquierda, la de la solicitud de pedido
    mucho más a la derecha.
    """
    reales = [_sin_tildes(celda) if isinstance(celda, str) else None for celda in encabezado]
    mapa: dict[str, int] = {}
    for columna in COLUMNAS:
        buscados = [_sin_tildes(r) for r in (columna.rotulo, *columna.alias)]
        indice = next((i for i, real in enumerate(reales) if real in buscados), None)
        if indice is None:
            indice = next(
                (
                    i
                    for i, real in enumerate(reales)
                    if real is not None and any(real.startswith(b) for b in buscados)
                ),
                None,
            )
        if indice is not None:
            mapa[columna.campo] = indice
    return mapa


def _localizar_encabezado(cabecera: list[tuple[Any, ...]]) -> tuple[int, dict[str, int]]:
    """Cuál de las primeras filas es el encabezado, y qué columnas trae.

    Gana la que reconozca más rótulos. En `PRODUCCION` de WK38 la fila 1 es una
    banda de agrupación —`Compras`, `Planificación`— que no reconoce ninguno y
    la 2 reconoce diecisiete; en `IDA` del mismo libro gana la 1. No hay que
    decirle a cada hoja dónde mirar, ni mantener un mapa por hoja que habría
    que corregir con cada entrega.
    """
    mejor_indice, mejor_mapa = 0, dict[str, int]()
    for indice, fila in enumerate(cabecera):
        mapa = _resolver_columnas(fila)
        if len(mapa) > len(mejor_mapa):
            mejor_indice, mejor_mapa = indice, mapa
    return mejor_indice, mejor_mapa


class HojaInesperada(ValueError):
    """El libro no tiene la forma del Z-tracking.

    Es un error y no una línea rechazada: si no aparecen las columnas
    obligatorias, seguir leyendo produciría datos plausibles pero equivocados,
    que es la peor clase de fallo.
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
        # Se materializan solo las primeras filas: el iterador de `read_only`
        # es de una pasada, así que hay que retener las candidatas a encabezado
        # para poder volver sobre las que resulten ser datos.
        cabecera = list(islice(filas, _FILAS_INSPECCIONADAS))
        if not cabecera:
            logger.warning("Z-tracking: la hoja %r está vacía.", nombre)
            return []

        indice_encabezado, mapa = _localizar_encabezado(cabecera)
        encabezado = cabecera[indice_encabezado]
        for columna in COLUMNAS:
            if columna.campo in mapa or columna.respaldo is None:
                continue
            if columna.respaldo < len(encabezado):
                mapa[columna.campo] = columna.respaldo
                logger.info(
                    "Z-tracking: %s!%d no trae el rótulo %r; se usa la columna %d.",
                    nombre,
                    indice_encabezado + 1,
                    columna.rotulo,
                    columna.respaldo,
                )

        faltantes = [c.rotulo for c in COLUMNAS if c.requerido and c.campo not in mapa]
        if faltantes or len(mapa) < _MINIMO_ROTULOS_RECONOCIDOS:
            detalle = f" y faltan las obligatorias {', '.join(faltantes)}" if faltantes else ""
            raise HojaInesperada(
                f"La hoja {nombre!r} de {self.ruta.name} no parece un Z-tracking: se "
                f"reconocieron {len(mapa)} de {len(COLUMNAS)} columnas{detalle}."
            )

        logger.debug(
            "Z-tracking: %s — encabezado en la fila %d, %d columnas reconocidas.",
            nombre,
            indice_encabezado + 1,
            len(mapa),
        )

        leidas: list[PedidoCrudo] = []
        # La primera fila de datos es la siguiente al encabezado; las que
        # quedaron en el buffer detrás de él son datos y hay que leerlas.
        datos = chain(cabecera[indice_encabezado + 1 :], filas)
        for numero, fila in enumerate(datos, start=indice_encabezado + 2):
            if all(celda is None for celda in fila):
                continue  # cola de filas vacías; no es un error ni se reporta
            linea = self._construir(fila, mapa, nombre, numero)
            if linea is not None:
                leidas.append(linea)
        return leidas

    def _construir(
        self, fila: tuple[Any, ...], mapa: dict[str, int], hoja: str, numero: int
    ) -> PedidoCrudo | None:
        """Una fila a `PedidoCrudo`, o `None` anotando por qué no se pudo."""

        def celda(campo: str) -> Any:
            indice = mapa.get(campo)
            if indice is None or indice >= len(fila):
                return None
            return fila[indice]

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
            # El archivo sigue sin traer columna de destino: el contrato de
            # `TASK-30` se la pidió a Planificación y WK38 tampoco la trae, así
            # que el destino se infiere de la vía en `carga.resolver_destino`.
            destino_codigo=None,
            # Todo lo de abajo va **sin normalizar**, a propósito (RN-17).
            via_transporte=_a_texto(celda("via_transporte")),
            # Aquí sí se convierte, porque `PENDIENTE` y `N/A` no son fechas y
            # `_a_fecha` ya los descarta: no hay decisión de negocio que tomar.
            eta_declarada=_a_fecha(celda("eta_declarada")),
            arribo_declarado=_a_texto(celda("arribo_declarado")),
            pais_origen=_a_texto(celda("pais_origen")),
            incoterm=_a_texto(celda("incoterm")),
            temperatura=_a_texto(celda("temperatura")),
            tipo_proveedor=_a_texto(celda("tipo_proveedor")),
            fabricante=_a_texto(celda("fabricante")),
            # Existen como columna desde WK38 y llegan vacías: ausente sigue
            # siendo el caso normal y el pedido nace `SIN_TRACKING` (RN-02).
            tipo_referencia=_a_texto(celda("tipo_referencia")),
            numero_referencia=_a_texto(celda("numero_referencia")),
            transportista=_a_texto(celda("transportista")),
            fecha_referencia=_a_fecha(celda("fecha_referencia")),
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
    "Columna",
    "FuenteZTracking",
    "HojaInesperada",
    "LineaIlegible",
]
