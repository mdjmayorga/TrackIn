"""Contrato de `/api/v1/shipsgo/altas` — altas en ShipsGo desde TrackIn (`US-55`)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineaPendiente(BaseModel):
    id_pedido: int
    oc_numero: str
    posicion_oc: int


class ReferenciaPendiente(BaseModel):
    """Una referencia de pedidos activos que todavía no está en la cuenta de ShipsGo."""

    tipo: str = Field(description="BL, CONTENEDOR, BOOKING o MAWB.")
    numero: str
    via_transporte: str
    lineas: list[LineaPendiente] = Field(
        description="Las líneas que la comparten: ShipsGo cobra por embarque, no por línea."
    )
    cubierta: bool | None = Field(
        description=(
            "Solo MAWB: si el catálogo de aerolíneas de ShipsGo la cubre. `null` si no "
            "aplica o si el catálogo no se pudo leer."
        )
    )
    aerolinea: str | None
    ofrecible: bool = Field(description="Se puede dar de alta: todo salvo una MAWB sin cobertura.")


class AltasPendientes(BaseModel):
    pendientes: list[ReferenciaPendiente]
    creditos_necesarios: int = Field(description="Uno por referencia ofrecible.")
    altas_hoy: int = Field(description="Altas que ya costaron crédito hoy, en hora de Costa Rica.")
    altas_maximas_dia: int = Field(description="El tope diario, `altas_maximas_dia`.")


class ReferenciaElegida(BaseModel):
    tipo: str = Field(max_length=20)
    numero: str = Field(max_length=50)


class SolicitudAltas(BaseModel):
    referencias: list[ReferenciaElegida] = Field(min_length=1, max_length=200)
    creditos_confirmados: int = Field(
        ge=1,
        description=(
            "Quien autoriza repite cuántos créditos se van a gastar: uno por referencia. "
            "Si no coincide, no se da de alta nada."
        ),
    )
    superar_tope: bool = Field(
        default=False,
        description="Acepta pasar del tope diario `altas_maximas_dia` (la carga semanal lo pasa).",
    )


class ResultadoAlta(BaseModel):
    tipo: str
    numero: str
    registrado: bool
    motivo: str
    consumio_credito: bool


class AltasHechas(BaseModel):
    resultados: list[ResultadoAlta]
    creditos_consumidos: int = Field(
        description="Los que de verdad se gastaron: un embarque que ya existía sale gratis."
    )


class TopeSuperado(BaseModel):
    """El 409 cuando el bloque pasa del tope diario y no se aceptó."""

    detail: str
    altas_hoy: int
    altas_maximas_dia: int
    requiere_superar_tope: bool = True


__all__ = [
    "AltasHechas",
    "AltasPendientes",
    "LineaPendiente",
    "ReferenciaElegida",
    "ReferenciaPendiente",
    "ResultadoAlta",
    "SolicitudAltas",
    "TopeSuperado",
]
