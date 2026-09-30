"""Quién hace la petición y qué puede hacer — `US-42` / RNF-05.

`usuario_actual` protege un endpoint: exige `Authorization: Bearer <token>` y
devuelve el usuario de la sesión. `requiere_rol` restringe además por rol.

La autoría de la auditoría (RF-14) sale de aquí, de la sesión, y no de un
selector en la pantalla: es lo que revierte la decisión B5.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import autenticacion

_bearer = HTTPBearer(auto_error=False, description="El token que devuelve `/auth/login`.")

#: Los roles de RNF-05, con nombre para no repetir cadenas en cada router.
COMPRAS = "COMPRAS"
LOGISTICA = "LOGISTICA"
PLANIFICACION = "PLANIFICACION"
ADMINISTRADOR = "ADMINISTRADOR"


@dataclass(frozen=True, slots=True)
class Autenticado:
    usuario: Usuario
    sesion: Sesion


def _no_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inexistente o vencida. Inicie sesión de nuevo.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def usuario_actual(
    db: Annotated[AsyncSession, Depends(get_db)],
    credencial: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Autenticado:
    if credencial is None:
        raise _no_autenticado()
    try:
        sesion, usuario = await autenticacion.validar_token(db, credencial.credentials)
    except autenticacion.SesionInvalida:
        # Se confirma igual: una sesión vencida queda marcada como cerrada.
        await db.commit()
        raise _no_autenticado() from None
    # El último uso se guarda ya: un GET no hace commit, y sin esto la sesión
    # vencería por inactividad aunque se esté usando.
    await db.commit()
    return Autenticado(usuario=usuario, sesion=sesion)


def requiere_rol(*roles: str) -> Callable[..., Awaitable[Autenticado]]:
    """Dependencia que deja pasar solo a esos roles. El Administrador, siempre."""
    permitidos = {*roles, ADMINISTRADOR}

    async def _verificar(
        quien: Annotated[Autenticado, Depends(usuario_actual)],
    ) -> Autenticado:
        if quien.usuario.rol not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El rol {quien.usuario.rol} no puede hacer esta operación.",
            )
        return quien

    return _verificar


__all__ = [
    "ADMINISTRADOR",
    "COMPRAS",
    "LOGISTICA",
    "PLANIFICACION",
    "Autenticado",
    "requiere_rol",
    "usuario_actual",
]
