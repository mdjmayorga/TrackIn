"""Contrato de `/api/v1/shipsgo` — altas (`US-55`) y créditos (`US-57`) de ShipsGo."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

NivelCreditos = Literal["SIN_PAQUETE", "OK", "POR_VENCER", "BAJO", "AGOTADO", "VENCIDO"]


class PaqueteCreditosOut(BaseModel):
    cantidad: int
    saldo_arrastrado: int = Field(description="Lo que se sumó del paquete anterior.")
    comprado_en: dt.date
    vence_en: dt.date | None
    registrado_en: dt.datetime
    registrado_por: str


class EstadoCreditosOut(BaseModel):
    """El saldo del paquete vigente y el aviso que corresponde (`US-57`)."""

    nivel: NivelCreditos
    mensaje: str
    paquete: PaqueteCreditosOut | None
    disponible: int = Field(description="Lo comprado más lo arrastrado.")
    consumidos: int = Field(description="Altas que costaron desde que se registró el paquete.")
    saldo: int
    porcentaje_consumido: float | None
    dias_para_vencer: int | None
    recompra_minima: int | None = Field(
        description="Lo mínimo que hay que comprar para arrastrar el saldo (50 % del paquete)."
    )


class PaqueteNuevo(BaseModel):
    cantidad: int = Field(ge=1, le=100_000)
    comprado_en: dt.date
    vence_en: dt.date | None = Field(
        default=None, description="Nulo si no vence (los créditos de prueba no tienen fecha)."
    )
    altas_maximas_dia: int | None = Field(
        default=None, ge=1, le=1000, description="Sube el tope diario de altas en el mismo paso."
    )
    nota: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _vence_despues(self) -> PaqueteNuevo:
        if self.vence_en is not None and self.vence_en < self.comprado_en:
            raise ValueError("El vencimiento no puede ser anterior a la compra.")
        return self


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
    creditos: EstadoCreditosOut = Field(description="El saldo, para advertir antes de gastar.")


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
    aceptar_saldo: bool = Field(
        default=False,
        description=(
            "Acepta seguir aunque el saldo registrado no alcance o el paquete haya vencido "
            "(`US-57`). El saldo es el que lleva TrackIn: puede no coincidir con ShipsGo."
        ),
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


class SaldoInsuficiente(BaseModel):
    """El 409 cuando el saldo registrado no alcanza y no se aceptó (`US-57`)."""

    detail: str
    saldo: int
    nivel: NivelCreditos
    requiere_aceptar_saldo: bool = True


__all__ = [
    "AltasHechas",
    "AltasPendientes",
    "EstadoCreditosOut",
    "NivelCreditos",
    "PaqueteCreditosOut",
    "PaqueteNuevo",
    "SaldoInsuficiente",
    "LineaPendiente",
    "ReferenciaElegida",
    "ReferenciaPendiente",
    "ResultadoAlta",
    "SolicitudAltas",
    "TopeSuperado",
]
