"""`/destinos` — el maestro de destinos y sus lead times (`US-13`, RF-23, CU-06).

Escribe, así que confirma la transacción en cada petición que cambia algo. Un
cambio de lead time recalcula en la misma transacción los pedidos activos del
destino (`US-12`): o entran los dos, o ninguno.

Leerlo puede cualquier rol autenticado; mantenerlo, solo Logística y el
Administrador (`US-42`, RNF-05: «solo los autorizados mantienen maestros»).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import LOGISTICA, requiere_rol, usuario_actual
from app.db.session import get_db
from app.schemas.destinos import (
    ConfirmacionPendiente,
    Destino,
    DestinoActualizado,
    DestinoCambios,
    DestinoNuevo,
)
from app.services import destinos as servicio

router = APIRouter(prefix="/destinos", tags=["destinos"])
#: Quién puede dar de alta y editar el maestro.
mantenedor = requiere_rol(LOGISTICA)


def _salida(ficha: servicio.FichaDestino) -> dict[str, object]:
    d = ficha.destino
    return {
        "id": d.id,
        "codigo": d.codigo,
        "nombre": d.nombre,
        "pais": d.pais,
        "via_transporte": d.via_transporte,
        "latitud": ficha.latitud,
        "longitud": ficha.longitud,
        "radio_geocerca_km": d.radio_geocerca_km,
        "lead_time_dias": d.lead_time_dias,
        "activo": d.activo,
        "observacion": d.observacion,
        "pedidos_activos": ficha.pedidos_activos,
    }


async def _ficha(db: AsyncSession, id_destino: int) -> servicio.FichaDestino:
    ficha = await servicio.ficha(db, id_destino)
    if ficha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el destino {id_destino}.")
    return ficha


@router.get(
    "",
    response_model=list[Destino],
    summary="Listar destinos",
    dependencies=[Depends(usuario_actual)],
)
async def listar_destinos(
    db: Annotated[AsyncSession, Depends(get_db)],
    incluir_inactivos: Annotated[bool, Query()] = False,
) -> list[Destino]:
    fichas = await servicio.listar_destinos(db, incluir_inactivos=incluir_inactivos)
    return [Destino.model_validate(_salida(f)) for f in fichas]


@router.get(
    "/{id_destino}",
    response_model=Destino,
    summary="Detalle de un destino",
    responses={404: {"description": "No existe un destino con ese id."}},
    dependencies=[Depends(usuario_actual)],
)
async def detalle_destino(id_destino: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Destino:
    return Destino.model_validate(_salida(await _ficha(db, id_destino)))


@router.post(
    "",
    response_model=Destino,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta un destino",
    responses={409: {"description": "Código, o nombre en esa vía, ya existentes."}},
    dependencies=[Depends(mantenedor)],
)
async def crear_destino(
    datos: DestinoNuevo, db: Annotated[AsyncSession, Depends(get_db)]
) -> Destino:
    try:
        destino = await servicio.crear_destino(db, **datos.model_dump())
    except servicio.DestinoDuplicado as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    return Destino.model_validate(_salida(await _ficha(db, destino.id)))


@router.patch(
    "/{id_destino}",
    response_model=DestinoActualizado,
    summary="Editar un destino",
    description=(
        "Cambia solo lo que viene. Cambiar el lead time recalcula los pedidos "
        "activos del destino. Desactivar uno con pedidos activos responde 409 "
        "con cuántos son, y exige repetir con `confirmar: true`."
    ),
    responses={
        404: {"description": "No existe un destino con ese id."},
        409: {
            "model": ConfirmacionPendiente,
            "description": "Nombre duplicado, o desactivación sin confirmar.",
        },
    },
    dependencies=[Depends(mantenedor)],
)
async def actualizar_destino(
    id_destino: int, cambios: DestinoCambios, db: Annotated[AsyncSession, Depends(get_db)]
) -> DestinoActualizado | JSONResponse:
    enviados = cambios.model_fields_set
    argumentos: dict[str, object] = {"confirmar": cambios.confirmar}
    if "nombre" in enviados and cambios.nombre is not None:
        argumentos["nombre"] = cambios.nombre
    if "lead_time_dias" in enviados and cambios.lead_time_dias is not None:
        argumentos["lead_time_dias"] = cambios.lead_time_dias
    if "radio_geocerca_km" in enviados:
        argumentos["radio_geocerca_km"] = cambios.radio_geocerca_km
    if "observacion" in enviados:
        argumentos["observacion"] = cambios.observacion
    if "activo" in enviados and cambios.activo is not None:
        argumentos["activo"] = cambios.activo

    try:
        _, cambio = await servicio.actualizar_destino(db, id_destino, **argumentos)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except servicio.DestinoDuplicado as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except servicio.ConfirmacionRequerida as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ConfirmacionPendiente(
                detail=str(exc), pedidos_activos=exc.pedidos_activos
            ).model_dump(),
        )
    await db.commit()

    salida = _salida(await _ficha(db, id_destino))
    resumen = cambio.recalculo if cambio is not None else None
    salida["recalculo"] = resumen.texto() if resumen is not None else None
    return DestinoActualizado.model_validate(salida)


__all__ = ["router"]
