"""Contrato de `/api/v1/cargas` — la subida del Excel del Z-tracking (`US-58`)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoCarga = Literal["APLICADA", "RECHAZADA"]
OrigenCarga = Literal["EXCEL", "API_SAP"]
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
    origen: OrigenCarga = Field(description="EXCEL (subido por una persona) o API_SAP (`US-65`).")
    usuario: Autor | None = Field(description="Quién subió el Excel. Nulo en los lotes de SAP.")
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


class EstadoCargas(BaseModel):
    """¿Está cargado el Z-tracking de esta semana? (`US-23`, acuerdo del 22/10/2026)."""

    situacion: Literal["AL_DIA", "TOCA_CARGAR", "ATRASADA", "NUNCA"] = Field(
        description=(
            "`AL_DIA`: hay carga aplicada desde el lunes. `TOCA_CARGAR`: no la hay, pero no "
            "pasó el día límite. `ATRASADA`: ya pasó. `NUNCA`: nunca se cargó desde TrackIn."
        )
    )
    ultima: CargaResumen | None = Field(description="La última carga **aplicada**.")
    semana_desde: dt.date = Field(description="El lunes de la semana en curso, en Costa Rica.")
    dia_limite: int = Field(ge=1, le=7, description="Último día para cargar: 1 lunes … 7 domingo.")


__all__ = ["Autor", "Aviso", "CargaDetalle", "CargaResumen", "EstadoCargas", "Incidencia"]
