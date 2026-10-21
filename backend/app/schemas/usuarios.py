"""Contratos de `/auth` y `/usuarios` — `US-42`."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Rol = Literal["COMPRAS", "LOGISTICA", "PLANIFICACION", "ADMINISTRADOR", "PLANTA"]


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


class UsuarioAdministrado(UsuarioPublico):
    """Lo que ve el Administrador en «Usuarios» (`US-62`): además, si está bloqueada."""

    bloqueado_hasta: dt.datetime | None = Field(
        description=(
            "Hasta cuándo la bloquean los intentos fallidos. Puede estar en el pasado: "
            "el bloqueo ya venció y la cuenta entra."
        )
    )


class SesionIniciada(BaseModel):
    token: str = Field(description="Enviar como `Authorization: Bearer <token>`.")
    tipo: Literal["bearer"] = "bearer"
    recordada: bool
    usuario: UsuarioPublico


class CambioContrasena(BaseModel):
    """`POST /auth/contrasena` (`US-61`): el propio usuario, con la vigente."""

    contrasena_actual: str = Field(min_length=1, max_length=200)
    contrasena_nueva: str = Field(max_length=200)


class ContrasenaCambiada(BaseModel):
    sesiones_cerradas: int = Field(
        description=(
            "Cuántas **otras** sesiones de la cuenta se cerraron. La del cambio sigue abierta; "
            "en la cuenta compartida de Compras, las demás personas vuelven a entrar."
        )
    )


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
    "CambioContrasena",
    "ContrasenaCambiada",
    "Credenciales",
    "NuevaContrasena",
    "Rol",
    "SesionIniciada",
    "UsuarioAdministrado",
    "UsuarioCambios",
    "UsuarioNuevo",
    "UsuarioPublico",
]
