"""`/usuarios` — cuentas y roles, solo para el Administrador (`US-42`, RNF-05).

Los usuarios **no se borran, se desactivan**: la auditoría referencia a cada
uno. Desactivar o reiniciar la contraseña cierra sus sesiones abiertas.

«¿Olvidó su contraseña?» no tiene flujo por correo —no hay infraestructura
para eso—: la reinicia el Administrador con `POST /usuarios/{id}/contrasena`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import ADMINISTRADOR, Autenticado, requiere_rol
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuarios import NuevaContrasena, UsuarioCambios, UsuarioNuevo, UsuarioPublico
from app.services import autenticacion

solo_administrador = requiere_rol(ADMINISTRADOR)
router = APIRouter(prefix="/usuarios", tags=["usuarios"])


async def _usuario(db: AsyncSession, id_usuario: int) -> Usuario:
    usuario = await db.get(Usuario, id_usuario)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el usuario {id_usuario}.")
    return usuario


@router.get("", response_model=list[UsuarioPublico], summary="Listar usuarios")
async def listar_usuarios(
    _: Annotated[Autenticado, Depends(solo_administrador)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UsuarioPublico]:
    usuarios = await db.scalars(select(Usuario).order_by(Usuario.usuario))
    return [UsuarioPublico.model_validate(u) for u in usuarios]


@router.post(
    "",
    response_model=UsuarioPublico,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario",
    responses={409: {"description": "Ya existe ese usuario o ese correo."}},
)
async def crear_usuario(
    datos: UsuarioNuevo,
    _: Annotated[Autenticado, Depends(solo_administrador)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioPublico:
    nombre = datos.usuario.strip().lower()
    if await db.scalar(select(Usuario).where(func.lower(Usuario.usuario) == nombre)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe el usuario {nombre}.")
    if datos.correo and await db.scalar(
        select(Usuario).where(func.lower(Usuario.correo) == datos.correo.strip().lower())
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe una cuenta con {datos.correo}.")
    try:
        hash_contrasena = autenticacion.hashear(datos.contrasena)
    except autenticacion.ContrasenaDebil as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    usuario = Usuario(
        usuario=nombre,
        nombre_completo=datos.nombre_completo.strip(),
        correo=datos.correo.strip().lower() if datos.correo else None,
        rol=datos.rol,
        hash_contrasena=hash_contrasena,
    )
    db.add(usuario)
    await db.commit()
    return UsuarioPublico.model_validate(usuario)


@router.patch(
    "/{id_usuario}",
    response_model=UsuarioPublico,
    summary="Cambiar nombre, correo, rol o estado",
    description="Un Administrador no puede quitarse el rol ni desactivarse a sí mismo.",
)
async def actualizar_usuario(
    id_usuario: int,
    cambios: UsuarioCambios,
    quien: Annotated[Autenticado, Depends(solo_administrador)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioPublico:
    usuario = await _usuario(db, id_usuario)
    enviados = cambios.model_fields_set
    if usuario.id == quien.usuario.id and (
        cambios.activo is False or (cambios.rol is not None and cambios.rol != ADMINISTRADOR)
    ):
        # Sin esto, el único Administrador podría dejar el sistema sin nadie
        # que administre cuentas.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Un Administrador no puede desactivarse ni quitarse el rol a sí mismo.",
        )
    if "nombre_completo" in enviados and cambios.nombre_completo is not None:
        usuario.nombre_completo = cambios.nombre_completo.strip()
    if "correo" in enviados:
        usuario.correo = cambios.correo.strip().lower() if cambios.correo else None
    if cambios.rol is not None:
        usuario.rol = cambios.rol
    if cambios.activo is not None:
        usuario.activo = cambios.activo
        if not cambios.activo:
            await autenticacion.cerrar_sesiones_de(db, usuario.id)
    await db.commit()
    return UsuarioPublico.model_validate(usuario)


@router.post(
    "/{id_usuario}/contrasena",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reiniciar la contraseña",
    description=(
        "El flujo de «¿Olvidó su contraseña?». Desbloquea la cuenta y cierra sus "
        "sesiones: quien tenía la contraseña vieja deja de estar dentro."
    ),
)
async def reiniciar_contrasena(
    id_usuario: int,
    datos: NuevaContrasena,
    _: Annotated[Autenticado, Depends(solo_administrador)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    usuario = await _usuario(db, id_usuario)
    try:
        usuario.hash_contrasena = autenticacion.hashear(datos.contrasena)
    except autenticacion.ContrasenaDebil as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    await autenticacion.cerrar_sesiones_de(db, usuario.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
