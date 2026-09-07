"""Fuente de datos semilla para desarrollo y demostración.

`TASK-03`. Existe porque el servicio de SAP nunca llegó y la carga del archivo
de Logística (`US-31`) es trabajo del Sprint 4: sin esta fuente no habría con
qué desarrollar el motor de cálculo ni demostrar el sistema en el Informe 1.

**Los datos imitan la muestra real del 03/09/2026**, no un caso ideal. Eso
incluye a propósito los defectos que trae el archivo, porque son los que la
validación de `US-32` tiene que saber manejar:

- Grafías distintas del mismo país (`USA` frente a `ESTADOS UNIDOS`).
- Mayúsculas mezcladas en el incoterm (`Exw`).
- La vía en `PENDIENTE`, que no es un dato.
- Y sobre todo, **la mayoría de las líneas sin referencia de embarque**: en la
  muestra real ninguna de las 429 la traía.
"""

from __future__ import annotations

import datetime as dt

from app.services.ingesta.dto import PedidoCrudo

#: Fecha de referencia de la semilla. Las fechas de entrega se expresan como
#: desplazamientos sobre ella para que el semáforo muestre los tres estados de
#: cumplimiento sin tener que reescribir el archivo cada semana.
_HOY = dt.date(2026, 9, 7)


def _f(dias: int) -> dt.date:
    return _HOY + dt.timedelta(days=dias)


PEDIDOS_SEMILLA: tuple[PedidoCrudo, ...] = (
    # --- Marítimo con contenedor: el caso rastreable por Vizion -------------
    PedidoCrudo(
        oc_numero="4500016171",
        posicion_oc=10,
        proveedor_codigo="1007052",
        proveedor_nombre="Proveedor 0001",
        material_codigo="11000371",
        material_descripcion="Colágeno hidrolizado bovino",
        cantidad=6_000_000,
        unidad_medida="G",
        fecha_entrega_pedido=_f(24),
        destino_codigo="CRMOB",
        via_transporte="MARITIMO",
        pais_origen="BRASIL",
        incoterm="CIF LIMON",
        temperatura="Ambiente",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0001",
        tipo_referencia="CONTENEDOR",
        numero_referencia="MSKU1234567",
        transportista="MAERSK",
    ),
    # --- Marítimo por el Pacífico: verifica que Caldera se distinga ---------
    PedidoCrudo(
        oc_numero="4500017044",
        posicion_oc=20,
        proveedor_codigo="1006804",
        proveedor_nombre="Proveedor 0002",
        material_codigo="17900766",
        material_descripcion="Isopropílico-IPA alcohol (2 propanol)",
        cantidad=40_000,
        unidad_medida="ML",
        fecha_entrega_pedido=_f(41),
        destino_codigo="CRCAL",
        via_transporte="MARITIMO",
        pais_origen="CHINA",
        incoterm="CIP",
        temperatura="Ambiente",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0002",
        tipo_referencia="BL",
        numero_referencia="COSU6789012345",
        transportista="COSCO",
    ),
    # --- Aéreo con MAWB y cadena de frío: el caso de IDA --------------------
    PedidoCrudo(
        oc_numero="4500018231",
        posicion_oc=10,
        proveedor_codigo="1007401",
        proveedor_nombre="Proveedor 0003",
        material_codigo="15900255",
        material_descripcion="Fentermina clorhidrato",
        cantidad=200,
        unidad_medida="MG",
        fecha_entrega_pedido=_f(9),
        destino_codigo="MROC",
        via_transporte="AEREO",
        pais_origen="INDIA",
        incoterm="CIP",
        temperatura="Entre 2°-8° C",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0003",
        tipo_referencia="MAWB",
        numero_referencia="176-12345678",
        transportista="EMIRATES SKYCARGO",
    ),
    # --- Aéreo en riesgo: la fecha comprometida está dentro del umbral ------
    PedidoCrudo(
        oc_numero="4500018460",
        posicion_oc=30,
        proveedor_codigo="1006311",
        proveedor_nombre="Proveedor 0004",
        material_codigo="6001087",
        material_descripcion="Espátula para muestreo 263 mm",
        cantidad=600,
        unidad_medida="UN",
        fecha_entrega_pedido=_f(2),
        destino_codigo="MROC",
        via_transporte="AEREO",
        pais_origen="ALEMANIA",
        incoterm="FCA",
        temperatura="Ambiente",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0004",
        tipo_referencia="MAWB",
        numero_referencia="020-87654321",
        transportista="LUFTHANSA CARGO",
    ),
    # --- SIN TRACKING: el caso mayoritario en la muestra real ---------------
    PedidoCrudo(
        oc_numero="4500018793",
        posicion_oc=10,
        proveedor_codigo="1005792",
        proveedor_nombre="Proveedor 0005",
        material_codigo="6000027",
        material_descripcion="Placa Petri apilable estéril 90x15",
        cantidad=30,
        unidad_medida="CS",
        fecha_entrega_pedido=_f(-12),  # ya vencida: debe salir RETRASADO
        destino_codigo="CRMOB",
        via_transporte="MARITIMO",
        pais_origen="ESPAÑA",
        incoterm="CIF",
        temperatura="Ambiente",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0005",
        # Sin referencia: así llega hoy el cien por ciento del archivo real.
    ),
    # --- SIN TRACKING con incoterm en minúsculas: ejercita el normalizador --
    PedidoCrudo(
        oc_numero="4500019004",
        posicion_oc=40,
        proveedor_codigo="1006256",
        proveedor_nombre="Proveedor 0006",
        material_codigo="8002963",
        material_descripcion="Banda PEBD transp. monoaxial ancho 75 mm",
        cantidad=110_910,
        unidad_medida="G",
        fecha_entrega_pedido=_f(60),
        destino_codigo="CRLIO",
        via_transporte="MARITIMO",
        pais_origen="ESTADOS UNIDOS",
        incoterm="Exw",
        temperatura="AMBIENTE",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0006",
    ),
    # --- Terrestre regional: no es rastreable por Vizion ni Portcast --------
    PedidoCrudo(
        oc_numero="4500019110",
        posicion_oc=10,
        proveedor_codigo="1005226",
        proveedor_nombre="Proveedor 0007",
        material_codigo="8000071",
        material_descripcion="Transparencias 215 mm x 279 mm",
        cantidad=1_500,
        unidad_medida="UN",
        fecha_entrega_pedido=_f(15),
        destino_codigo=None,
        via_transporte="Terrestre",
        pais_origen="GUATEMALA",
        incoterm="LOCAL",
        temperatura="Ambiente",
        tipo_proveedor="LOCAL",
        fabricante=None,
    ),
    # --- Línea sucia: debe quedar marcada para revisión, sin abortar el lote -
    PedidoCrudo(
        oc_numero="4500019233",
        posicion_oc=20,
        proveedor_codigo="1006497",
        proveedor_nombre="Proveedor 0008",
        material_codigo="14001461",
        material_descripcion="Pistón Parker D32-H50",
        cantidad=2,
        unidad_medida="UN",
        fecha_entrega_pedido=_f(33),
        destino_codigo=None,
        via_transporte="PENDIENTE",  # no es un dato: va a revisión
        pais_origen="USA",  # misma nación que «ESTADOS UNIDOS» de arriba
        incoterm="N/A",
        temperatura="N/A",
        tipo_proveedor="INTERNACIONAL",
        fabricante="Fabricante 0008",
    ),
)


class FuenteSemilla:
    """Fuente en memoria con pedidos representativos de la operación real."""

    nombre = "semilla"
    descripcion = (
        "Pedidos de ejemplo en memoria, con la forma y los defectos de la "
        "muestra real del Z-tracking. Solo para desarrollo y demostración."
    )

    async def obtener_pedidos(self) -> list[PedidoCrudo]:
        """Devuelve la semilla completa. No toca la base ni la red."""
        return list(PEDIDOS_SEMILLA)


__all__ = ["PEDIDOS_SEMILLA", "FuenteSemilla"]
