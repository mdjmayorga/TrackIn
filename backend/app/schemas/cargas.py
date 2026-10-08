"""Contrato de `/api/v1/cargas` — la subida del Excel del Z-tracking (`US-58`)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoCarga = Literal["APLICADA", "RECHAZADA"]
Consecuencia = Literal["no_entro", "entro_sin_rastreo"]


class Autor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usuario: str
    nombre_completo: str


class CargaResumen(BaseModel):
    """Una carga en el historial: quién, cuándo, qué archivo y los totales."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    archivo: str
    tamano_bytes: int
    realizada_en: dt.datetime
    estado: EstadoCarga
    motivo_rechazo: str | None = Field(description="Por qué se rechazó el archivo entero.")
    usuario: Autor
    recibidas: int = Field(description="Líneas del archivo, legibles o no.")
    insertadas: int
    actualizadas: int
    sin_cambios: int
    ausentes: int = Field(description="Estaban en TrackIn y no vinieron: quedan para revisión.")
    no_entraron: int
    entraron_sin_rastreo: int


class Incidencia(BaseModel):
    clave: str = Field(description="`OC-posición`, o `hoja!fila` si la fila no tenía OC.")
    motivo: str
    detalle: str
    consecuencia: Consecuencia


class Aviso(BaseModel):
    """Entró, pero conviene corregirlo en SAP (`US-52`, `US-54`)."""

    clave: str
    tipo: str
    detalle: str


class CargaDetalle(CargaResumen):
    """La carga con su informe completo: cada línea que no entró y por qué."""

    por_motivo: dict[str, int] = Field(
        default_factory=dict, description="Cuántas veces se repite cada problema, de mayor a menor."
    )
    incidencias: list[Incidencia] = Field(default_factory=list)
    avisos: list[Aviso] = Field(default_factory=list)


__all__ = ["Autor", "Aviso", "CargaDetalle", "CargaResumen", "Incidencia"]
