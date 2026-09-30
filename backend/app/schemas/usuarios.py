"""Contratos de `/auth` y `/usuarios` — `US-42`."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Rol = Literal["COMPRAS", "LOGISTICA", "PLANIFICACION", "ADMINISTRADOR"]


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)
    contrasena: str = Field(min_length=1, max_length=200)
    recordar: bool = Field(
        default=False, description="«Recordar sesión»: no cierra por inactividad."
    )


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario: str
    nombre_completo: str
    correo: str | None
    rol: Rol
    activo: bool
    ultimo_acceso: dt.datetime | None


class SesionIniciada(BaseModel):
    token: str = Field(description="Enviar como `Authorization: Bearer <token>`.")
    tipo: Literal["bearer"] = "bearer"
    recordada: bool
    usuario: UsuarioPublico


class UsuarioNuevo(BaseModel):
    usuario: str = Field(min_length=3, max_length=50)
    nombre_completo: str = Field(min_length=1, max_length=120)
    correo: str | None = Field(default=None, max_length=120)
    rol: Rol
    contrasena: str = Field(max_length=200)


class UsuarioCambios(BaseModel):
    nombre_completo: str | None = Field(default=None, min_length=1, max_length=120)
    correo: str | None = Field(default=None, max_length=120)
    rol: Rol | None = None
    activo: bool | None = Field(
        default=None, description="Desactivar cierra todas sus sesiones abiertas."
    )


class NuevaContrasena(BaseModel):
    contrasena: str = Field(max_length=200)


__all__ = [
    "Credenciales",
    "NuevaContrasena",
    "Rol",
    "SesionIniciada",
    "UsuarioCambios",
    "UsuarioNuevo",
    "UsuarioPublico",
]
