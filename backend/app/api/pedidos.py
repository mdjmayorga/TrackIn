"""`/pedidos` — listado y detalle por API REST (`US-16`, RF-04 y RF-05).

Lee el estado ya calculado por el worker; ninguna petición llega a una fuente
externa (RNF-03). Los recursos se identifican por la clave sustituta, no por
OC y posición: `/pedidos/1042` es una URL, `/pedidos/4500001234/10` acoplaría
la ruta a SAP (`data-model.md` §1.2).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import (
    COMPRAS,
    LOGISTICA,
    PLANIFICACION,
    Autenticado,
    requiere_rol,
    usuario_actual,
)
from app.db.session import get_db
from app.models.pedido_transito import PedidoTransito
from app.schemas.pedidos import (
    AjusteEntrada,
    AsientoBitacora,
    ConfirmacionDesembarco,
    CumplimientoFiltro,
    DesembarcoEntrada,
    EstadoCalculado,
    EtapaFiltro,
    IndicadoresKpi,
    LiberacionEntrada,
    MapaPedidos,
    PaginaPedidos,
    PasoAduanalEntrada,
    PedidoDetalle,
    Porcentaje,
    ProximoArribo,
    ProximosArribos,
    RecepcionEntrada,
    RecepcionIncompleta,
    ReferenciaEntrada,
    Via,
)
from app.services import auditoria, consulta_pedidos, intervenciones
from app.services.consulta_pedidos import ORDEN_POR_OMISION, PATRON_ORDEN, Filtros
from app.services.intervenciones import ZONA_CR

# Cualquier rol autenticado consulta pedidos (`US-42`).
router = APIRouter(prefix="/pedidos", tags=["pedidos"], dependencies=[Depends(usuario_actual)])

#: RNF-01 fija 200 pedidos activos como volumen de referencia: una página cabe.
LIMITE_MAXIMO = 200


def filtros_de_consulta(
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
    solped: Annotated[
        str | None,
        Query(
            max_length=20,
            description="Prefijo del número de la solicitud de pedido (filtro de planta, `US-63`).",
        ),
    ] = None,
) -> Filtros:
    """Los filtros de RF-19, comunes a la grilla, los KPIs y los próximos
    arribos: los tres bloques tienen que mostrar el mismo subconjunto (`US-21`).
    """
    return Filtros(
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
        solped=solped,
    )


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
    filtros: Annotated[Filtros, Depends(filtros_de_consulta)],
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
    total, items = await consulta_pedidos.listar(
        db, filtros, orden=orden, limite=limite, desplazamiento=desplazamiento
    )
    return PaginaPedidos(total=total, limite=limite, desplazamiento=desplazamiento, items=items)


def _porcentaje(pedidos: int, evaluables: int) -> Porcentaje:
    if evaluables == 0:
        return Porcentaje(pedidos=pedidos, porcentaje=None)
    valor = (Decimal(pedidos) * 100 / evaluables).quantize(Decimal("0.01"))
    return Porcentaje(pedidos=pedidos, porcentaje=valor)


# Las rutas fijas van antes de `/{id_pedido}`: si no, «indicadores» se
# intentaría leer como id y respondería 422.
@router.get(
    "/indicadores",
    response_model=IndicadoresKpi,
    summary="Cinta de KPIs (US-22)",
    description=(
        "Pedidos activos, el reparto por cumplimiento y el lead time medio, con los "
        "mismos filtros que la grilla. Solo cuentan los activos, aunque el filtro pida "
        "cerrados o cancelados. Los porcentajes son sobre los activos con fecha "
        "proyectada; los demás se cuentan en `sin_proyeccion`."
    ),
)
async def indicadores(
    db: Annotated[AsyncSession, Depends(get_db)],
    filtros: Annotated[Filtros, Depends(filtros_de_consulta)],
) -> IndicadoresKpi:
    datos = await consulta_pedidos.indicadores(db, filtros)
    # Sobre los que tienen fecha proyectada: ver `IndicadoresKpi`.
    evaluables = datos.a_tiempo + datos.en_riesgo + datos.retrasados
    return IndicadoresKpi(
        activos=datos.activos,
        a_tiempo=_porcentaje(datos.a_tiempo, evaluables),
        en_riesgo=_porcentaje(datos.en_riesgo, evaluables),
        retrasados=_porcentaje(datos.retrasados, evaluables),
        sin_proyeccion=datos.sin_proyeccion,
        lead_time_medio_dias=datos.lead_time_medio_dias,
    )


@router.get(
    "/mapa/{capa}",
    response_model=MapaPedidos,
    summary="Embarques en el mapa (US-25, US-26)",
    description=(
        "Los embarques de la vía que tienen posición, uno por marcador con sus pedidos, "
        "coloreados por el estado más urgente. Mismos filtros que la grilla. Una lectura "
        "más vieja que el doble de la frecuencia de consulta de la vía se marca "
        "desactualizada."
    ),
)
async def mapa_de_pedidos(
    capa: Literal["MARITIMO", "AEREO"],
    db: Annotated[AsyncSession, Depends(get_db)],
    filtros: Annotated[Filtros, Depends(filtros_de_consulta)],
) -> MapaPedidos:
    return await consulta_pedidos.mapa(db, filtros, via=capa)


@router.get(
    "/proximos-arribos",
    response_model=ProximosArribos,
    summary="Próximos arribos (US-28)",
    description=(
        "Los cinco pedidos activos con fecha proyectada más próxima entre hoy y los "
        "siguientes 7 días, en hora de Costa Rica. Si hay menos, devuelve los que haya: "
        "no rellena con pedidos fuera del horizonte (RF-27, 01/09). Mismos filtros que "
        "la grilla."
    ),
)
async def proximos_arribos(
    db: Annotated[AsyncSession, Depends(get_db)],
    filtros: Annotated[Filtros, Depends(filtros_de_consulta)],
) -> ProximosArribos:
    hoy = hoy_en_costa_rica()
    pedidos = await consulta_pedidos.proximos_arribos(db, filtros, hoy=hoy)
    return ProximosArribos(
        hoy=hoy,
        horizonte_dias=consulta_pedidos.HORIZONTE_ARRIBOS_DIAS,
        items=[
            ProximoArribo(
                **p.model_dump(),
                # El filtro de la consulta garantiza que hay fecha.
                dias_restantes=(p.fecha_proyectada_disponible - hoy).days,  # type: ignore[operator]
            )
            for p in pedidos
        ],
    )


def hoy_en_costa_rica() -> dt.date:
    """Separado para que las pruebas fijen el día."""
    return dt.datetime.now(ZONA_CR).date()


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


# Decisión del 21/10/2026: **Compras hace en el detalle lo mismo que el
# Administrador**: confirmar desembarco, pasar a aduana, recibir (también con
# cierre forzado), liberar y ajustar días. Se suma a las tres guardas de abajo.

#: Quién confirma desembarcos, recibe y ajusta: Logística y Compras (y el Administrador).
logistica = requiere_rol(LOGISTICA, COMPRAS)
#: `US-47`: la liberación la registra Planificación, dueña de la historia, o
#: Logística, que ya registra la recepción, y Compras desde el 21/10. Calidad no
#: tiene rol en el sistema.
calidad = requiere_rol(PLANIFICACION, LOGISTICA, COMPRAS)
# El paso a proceso aduanal lo ejecuta Planificación (decisión del 04/09, `US-43`,
# `US-48`); Logística conserva el permiso, que tenía desde `US-14`. Corregido el 15/10.
# Compras también, desde la bandeja y el detalle (21/10).
aduana = requiere_rol(PLANIFICACION, LOGISTICA, COMPRAS)


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
    quien: Annotated[Autenticado, Depends(aduana)],
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


@router.post(
    "/{id_pedido}/recepcion",
    response_model=PedidoDetalle,
    summary="Registrar la recepción en planta (US-18)",
    description=(
        "Deja el pedido «Recibido en planta» **sin cerrarlo**: lo cierra la liberación "
        "de Calidad. Exige haber pasado aduana. Si lo recibido no llega al mínimo de "
        "RN-10 (`tolerancia_recepcion_pct`), el pedido no avanza y responde 409 con el "
        "mínimo, ofreciendo el cierre forzado."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {
            "model": RecepcionIncompleta,
            "description": "Recepción incompleta, o fuera de etapa.",
        },
    },
)
async def registrar_recepcion(
    id_pedido: int,
    datos: RecepcionEntrada,
    quien: Annotated[Autenticado, Depends(logistica)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle | JSONResponse:
    try:
        await intervenciones.registrar_recepcion(
            db,
            id_pedido,
            fecha=datos.fecha,
            cantidad=datos.cantidad,
            motivo=datos.motivo,
            id_usuario=quien.usuario.id,
        )
    except intervenciones.RecepcionIncompleta as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=RecepcionIncompleta(
                detail=str(exc),
                cantidad_pedida=exc.pedida,
                cantidad_recibida=exc.recibida,
                minimo_conforme=exc.minimo,
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
    "/{id_pedido}/cierre-forzado",
    response_model=PedidoDetalle,
    summary="Cerrar con una recepción parcial (US-18)",
    description=(
        "Registra lo recibido y cierra el pedido como `CIERRE_FORZADO` (RN-10, RN-13), "
        "cuando el resto no va a llegar. Deja dos asientos en la bitácora: la "
        "recepción y el cierre."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {"description": "Fuera de etapa o cerrado."},
    },
)
async def cerrar_forzado(
    id_pedido: int,
    datos: RecepcionEntrada,
    quien: Annotated[Autenticado, Depends(logistica)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle:
    try:
        await intervenciones.cerrar_forzado(
            db,
            id_pedido,
            fecha=datos.fecha,
            cantidad=datos.cantidad,
            motivo=datos.motivo,
            id_usuario=quien.usuario.id,
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
    "/{id_pedido}/liberacion-calidad",
    response_model=PedidoDetalle,
    summary="Registrar la liberación de Calidad (US-47)",
    description=(
        "Registra lo que Control de Calidad liberó. Con el total de lo recibido, el "
        "pedido se cierra (`RECEPCION_CONFORME`) y queda disponible para producción; "
        "con una parte, suma a lo liberado y la línea **sigue activa**. Exige la "
        "recepción en planta, y no se libera más de lo recibido."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {"description": "Sin recepción en planta, o cerrado."},
    },
)
async def liberar_calidad(
    id_pedido: int,
    datos: LiberacionEntrada,
    quien: Annotated[Autenticado, Depends(calidad)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle:
    try:
        await intervenciones.liberar_calidad(
            db,
            id_pedido,
            fecha=datos.fecha,
            cantidad=datos.cantidad,
            motivo=datos.motivo,
            id_usuario=quien.usuario.id,
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
    "/{id_pedido}/ajuste-manual",
    response_model=PedidoDetalle,
    summary="Ajustar la fecha proyectada (US-40)",
    description=(
        "Fija los días que RN-01 suma (o resta) a la fecha proyectada, con un motivo "
        "declarado. Reemplaza al ajuste anterior y 0 lo quita. Se recalcula en el acto, "
        "y la bitácora conserva el valor anterior y el nuevo."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {"description": "Cerrado, o el ajuste ya tiene ese valor."},
    },
)
async def ajustar_fecha(
    id_pedido: int,
    datos: AjusteEntrada,
    quien: Annotated[Autenticado, Depends(logistica)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle:
    try:
        await intervenciones.ajustar_fecha(
            db,
            id_pedido,
            dias=datos.dias,
            motivo=datos.motivo,
            id_usuario=quien.usuario.id,
        )
    except (
        LookupError,
        intervenciones.IntervencionRechazada,
        auditoria.IntervencionInvalida,
    ) as exc:
        raise _error_de_intervencion(exc) from exc
    return await _detalle_tras_intervenir(db, id_pedido)


# Logística registra la referencia (TASK-30) y Compras carga el archivo que la trae.
asociadores = requiere_rol(LOGISTICA, COMPRAS)


@router.post(
    "/{id_pedido}/referencia",
    response_model=PedidoDetalle,
    summary="Asociar el identificador de rastreo (US-20)",
    description=(
        "Vincula una referencia de embarque —contenedor, BL, booking, MAWB o guía hija— "
        "a un pedido que no la tiene, con su motivo. Valida el formato y el dígito de "
        "control (TASK-30), saca el pedido de «Sin tracking», recalcula y audita. Si el "
        "pedido ya tiene identificador responde 409: cambiarlo es un transbordo (US-30)."
    ),
    responses={
        404: {"description": "No existe el pedido."},
        409: {"description": "Cerrado, o ya tiene identificador."},
        422: {"description": "Referencia con formato o dígito de control inválido, o sin motivo."},
    },
)
async def asociar_referencia(
    id_pedido: int,
    datos: ReferenciaEntrada,
    quien: Annotated[Autenticado, Depends(asociadores)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoDetalle:
    try:
        await intervenciones.asociar_identificador(
            db,
            id_pedido,
            tipo=datos.tipo,
            numero=datos.numero,
            motivo=datos.motivo,
            id_usuario=quien.usuario.id,
        )
    except (
        LookupError,
        intervenciones.IntervencionRechazada,
        intervenciones.ReferenciaInvalida,
        auditoria.IntervencionInvalida,
    ) as exc:
        raise _error_de_intervencion(exc) from exc
    return await _detalle_tras_intervenir(db, id_pedido)


__all__ = ["router"]
