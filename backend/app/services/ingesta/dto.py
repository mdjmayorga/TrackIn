"""Registro de pedido tal como lo entrega una fuente, antes de normalizar.

`TASK-03`. Los campos son **texto crudo a propósito**: la fuente entrega lo que
tiene y quien normaliza es `app.services.normalizacion` (RN-17), en el paso de
validación de `US-32`. Si el DTO ya llegara normalizado, cada nueva fuente
tendría que reimplementar la normalización y las reglas se dispersarían.

La forma de este registro sale del inventario real del Anexo B del SRS, es decir
de la muestra del Z-tracking del 03/09/2026, no de un contrato hipotético.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PedidoCrudo:
    """Una línea de orden de compra tal como llega de la fuente.

    Inmutable: lo que la fuente entregó es evidencia de entrada y no debe
    mutarse durante la carga. Las correcciones producen un registro nuevo.
    """

    # --- Identificación (obligatorios en toda fuente) -----------------------
    oc_numero: str
    posicion_oc: int

    # --- Datos maestros -----------------------------------------------------
    proveedor_codigo: str
    proveedor_nombre: str
    material_codigo: str
    material_descripcion: str
    cantidad: float
    unidad_medida: str
    fecha_entrega_pedido: dt.date

    #: Código del destino en el maestro. `None` si la fuente no lo trae y hay
    #: que inferirlo de la vía de transporte.
    destino_codigo: str | None = None

    # --- Campos que llegan como texto libre y se normalizan después ---------
    via_transporte: str | None = None
    pais_origen: str | None = None
    incoterm: str | None = None
    temperatura: str | None = None
    tipo_proveedor: str | None = None
    fabricante: str | None = None

    #: ETA declarada en el archivo (columna `ETA CR`). Llega casi siempre
    #: vacía: 18 fechas usables en las 429 líneas de la muestra del 03/09.
    eta_declarada: dt.date | None = None

    #: Lo que Logística anotó a mano sobre si la carga llegó: `SI`, `NO`,
    #: `PENDIENTE`, `N/A`. Sale de `Carga arribo a Costa Rica (SI - NO)`, que la
    #: entrega WK38 del 23/09/2026 renombró a `ATA CR` sin cambiarle el
    #: contenido —el nombre sugiere una fecha y no lo es—. **No es el ATA
    #: confirmado de RN-05**: no tiene la trazabilidad de un hito de rastreo,
    #: pero para una línea sin referencia es el único indicio de arribo que hay.
    #: Va sin normalizar, como el resto del texto libre (RN-17).
    arribo_declarado: str | None = None

    # --- Referencia de embarque (contrato de TASK-30) -----------------------
    #: Habitualmente vacíos. La hoja `IDA` tiene las columnas desde WK38
    #: (23/09/2026), pero ninguna de sus 96 líneas las trae llenas, y
    #: `PRODUCCION` —donde viven las 109 líneas marítimas— todavía no las
    #: tiene. Ausente es el caso normal: es la razón de ser del estado
    #: `SIN_TRACKING` (RN-02) y de la asociación manual de RF-03.
    tipo_referencia: str | None = None
    numero_referencia: str | None = None
    transportista: str | None = None

    #: Cuándo obtuvo Logística la referencia. Planificación confirmó el
    #: 23/09/2026 que lo normal es tenerla **al zarpe**; esta columna es lo que
    #: permitirá medir si eso se cumple. Importa por presupuesto: cada alta en
    #: ShipsGo cuesta un crédito, y darla de alta antes de que el embarque
    #: exista gasta el crédito igual.
    fecha_referencia: dt.date | None = None

    @property
    def clave(self) -> tuple[str, int]:
        """Clave natural de la línea: identifica el pedido entre cargas."""
        return (self.oc_numero, self.posicion_oc)

    def __str__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"{self.oc_numero}-{self.posicion_oc}"


__all__ = ["PedidoCrudo"]
