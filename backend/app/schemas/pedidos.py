"""Contratos de `/pedidos` — `US-16` (RF-04 y RF-05, lado backend).

Dos formas del mismo pedido: el **resumen**, que es una fila de la grilla de
`US-19`, y el **detalle**, que es la vista de `US-20` con el desglose del
cálculo. El resumen lleva solo lo que la grilla pinta; lo demás cuesta joins
que doscientas filas no necesitan.

Los `Literal` repiten los dominios de `app.models.enums` a propósito: así
OpenAPI publica los valores válidos y el frontend los puede generar. Que no se
desincronicen lo vigila `test_pedidos_api.py`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Via = Literal["AEREO", "MARITIMO", "TERRESTRE"]
EtapaViaje = Literal[
    "SIN_TRACKING",
    "EN_ORIGEN",
    "EN_TRANSITO",
    "EN_DESTINO",
    "EN_PROCESO_ADUANAL",
    "RECIBIDO_EN_PLANTA",
]
Cumplimiento = Literal["A_TIEMPO", "EN_RIESGO", "RETRASADO"]

#: El filtro «Etapa» del Figma del 30/09: la columna muestra el estado terminal
#: en las filas cerradas (`wireframes.md` §1.11), así que el filtro también.
EtapaFiltro = Literal[
    "SIN_TRACKING",
    "EN_ORIGEN",
    "EN_TRANSITO",
    "EN_DESTINO",
    "EN_PROCESO_ADUANAL",
    "RECIBIDO_EN_PLANTA",
    "CERRADO",
    "CANCELADO",
]
#: El guion de la columna «Cumplimiento» es una categoría: sin fecha proyectada.
SIN_PROYECCION = "SIN_PROYECCION"
CumplimientoFiltro = Literal["A_TIEMPO", "EN_RIESGO", "RETRASADO", "SIN_PROYECCION"]
EstadoCalculado = Literal[
    "SIN_TRACKING",
    "EN_ORIGEN",
    "EN_TRANSITO",
    "EN_DESTINO",
    "EN_PROCESO_ADUANAL",
    "RECIBIDO_EN_PLANTA",
    "A_TIEMPO",
    "EN_RIESGO",
    "RETRASADO",
    "CERRADO",
    "CANCELADO",
]


class _Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Referencias a los maestros ---------------------------------------------


class ProveedorRef(_Esquema):
    id: int
    codigo: str
    nombre: str


class MaterialRef(_Esquema):
    id: int
    codigo: str
    descripcion: str


class DestinoRef(_Esquema):
    id: int
    codigo: str
    nombre: str


class PaisRef(_Esquema):
    codigo: str
    nombre: str


# --- Listado (RF-04) --------------------------------------------------------


class PedidoResumen(_Esquema):
    """Una fila de la grilla: las once columnas de `wireframes.md` §1.5."""

    id: int
    oc_numero: str
    posicion_oc: int
    tracking_interno: str
    material: MaterialRef
    proveedor: ProveedorRef
    via_transporte: Via
    destino: DestinoRef
    eta_utilizada: dt.datetime | None = Field(
        description="Fecha base del cálculo. Nula cuando RN-16 no pudo proyectar."
    )
    fecha_proyectada_disponible: dt.date | None
    fecha_entrega_pedido: dt.date = Field(description="La fecha comprometida (RN-07 a RN-09).")
    etapa_viaje: EtapaViaje
    estado_cumplimiento: Cumplimiento | None = Field(
        description="Nulo si no hay fecha proyectada: no se puede afirmar si llega a tiempo."
    )
    estado_calculado: EstadoCalculado = Field(description="El que pinta el semáforo (RF-11).")
    rastreable: bool = Field(description="Si tiene elemento rastreado. `false` es RN-02.")
    ultima_actualizacion_fuente: dt.datetime | None = Field(
        description="Antigüedad del último dato bueno de la fuente (RNF-12)."
    )
    ausente_desde: dt.datetime | None = Field(
        description="Desde cuándo la línea dejó de venir en el archivo (`US-31`)."
    )
    fecha_recepcion_planta: dt.datetime | None = Field(
        description="Lo que la grilla muestra en lugar de la ETA al filtrar por terminales."
    )
    cantidad_recibida: Decimal | None


class PaginaPedidos(BaseModel):
    total: int = Field(description="Pedidos que cumplen los filtros, sin paginar.")
    limite: int
    desplazamiento: int
    items: list[PedidoResumen]


# --- Detalle (RF-05) --------------------------------------------------------


class Posicion(BaseModel):
    latitud: float
    longitud: float


class Rastreo(BaseModel):
    """El elemento rastreado vigente: qué se sigue y qué dijo la fuente."""

    tipo: str = Field(description="CONTENEDOR, BL, BOOKING, MAWB, HAWB…")
    referencia: str
    via_transporte: Via
    nombre: str | None = Field(description="Nombre de la nave, si la fuente lo dio.")
    imo: int | None
    eta_fuente: dt.datetime | None
    ata_fuente: dt.datetime | None
    posicion: Posicion | None
    velocidad_nudos: Decimal | None
    ultima_consulta_exitosa: dt.datetime | None = Field(
        description="Cuándo respondió bien la fuente por última vez (RNF-12)."
    )
    guia_madre: str | None = Field(description="Solo guías hijas por TICA (`US-49`).")
    manifiesto_aduana: str | None
    activo: bool = Field(description="`false` cuando ya arribó y no se consulta más.")


class Arribos(BaseModel):
    """Los tres orígenes del arribo que RN-05 exige distinguir."""

    confirmado: dt.datetime | None = Field(description="Registrado a mano (`US-14`).")
    fuente: dt.datetime | None = Field(description="Reportado por ShipsGo o TICA.")
    inferido: dt.datetime | None = Field(description="Deducido por la geocerca.")


class Calculo(BaseModel):
    """El desglose de RN-01 que exige RF-05: de dónde sale la fecha proyectada."""

    origen: str | None = Field(
        description=(
            "De qué fecha partió, por la precedencia de RN-14 (`ATA_CONFIRMADA`, "
            "`ETA_FUENTE`, `ETA_DECLARADA`…). Nulo si no hubo fecha base."
        )
    )
    eta_utilizada: dt.datetime | None
    lead_time_dias: int = Field(description="La instantánea usada en el último recálculo.")
    lead_time_maestro_dias: int = Field(
        description=(
            "El vigente en el maestro. Si difiere del anterior, el pedido todavía "
            "no se recalculó con el valor nuevo: ninguno de los dos está mal."
        )
    )
    ajuste_manual_dias: int
    fecha_proyectada: dt.date | None
    fecha_comprometida: dt.date = Field(
        description="Llegada a Gutis según Compras: `Fecha Entrega`, columna R (`US-53`)."
    )
    ventana_aduanal_dias: int | None = Field(
        description=(
            "Días entre la llegada a Costa Rica (la fecha base) y la comprometida: "
            "lo que el plan de Compras le deja al proceso aduanal. Se lee junto a "
            "`lead_time_dias`, que es lo que ese proceso suele tardar en el destino. "
            "Nulo si no hay fecha base."
        )
    )
    margen_dias: int | None = Field(
        description="Comprometida menos proyectada. Negativo es atraso."
    )
    umbral_riesgo_dias: int = Field(description="Ventana de `EN_RIESGO` (RN-08).")
    desglose: str = Field(
        description="La operación que produjo la fecha guardada, o por qué no hay fecha."
    )
    al_dia: bool = Field(
        description=(
            "Si proyectar hoy con los mismos insumos da la fecha guardada. "
            "`false` significa que un insumo cambió y falta el recálculo."
        )
    )
    desglose_actual: str | None = Field(
        description="Lo que darían los insumos de hoy. Solo cuando `al_dia` es `false`."
    )
    fecha_ultimo_recalculo: dt.datetime | None


class Cierre(BaseModel):
    fecha_recepcion_planta: dt.datetime | None
    cantidad_recibida: Decimal | None
    motivo_cierre: str | None


class PedidoDetalle(PedidoResumen):
    """Todo lo que la vista de `US-20` necesita en una sola respuesta."""

    cantidad_pedida: Decimal
    unidad_medida: str
    incoterm: str | None
    temperatura: str | None
    tipo_proveedor: str | None
    fabricante: str | None
    pais_origen: PaisRef | None
    rastreo: Rastreo | None = Field(
        description="Nulo cuando el pedido no es rastreable: se ofrece asociar uno."
    )
    arribos: Arribos
    calculo: Calculo
    cierre: Cierre
    fecha_ultima_carga: dt.datetime | None


class DesembarcoEntrada(BaseModel):
    """`US-14`: la llegada real de la carga, con su motivo."""

    ata: dt.datetime = Field(
        description="Fecha y hora de llegada **con zona horaria** (`2026-09-30T08:15:00-06:00`)."
    )
    motivo: str = Field(description="Obligatorio (RF-14): por qué se confirma a mano.")
    confirmar: bool = Field(
        default=False, description="Obligatorio para reemplazar una llegada ya confirmada."
    )


class RecepcionEntrada(BaseModel):
    """`US-18`: la entrada a planta, o la recepción parcial de un cierre forzado."""

    fecha: dt.datetime = Field(description="Fecha y hora de recepción, con zona horaria.")
    cantidad: Decimal = Field(ge=0, description="Cantidad recibida, en la unidad del pedido.")
    motivo: str = Field(description="Obligatorio (RF-14).")


class RecepcionIncompleta(BaseModel):
    """El cuerpo del 409 cuando lo recibido no llega al mínimo de RN-10."""

    detail: str
    cantidad_pedida: Decimal
    cantidad_recibida: Decimal
    minimo_conforme: Decimal
    ofrece_cierre_forzado: bool = True


class PasoAduanalEntrada(BaseModel):
    motivo: str = Field(description="Obligatorio (RF-14).")


class ConfirmacionDesembarco(BaseModel):
    """El cuerpo del 409 cuando ya había una llegada confirmada."""

    detail: str
    ata_confirmada_actual: dt.datetime
    requiere_confirmacion: bool = True


class AsientoBitacora(BaseModel):
    """Una intervención manual sobre el pedido (`US-15`, RF-14)."""

    fecha_hora: dt.datetime
    usuario: str = Field(description="Cuenta que la hizo. `compras@gutis.com` es compartida.")
    nombre_usuario: str
    rol: str
    tipo: str = Field(description="CONFIRMACION_DESEMBARCO, AJUSTE_MANUAL, …")
    campo: str | None
    valor_anterior: str | None
    valor_nuevo: str | None
    motivo: str


__all__ = [
    "Arribos",
    "AsientoBitacora",
    "ConfirmacionDesembarco",
    "DesembarcoEntrada",
    "PasoAduanalEntrada",
    "RecepcionEntrada",
    "RecepcionIncompleta",
    "Calculo",
    "Cierre",
    "Cumplimiento",
    "CumplimientoFiltro",
    "EtapaFiltro",
    "SIN_PROYECCION",
    "DestinoRef",
    "EstadoCalculado",
    "EtapaViaje",
    "MaterialRef",
    "PaginaPedidos",
    "PaisRef",
    "PedidoDetalle",
    "PedidoResumen",
    "Posicion",
    "ProveedorRef",
    "Rastreo",
    "Via",
]
