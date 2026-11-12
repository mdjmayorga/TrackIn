"""Los pedidos de la grilla en un Excel que se vuelve a cargar — `US-68`.

    «Como usuario de Compras, quiero descargar los pedidos que tiene la grilla en
    un Excel, para llevar una copia local y poder cargarla en otro equipo.»

Decisiones del 12/11/2026 (Mariano): todos los pedidos activos —la grilla sin
filtros—, para Compras y el Administrador, desde la pantalla de carga. Dos hojas:

| Hoja | Qué lleva | Para qué |
|---|---|---|
| `Grilla` | Las nueve columnas del panel, con sus textos | La que se ve al abrir |
| `PRODUCCION` | Las columnas de la plantilla (`US-59`) | La que lee la carga |

El libro **es** el de la plantilla (`plantilla.libro_plantilla`) con una hoja
más y las filas llenas: mismos rótulos, formatos y listas. La carga solo lee
`PRODUCCION` e `IDA`, así que `Grilla` no le estorba.

Para que la carga lo acepte en otra base, sin ShipsGo y sin el destino ya
guardado, dos datos se escriben como la carga los espera y no como se guardan:

- **El incoterm lleva el puerto.** La base guarda solo el código (`CIF`); el
  puerto se resolvió al cargar y quedó en el destino. Se escribe `CIF LIMON`
  (`normalizacion.incoterm_con_lugar`).
- **Solo van las líneas con referencia de embarque.** Desde el 04/11/2026 una
  línea sin BL ni guía no entra; en `PRODUCCION` sería un rechazo seguro. En la
  `Grilla` sí están, porque están en la pantalla.

El comentario del comprador no se guarda: esa columna va vacía.
"""

from __future__ import annotations

import datetime as dt
import io
from collections.abc import Sequence
from typing import Any, Final

from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from app.models.pedido_transito import PedidoTransito
from app.services import normalizacion
from app.services.ingesta.comentario import tipo_de_guia
from app.services.ingesta.plantilla import libro_plantilla
from app.services.ingesta.ztracking import PLANTILLA

HOJA_GRILLA: Final = "Grilla"
HOJA_CARGA: Final = "PRODUCCION"

#: Los textos del panel (`frontend/src/components/estados.ts`), para que la hoja
#: diga lo mismo que la pantalla.
_ETAPAS: Final[dict[str, str]] = {
    "SIN_TRACKING": "Sin Tracking",
    "EN_ORIGEN": "En Origen",
    "EN_TRANSITO": "En Tránsito",
    "EN_DESTINO": "En Destino",
    "EN_PROCESO_ADUANAL": "P. Aduanal",
    "RECIBIDO_EN_PLANTA": "Recibido",
    "CERRADO": "Cerrado",
    "CANCELADO": "Cancelado",
}
_CUMPLIMIENTOS: Final[dict[str, str]] = {
    "A_TIEMPO": "A Tiempo",
    "EN_RIESGO": "En Riesgo",
    "RETRASADO": "Retrasado",
}
_VIAS: Final[dict[str, str]] = {"AEREO": "Aéreo", "MARITIMO": "Marítimo", "TERRESTRE": "Terrestre"}

#: Las columnas de la grilla completa del panel, en su orden (`GrillaPedidos.tsx`).
COLUMNAS_GRILLA: Final[tuple[str, ...]] = (
    "Material",
    "Etapa",
    "Cumplimiento",
    "OC",
    "POS",
    "F. Proyectada",
    "F. Comprometida",
    "Vía",
    "Destino",
)
_ANCHOS_GRILLA: Final = (44, 14, 14, 13, 7, 14, 16, 11, 22)
_FORMATO_FECHA: Final = "dd/mm/yyyy"


def nombre_archivo(hoy: dt.date) -> str:
    return f"TrackIn pedidos {hoy.isoformat()}.xlsx"


def _etapa(pedido: PedidoTransito) -> str:
    # Como `etapaVisible` del panel: un cerrado muestra su cierre, no su etapa.
    if pedido.estado_calculado in ("CERRADO", "CANCELADO"):
        return _ETAPAS[pedido.estado_calculado]
    return _ETAPAS.get(pedido.etapa_viaje, pedido.etapa_viaje)


def _fila_grilla(pedido: PedidoTransito) -> list[Any]:
    return [
        f"{pedido.material.codigo} {pedido.material.descripcion}",
        _etapa(pedido),
        # El panel muestra un guion cuando no se puede evaluar.
        _CUMPLIMIENTOS.get(pedido.estado_cumplimiento or "", "-"),
        pedido.oc_numero,
        pedido.posicion_oc,
        pedido.fecha_proyectada_disponible,
        pedido.fecha_entrega_pedido,
        _VIAS.get(pedido.via_transporte, pedido.via_transporte),
        # Como `destinoCorto`: el código del aeropuerto, el nombre del puerto.
        pedido.destino.codigo if pedido.via_transporte == "AEREO" else pedido.destino.nombre,
    ]


def _tipo_de_documento(tipo: str, numero: str) -> str:
    """`AWB`, como la lista de la plantilla, si la carga va a deducir la misma guía.

    La carga convierte `AWB` en `MAWB` o `HAWB` según la forma del número
    (`tipo_de_guia`). Si deduciría otra, se escribe la guardada, que la carga
    también acepta.
    """
    if tipo in ("MAWB", "HAWB") and tipo_de_guia(numero) == tipo:
        return "AWB"
    return tipo


def _fila_carga(pedido: PedidoTransito) -> dict[str, Any]:
    elemento = pedido.elemento_rastreado
    assert elemento is not None  # solo se llama con referencia
    incoterm = pedido.incoterm
    if pedido.via_transporte != "AEREO":
        # El aéreo tiene un solo destino y la carga lo infiere de la vía.
        incoterm = normalizacion.incoterm_con_lugar(incoterm, pedido.destino.nombre)
    return {
        "oc_numero": pedido.oc_numero,
        "posicion_oc": pedido.posicion_oc,
        "proveedor_codigo": pedido.proveedor.codigo,
        "proveedor_nombre": pedido.proveedor.nombre,
        "material_codigo": pedido.material.codigo,
        "material_descripcion": pedido.material.descripcion,
        "cantidad": float(pedido.cantidad_pedida),
        "unidad_medida": pedido.unidad_medida,
        "fecha_entrega_pedido": pedido.fecha_entrega_pedido,
        "via_transporte": pedido.via_transporte,
        "incoterm": incoterm,
        "pais_origen": pedido.pais_origen.nombre if pedido.pais_origen else None,
        "eta_declarada": pedido.eta_declarada,
        "solicitud_pedido": pedido.solicitud_pedido,
        "tipo_referencia": _tipo_de_documento(
            elemento.tipo_tracking_externo, elemento.tracking_externo
        ),
        "numero_referencia": elemento.tracking_externo,
        "comentario": None,
    }


def _escribir(hoja: Worksheet, numero_fila: int, valores: Sequence[Any]) -> None:
    for columna, valor in enumerate(valores, start=1):
        celda = hoja.cell(row=numero_fila, column=columna, value=valor)
        if isinstance(valor, dt.date):
            # La plantilla da formato a 2000 filas; más allá, también.
            celda.number_format = _FORMATO_FECHA


def generar(pedidos: Sequence[PedidoTransito], ahora: dt.datetime) -> bytes:
    """El libro con los pedidos, listo para devolver como descarga."""
    libro = libro_plantilla()

    grilla = libro.create_sheet(HOJA_GRILLA, 0)
    grilla.append(list(COLUMNAS_GRILLA))
    for columna, ancho in enumerate(_ANCHOS_GRILLA, start=1):
        grilla.cell(row=1, column=columna).font = Font(bold=True)
        grilla.column_dimensions[grilla.cell(row=1, column=columna).column_letter].width = ancho
    for numero_fila, pedido in enumerate(pedidos, start=2):
        _escribir(grilla, numero_fila, _fila_grilla(pedido))
    grilla.freeze_panes = "A2"
    grilla.auto_filter.ref = grilla.dimensions
    libro.active = 0

    carga = libro[HOJA_CARGA]
    con_referencia = [p for p in pedidos if p.elemento_rastreado is not None]
    for numero_fila, pedido in enumerate(con_referencia, start=2):
        fila = _fila_carga(pedido)
        _escribir(carga, numero_fila, [fila[campo] for campo, _ in PLANTILLA])

    libro.properties.title = f"TrackIn: pedidos activos al {ahora:%d/%m/%Y %H:%M}"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


__all__ = ["COLUMNAS_GRILLA", "HOJA_CARGA", "HOJA_GRILLA", "generar", "nombre_archivo"]
