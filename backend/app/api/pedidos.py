"""`/pedidos` — listado y detalle por API REST (`US-16`, RF-04 y RF-05).

Lee el estado ya calculado por el worker; ninguna petición llega a una fuente
externa (RNF-03). Los recursos se identifican por la clave sustituta, no por
OC y posición: `/pedidos/1042` es una URL, `/pedidos/4500001234/10` acoplaría
la ruta a SAP (`data-model.md` §1.2).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import usuario_actual
from app.db.session import get_db
from app.schemas.pedidos import (
    CumplimientoFiltro,
    EstadoCalculado,
    EtapaFiltro,
    PaginaPedidos,
    PedidoDetalle,
    Via,
)
from app.services import consulta_pedidos
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


__all__ = ["router"]
