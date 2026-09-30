"""Contratos de `/destinos` — el maestro de destinos (`US-13`, RF-23, CU-06)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.pedidos import Via
from app.services.destinos import LeadTimeInvalido, validar_lead_time


def _lead_time(valor: Any) -> int:
    """El mismo mensaje que da el servicio: dice qué formato se esperaba."""
    try:
        return validar_lead_time(valor)
    except LeadTimeInvalido as exc:
        raise ValueError(str(exc)) from exc


class Destino(BaseModel):
    id: int
    codigo: str = Field(description="UN/LOCODE del puerto u OACI del aeropuerto.")
    nombre: str
    pais: str
    via_transporte: Via
    latitud: float
    longitud: float
    radio_geocerca_km: int | None = Field(
        description="Radio propio; nulo usa el parámetro general `radio_geocerca_km`."
    )
    lead_time_dias: int = Field(description="Días del arribo a la disponibilidad (RN-01).")
    activo: bool
    observacion: str | None
    pedidos_activos: int = Field(description="Pedidos no cerrados que van a este destino.")


class DestinoNuevo(BaseModel):
    codigo: str = Field(min_length=3, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    nombre: str = Field(min_length=1, max_length=80)
    pais: str = Field(pattern=r"^[A-Za-z]{2}$", description="ISO 3166-1 alfa-2.")
    via_transporte: Via
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    lead_time_dias: int = Field(description="Días enteros, cero o más.")
    radio_geocerca_km: int | None = Field(default=None, gt=0)
    observacion: str | None = None

    _validar_lead_time = field_validator("lead_time_dias", mode="before")(_lead_time)


class DestinoCambios(BaseModel):
    """Solo lo que viene se cambia. El código y la vía no se editan."""

    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    lead_time_dias: int | None = Field(
        default=None, description="Cambiarlo recalcula los pedidos activos del destino."
    )
    radio_geocerca_km: int | None = Field(default=None, gt=0)
    observacion: str | None = None
    activo: bool | None = None
    confirmar: bool = Field(
        default=False,
        description="Obligatorio para desactivar un destino con pedidos activos.",
    )

    @field_validator("lead_time_dias", mode="before")
    @classmethod
    def _validar_lead_time(cls, valor: Any) -> Any:
        return None if valor is None else _lead_time(valor)


class DestinoActualizado(Destino):
    recalculo: str | None = Field(
        description="Qué movió el cambio de lead time en los pedidos, si lo hubo."
    )


class ConfirmacionPendiente(BaseModel):
    """El cuerpo del 409 cuando desactivar exige confirmar."""

    detail: str
    pedidos_activos: int
    requiere_confirmacion: bool = True


__all__ = [
    "ConfirmacionPendiente",
    "Destino",
    "DestinoActualizado",
    "DestinoCambios",
    "DestinoNuevo",
]
