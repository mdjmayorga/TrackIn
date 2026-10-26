"""`/api/v1/shipsgo/altas` — dar de alta embarques en ShipsGo desde TrackIn (`US-55`).

Lo autorizan Compras y el Administrador (reunión con Compras del 29/09/2026). La
lista de pendientes es gratis: listar la cuenta y el catálogo de aerolíneas no
consume crédito. **El alta sí cuesta**, y por eso pide confirmar cuántos créditos
se gastan y advierte antes de pasar el tope diario.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import COMPRAS, Autenticado, requiere_rol
from app.core.config import settings
from app.db.session import get_db
from app.schemas.shipsgo import (
    AltasHechas,
    AltasPendientes,
    LineaPendiente,
    ReferenciaPendiente,
    ResultadoAlta,
    SolicitudAltas,
    TopeSuperado,
)
from app.services import planificador
from app.services.rastreo import altas, shipsgo_aerolineas, transporte_http
from app.services.rastreo.indice_shipsgo import clave_referencia, indice_shipsgo
from app.services.rastreo.shipsgo_aerolineas import CatalogoAerolineas
from app.services.rastreo.shipsgo_cliente import ClienteShipsGo, ErrorShipsGo

compras = requiere_rol(COMPRAS)
router = APIRouter(prefix="/shipsgo", tags=["shipsgo"])


async def cliente_shipsgo() -> AsyncIterator[ClienteShipsGo]:
    """El cliente real; sin token no hay a quién preguntar, y se dice."""
    if not settings.SHIPSGO_API_TOKEN:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ShipsGo no está configurado en el servidor (falta SHIPSGO_API_TOKEN).",
        )
    async with transporte_http.crear_cliente_http() as http:
        yield transporte_http.crear_cliente_shipsgo(http, settings.SHIPSGO_API_TOKEN)


async def _leer_cuenta(
    cliente: ClienteShipsGo,
) -> tuple[dict[str, tuple[int, bool]], CatalogoAerolineas | None]:
    """El índice de la cuenta y el catálogo, los dos gratis.

    Sin el índice no se sabe qué está pendiente: se responde 503. Sin el catálogo
    se sigue —`registro_embarque` no niega un alta por no haber podido leerlo—.
    """
    try:
        indice = await indice_shipsgo(cliente)
    except ErrorShipsGo as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"No se pudo leer la cuenta de ShipsGo: {exc}",
        ) from None
    try:
        catalogo: CatalogoAerolineas | None = await shipsgo_aerolineas.cargar(cliente)
    except ErrorShipsGo:
        catalogo = None
    return indice, catalogo


def _pendiente(p: altas.Pendiente) -> ReferenciaPendiente:
    return ReferenciaPendiente(
        tipo=p.tipo,
        numero=p.numero,
        via_transporte=p.via,
        lineas=[
            LineaPendiente(
                id_pedido=linea.id_pedido,
                oc_numero=linea.oc_numero,
                posicion_oc=linea.posicion_oc,
            )
            for linea in p.lineas
        ],
        cubierta=p.cubierta,
        aerolinea=p.aerolinea,
        ofrecible=p.ofrecible,
    )


@router.get(
    "/altas/pendientes",
    response_model=AltasPendientes,
    summary="Referencias que todavía no están en ShipsGo",
    description=(
        "Las de pedidos activos, agrupadas por referencia: ShipsGo cobra por embarque. "
        "**No consume crédito**: lista la cuenta y el catálogo de aerolíneas."
    ),
    responses={503: {"description": "ShipsGo sin configurar o sin responder."}},
)
async def listar_pendientes(
    _: Annotated[Autenticado, Depends(compras)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cliente: Annotated[ClienteShipsGo, Depends(cliente_shipsgo)],
) -> AltasPendientes:
    indice, catalogo = await _leer_cuenta(cliente)
    lista = await altas.pendientes(db, indice, catalogo)
    politica = await planificador.politica_vigente(db)
    return AltasPendientes(
        pendientes=[_pendiente(p) for p in lista],
        creditos_necesarios=sum(1 for p in lista if p.ofrecible),
        altas_hoy=await planificador.altas_del_dia(db),
        altas_maximas_dia=politica.altas_maximas_dia,
    )


@router.post(
    "/altas",
    response_model=AltasHechas,
    summary="Dar de alta referencias en ShipsGo — **cuesta un crédito cada una**",
    description=(
        "Solo referencias pendientes y ofrecibles. `creditos_confirmados` tiene que ser "
        "igual al número de referencias, y pasar el tope diario exige `superar_tope`."
    ),
    responses={
        409: {"model": TopeSuperado, "description": "Pasa del tope diario y no se aceptó."},
        422: {"description": "Una referencia no está pendiente, o el costo no se confirmó."},
        503: {"description": "ShipsGo sin configurar o sin responder."},
    },
)
async def dar_de_alta(
    solicitud: SolicitudAltas,
    quien: Annotated[Autenticado, Depends(compras)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cliente: Annotated[ClienteShipsGo, Depends(cliente_shipsgo)],
) -> AltasHechas | JSONResponse:
    indice, catalogo = await _leer_cuenta(cliente)
    por_clave = {
        clave_referencia(p.numero): p for p in await altas.pendientes(db, indice, catalogo)
    }

    elegidas: list[altas.Pendiente] = []
    for ref in solicitud.referencias:
        pendiente = por_clave.get(clave_referencia(ref.numero))
        if pendiente is None or not pendiente.ofrecible:
            # No se paga por algo que ya está en la cuenta, que ningún pedido usa o
            # que la aerolínea no cubre.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{ref.numero} no está pendiente de alta: no se dio de alta nada.",
            )
        if pendiente not in elegidas:
            elegidas.append(pendiente)

    if solicitud.creditos_confirmados != len(elegidas):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Confirme el costo: son {len(elegidas)} créditos, uno por referencia.",
        )

    hoy = await planificador.altas_del_dia(db)
    tope = (await planificador.politica_vigente(db)).altas_maximas_dia
    if hoy + len(elegidas) > tope and not solicitud.superar_tope:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=TopeSuperado(
                detail=(
                    f"Con estas {len(elegidas)} altas serían {hoy + len(elegidas)} hoy, más "
                    f"que el tope diario de {tope}. Confirme que quiere superarlo."
                ),
                altas_hoy=hoy,
                altas_maximas_dia=tope,
            ).model_dump(),
        )

    hechos = await altas.dar_de_alta(
        db, cliente, elegidas, id_usuario=quien.usuario.id, catalogo=catalogo
    )
    await db.commit()
    return AltasHechas(
        resultados=[
            ResultadoAlta(
                tipo=r.tipo,
                numero=r.numero,
                registrado=r.registrado,
                motivo=r.motivo,
                consumio_credito=r.consumio_credito,
            )
            for r in hechos
        ],
        creditos_consumidos=sum(1 for r in hechos if r.consumio_credito),
    )


__all__ = ["cliente_shipsgo", "router"]
