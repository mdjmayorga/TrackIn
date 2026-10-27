"""Contrato de `/api/v1/integraciones/sap` — los pedidos que envía SAP (`US-65`).

Es el mismo contrato de `docs/integraciones/sap/lote_pedidos.schema.json`
(`US-64`); `tests/test_integracion_sap.py` verifica que no se separen. Es
**estricto** a propósito: un `"10"` donde va un número o un campo que el contrato
no conoce se rechazan, en vez de interpretarse. Con una API que todavía no
existe, lo que no se rechaza el primer día se vuelve costumbre.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.cargas import Autor, CargaResumen, Incidencia

#: Máximo de pedidos por lote. Por encima, `413`: hay que partir el envío.
MAXIMO_PEDIDOS: int = 5000

_Texto = Annotated[str, Field(min_length=1)]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DatosLote(_Estricto):
    id: Annotated[_Texto, Field(max_length=64)]
    generado_en: AwareDatetime
    tipo: Literal["INCREMENTAL", "COMPLETO"]
    sistema: Annotated[str, Field(max_length=60)] | None = None


class PedidoSap(_Estricto):
    """Una línea de OC con su reparto. Ver `docs/integraciones/sap/README.md`."""

    # --- Obligatorios ---------------------------------------------------------
    oc_numero: Annotated[str, Field(pattern=r"^\d{1,10}$")]
    posicion_oc: Annotated[int, Field(ge=1, le=99999)]
    proveedor_codigo: Annotated[_Texto, Field(max_length=20)]
    proveedor_nombre: Annotated[_Texto, Field(max_length=200)]
    material_codigo: Annotated[_Texto, Field(max_length=40)]
    material_descripcion: Annotated[_Texto, Field(max_length=200)]
    cantidad: Annotated[float, Field(gt=0)]
    unidad_medida: Annotated[_Texto, Field(max_length=10)]
    fecha_entrega_pedido: dt.date

    # --- Opcionales que TrackIn usa -------------------------------------------
    destino_codigo: Literal["CRMOB", "CRLIO", "CRCAL", "MROC"] | None = None
    via_transporte: Literal["MARITIMO", "AEREO", "TERRESTRE"] | None = None
    pais_origen: Annotated[str, Field(max_length=60)] | None = None
    incoterm: Annotated[str, Field(max_length=60)] | None = None
    temperatura: Annotated[str, Field(max_length=40)] | None = None
    tipo_proveedor: Literal["LOCAL", "INTERNACIONAL"] | None = None
    fabricante: Annotated[str, Field(max_length=200)] | None = None
    eta_declarada: dt.date | None = None
    arribo_declarado: Literal["SI", "NO", "PENDIENTE", "N/A"] | None = None
    tipo_referencia: Literal["BL", "CONTENEDOR", "BOOKING", "MAWB", "HAWB"] | None = None
    numero_referencia: Annotated[str, Field(max_length=40)] | None = None
    transportista: Annotated[str, Field(max_length=120)] | None = None
    fecha_referencia: dt.date | None = None
    #: No se guarda: se buscan en él referencias escritas a mano (`US-52`).
    comentario: Annotated[str, Field(max_length=1000)] | None = None
    solicitud_pedido: Annotated[str, Field(max_length=20)] | None = None

    # --- Reservados: se aceptan y hoy no se usan -------------------------------
    fecha_entrega_solped: dt.date | None = None
    centro: Annotated[str, Field(max_length=10)] | None = None
    grupo_compras: Annotated[str, Field(max_length=10)] | None = None
    fecha_documento: dt.date | None = None
    indicador_borrado: bool | None = None
    entrega_final: bool | None = None
    cantidad_recibida: Annotated[float, Field(ge=0)] | None = None
    modificado_en: AwareDatetime | None = None


class LoteSap(_Estricto):
    lote: DatosLote
    pedidos: Annotated[list[PedidoSap], Field(min_length=1, max_length=MAXIMO_PEDIDOS)]


class InformeLote(BaseModel):
    """Lo que TrackIn responde a SAP: el informe de la carga."""

    id_carga: int
    lote_id: str
    estado: Literal["APLICADA"]
    recibidas: int
    insertadas: int
    actualizadas: int
    sin_cambios: int
    no_entraron: int
    entraron_sin_rastreo: int
    incidencias: list[Incidencia]


class EscuchaApagada(BaseModel):
    """El `503` mientras la escucha esté apagada."""

    detail: str
    escucha_habilitada: Literal[False] = False


class EstadoEscuchaOut(BaseModel):
    """El interruptor de la escucha (`US-66`)."""

    habilitada: bool
    cambiada_por: Autor | None = Field(description="Quién la cambió por última vez.")
    cambiada_en: dt.datetime | None
    clave_configurada: bool = Field(
        description="Si el servidor tiene `SAP_INTEGRACION_CLAVE`. Sin ella, SAP no puede "
        "enviar aunque la escucha esté encendida."
    )
    ultima_recepcion: CargaResumen | None = Field(
        description="El último lote recibido de SAP, o nulo si todavía no llegó ninguno."
    )


class CambioEscucha(BaseModel):
    model_config = ConfigDict(extra="forbid")

    habilitada: bool


__all__ = [
    "MAXIMO_PEDIDOS",
    "CambioEscucha",
    "EstadoEscuchaOut",
    "DatosLote",
    "EscuchaApagada",
    "InformeLote",
    "LoteSap",
    "PedidoSap",
]
