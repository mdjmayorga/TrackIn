"""`/pedidos` — listado y detalle por API REST (`US-16`, RF-04 y RF-05).

Lee el estado ya calculado por el worker; ninguna petición llega a una fuente
externa (RNF-03). Los recursos se identifican por la clave sustituta, no por
OC y posición: `/pedidos/1042` es una URL, `/pedidos/4500001234/10` acoplaría
la ruta a SAP (`data-model.md` §1.2).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import LOGISTICA, Autenticado, requiere_rol, usuario_actual
from app.db.session import get_db
from app.models.pedido_transito import PedidoTransito
from app.schemas.pedidos import (
    AsientoBitacora,
    ConfirmacionDesembarco,
    CumplimientoFiltro,
    DesembarcoEntrada,
    EstadoCalculado,
    EtapaFiltro,
    PaginaPedidos,
    PasoAduanalEntrada,
    PedidoDetalle,
    Via,
)
from app.services import auditoria, consulta_pedidos, intervenciones
from app.services.consulta_pedidos import ORDEN_POR_OMISION, PATRON_ORDEN, Filtros

# Cualquier rol autenticado consulta pedidos (`US-42`).
router = APIRouter(prefix="/pedidos", tags=["pedidos"], dependencies=[Depends(usuario_actual)])

#: RNF-01 fija 200 pedidos activos como volumen de referencia: una página cabe.
LIMITE_MAXIMO = 200


@router.get(
    "",
    response_model=PaginaPedidos,
    summary="Listar pedidos en tránsito",
    description=(
        "Los pedidos con su estado calculado, filtrados, ordenados y paginados. "
        "Sin filtro de `estado` devuelve solo los activos; los cerrados y "
        "cancelados aparecen al pedir ese estado (`wireframes.md` §1.11). "
        "Los filtros de lista se repiten: `?via=AEREO&via=MARITIMO`."
    ),
)
async def listar_pedidos(
    db: Annotated[AsyncSession, Depends(get_db)],
    oc: Annotated[str | None, Query(max_length=20, description="Prefijo del número de OC.")] = None,
    proveedor: Annotated[list[int] | None, Query(description="Id de proveedor.")] = None,
    material: Annotated[list[int] | None, Query(description="Id de material.")] = None,
    via: Annotated[list[Via] | None, Query()] = None,
    estado: Annotated[
        list[EstadoCalculado] | None, Query(description="El estado que pinta el semáforo.")
    ] = None,
    destino: Annotated[list[int] | None, Query(description="Id de destino.")] = None,
    posicion: Annotated[list[int] | None, Query(description="Posición de la OC.")] = None,
    etapa: Annotated[
        list[EtapaFiltro] | None,
        Query(description="Etapa del viaje; `CERRADO` y `CANCELADO` traen los terminales."),
    ] = None,
    cumplimiento: Annotated[
        list[CumplimientoFiltro] | None,
        Query(description="`SIN_PROYECCION` es el guion de la grilla: sin fecha proyectada."),
    ] = None,
    buscar_material: Annotated[
        str | None,
        Query(max_length=60, description="Texto en el código o la descripción del material."),
    ] = None,
    orden: Annotated[
        str,
        Query(
            pattern=PATRON_ORDEN,
            description="Columna por la que ordenar; con `-` delante, descendente.",
        ),
    ] = ORDEN_POR_OMISION,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = 50,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> PaginaPedidos:
    filtros = Filtros(
        oc=oc,
        proveedores=proveedor or (),
        materiales=material or (),
        vias=via or (),
        estados=estado or (),
        destinos=destino or (),
        posiciones=posicion or (),
        etapas=etapa or (),
        cumplimientos=cumplimiento or (),
        material_texto=buscar_material,
    )
    total, items = await consulta_pedidos.listar(
        db, filtros, orden=orden, limite=limite, desplazamiento=desplazamiento
    )
    return PaginaPedidos(total=total, limite=limite, desplazamiento=desplazamiento, items=items)


@router.get(
    "/{id_pedido}",
    response_model=PedidoDetalle,
    summary="Detalle de un pedido",
    description=(
        "Datos maestros, rastreo, última posición, los tres arribos de RN-05 y "
        "el desglose del cálculo de la fecha proyectada (RF-05)."
    ),
    responses={404: {"description": "No existe un pedido con ese id."}},
)
async def detalle_pedido(
    id_pedido: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> PedidoDetalle:
    pedido = await consulta_pedidos.detalle(db, id_pedido)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el pedido {id_pedido}.",
        )
    return pedido


@router.get(
    "/{id_pedido}/bitacora",
    response_model=list[AsientoBitacora],
    summary="Bitácora de intervenciones de un pedido",
    description=(
        "Las intervenciones manuales sobre el pedido, de la más antigua a la más "
        "reciente (RF-14). Es de solo lectura: la base rechaza editar o borrar "
        "un registro."
    ),
    responses={404: {"description": "No existe un pedido con ese id."}},
)
async def bitacora_pedido(
    id_pedido: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[AsientoBitacora]:
    if await db.get(PedidoTransito, id_pedido) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el pedido {id_pedido}.",
        )
    return [
        AsientoBitacora(
            fecha_hora=a.fila.fecha_hora,
            usuario=a.usuario,
            nombre_usuario=a.nombre_usuario,
            rol=a.rol,
            tipo=a.fila.tipo_intervencion,
            campo=a.fila.campo_afectado,
            valor_anterior=a.fila.valor_anterior,
            valor_nuevo=a.fila.valor_nuevo,
            motivo=a.fila.motivo,
        )
        for a in await auditoria.bitacora(db, id_pedido)
    ]


#: Quién confirma desembarcos y pasa a aduana: Logística (y el Administrador).
logistica = requiere_rol(LOGISTICA)


async def _detalle_tras_intervenir(db: AsyncSession, id_pedido: int) -> PedidoDetalle:
    await db.commit()
    detalle = await consulta_pedidos.detalle(db, id_pedido)
    assert detalle is not None
    return detalle


def _error_de_intervencion(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, intervenciones.IntervencionRechazada):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    # Motivo ausente o fecha inválida: es el dato que se envió.
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post(
    "/{id_pedido}/desembarco",
    response_model=PedidoDetalle,
    summary="Confirmar el desembarco (US-14)",
    description=(
        "Registra la llegada real con su motivo y deja el pedido «En destino». La "
        "llegada confirmada manda sobre la ETA de la fuente (RN-14); se recalcula y "
        "se audita. Una fecha futura se rechaza. Si ya había una llegada confirmada, "
        "responde 409 con la actual y exige repetir con `confirmar: true`."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {"model": ConfirmacionDesembarco, "description": "Ya confirmado, o pedido cerrado."},
    },
)
async def confirmar_desembarco(
    id_pedido: int,
    datos: DesembarcoEntrada,
    quien: Annotated[Autenticado, Depends(logistica)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle | JSONResponse:
    try:
        await intervenciones.confirmar_desembarco(
            db,
            id_pedido,
            ata=datos.ata,
            motivo=datos.motivo,
            id_usuario=quien.usuario.id,
            confirmar=datos.confirmar,
        )
    except intervenciones.ConfirmacionRequerida as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ConfirmacionDesembarco(
                detail=str(exc), ata_confirmada_actual=exc.valor_actual
            ).model_dump(mode="json"),
        )
    except (
        LookupError,
        intervenciones.IntervencionRechazada,
        intervenciones.FechaInvalida,
        auditoria.IntervencionInvalida,
    ) as exc:
        raise _error_de_intervencion(exc) from exc
    return await _detalle_tras_intervenir(db, id_pedido)


@router.post(
    "/{id_pedido}/paso-aduanal",
    response_model=PedidoDetalle,
    summary="Pasar a proceso aduanal (US-14)",
    description=(
        "El acto humano que autoriza pasar de «En destino» a «En proceso aduanal» "
        "(decisión del 04/09). Exige que el arribo se conozca: confirmado a mano o "
        "por el hito de la fuente."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {"description": "No llegó, ya pasó, o está cerrado."},
    },
)
async def pasar_a_aduanal(
    id_pedido: int,
    datos: PasoAduanalEntrada,
    quien: Annotated[Autenticado, Depends(logistica)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle:
    try:
        await intervenciones.pasar_a_aduanal(
            db, id_pedido, motivo=datos.motivo, id_usuario=quien.usuario.id
        )
    except (
        LookupError,
        intervenciones.IntervencionRechazada,
        auditoria.IntervencionInvalida,
    ) as exc:
        raise _error_de_intervencion(exc) from exc
    return await _detalle_tras_intervenir(db, id_pedido)


__all__ = ["router"]
