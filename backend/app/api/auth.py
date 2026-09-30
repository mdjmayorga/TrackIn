"""`/auth` — iniciar y cerrar sesión (`US-42`, RNF-05)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import get_db
from app.schemas.usuarios import Credenciales, SesionIniciada, UsuarioPublico
from app.services import autenticacion

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post(
    "/login",
    response_model=SesionIniciada,
    summary="Iniciar sesión",
    description=(
        "Devuelve un token de sesión. El error es siempre el mismo, falle el "
        "usuario, la contraseña o esté la cuenta bloqueada. Abrir una sesión no "
        "cierra las demás del mismo usuario (cuenta compartida de Compras)."
    ),
    responses={401: {"description": autenticacion.MENSAJE_CREDENCIALES}},
)
async def login(
    credenciales: Credenciales, db: Annotated[AsyncSession, Depends(get_db)]
) -> SesionIniciada:
    try:
        abierta = await autenticacion.iniciar_sesion(
            db, credenciales.usuario, credenciales.contrasena, recordar=credenciales.recordar
        )
    except autenticacion.CredencialesInvalidas as exc:
        # Se confirma igual: el intento fallido tiene que contar.
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from None
    await db.commit()
    return SesionIniciada(
        token=abierta.token,
        recordada=abierta.sesion.recordada,
        usuario=UsuarioPublico.model_validate(abierta.usuario),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar esta sesión",
    description="Cierra solo la sesión del token; las demás del usuario siguen abiertas.",
)
async def logout(
    quien: Annotated[Autenticado, Depends(usuario_actual)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await autenticacion.cerrar_sesion(db, quien.sesion)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/yo", response_model=UsuarioPublico, summary="Quién soy")
async def yo(quien: Annotated[Autenticado, Depends(usuario_actual)]) -> UsuarioPublico:
    return UsuarioPublico.model_validate(quien.usuario)


__all__ = ["router"]
