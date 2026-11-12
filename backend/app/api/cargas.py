"""`/api/v1/cargas` — subir el Excel del Z-tracking y ver el historial (`US-58`).

Desde el 07/10/2026 el Excel es la vía definitiva de entrada de los pedidos (la
API de SAP no va a existir). Cargan Compras y el Administrador; el historial lo
ve cualquier usuario, porque explica por qué un pedido está o no está.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencias import COMPRAS, Autenticado, requiere_rol, usuario_actual
from app.core.config import settings
from app.db.session import get_db
from app.models.carga_ztracking import CargaZTracking
from app.schemas.cargas import CargaDetalle, CargaResumen, EstadoCargas
from app.services import consulta_pedidos
from app.services.ingesta import carga_archivo, exportacion, frescura, plantilla
from app.services.ingesta.carga import ResolutorDestino
from app.services.rastreo import transporte_http
from app.services.rastreo.destino_shipsgo import ResolutorDestinoShipsGo

compras = requiere_rol(COMPRAS)
router = APIRouter(prefix="/cargas", tags=["cargas"])


async def resolutor_de_destinos() -> AsyncIterator[ResolutorDestino | None]:
    """El mismo resolutor del script: ShipsGo completa el destino que el archivo
    no dice (`US-52`). Solo lee, que es gratis. Sin token, la carga sigue sin él.
    """
    if not settings.SHIPSGO_API_TOKEN:
        yield None
        return
    async with transporte_http.crear_cliente_http() as http:
        yield ResolutorDestinoShipsGo(
            transporte_http.crear_cliente_shipsgo(http, settings.SHIPSGO_API_TOKEN)
        )


def _detalle(fila: CargaZTracking) -> CargaDetalle:
    informe = fila.informe or {}
    return CargaDetalle.model_validate(
        {
            **CargaResumen.model_validate(fila).model_dump(),
            "por_motivo": informe.get("por_motivo", {}),
            "incidencias": informe.get("incidencias", []),
            "avisos": informe.get("avisos", []),
            "cerrados_sin_referencia": informe.get("cerrados_sin_referencia", []),
        }
    )


@router.post(
    "",
    response_model=CargaDetalle,
    status_code=status.HTTP_201_CREATED,
    summary="Subir el Excel del Z-tracking (US-58)",
    description=(
        "Carga los pedidos del Excel exportado de SAP: inserta los nuevos, actualiza los "
        "existentes por OC y posición, marca como ausentes los que no vienen (sin borrarlos) "
        "y recalcula. Devuelve el informe con cada línea que no entró y por qué. Un archivo "
        "que no es el Z-tracking —sin las hojas PRODUCCION e IDA, dañado o sin líneas— se "
        "rechaza entero con 422 y no toca ningún pedido."
    ),
    responses={
        409: {"description": "Hay otra carga en curso."},
        422: {"description": "El archivo no es un Z-tracking utilizable. No se cargó nada."},
    },
)
async def subir_ztracking(
    archivo: Annotated[UploadFile, File(description="El Excel del Z-tracking (.xlsx).")],
    quien: Annotated[Autenticado, Depends(compras)],
    db: Annotated[AsyncSession, Depends(get_db)],
    resolutor: Annotated[ResolutorDestino | None, Depends(resolutor_de_destinos)],
) -> CargaDetalle:
    # Se lee un byte de más para distinguir «justo en el límite» de «se pasa».
    contenido = await archivo.read(carga_archivo.TAMANO_MAXIMO_BYTES + 1)
    nombre = archivo.filename or ""
    try:
        fila = await carga_archivo.cargar_archivo(
            db,
            contenido=contenido,
            nombre_archivo=nombre,
            id_usuario=quien.usuario.id,
            resolutor_destino=resolutor,
        )
    except carga_archivo.ArchivoInvalido as exc:
        # El rechazo queda registrado aunque no se haya cargado nada: es lo que
        # explica, después, por qué un archivo «no hizo nada».
        await db.rollback()
        carga_archivo.registrar_rechazo(
            db,
            nombre_archivo=nombre,
            tamano=len(contenido),
            id_usuario=quien.usuario.id,
            motivo=str(exc),
        )
        await db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except carga_archivo.CargaEnCurso as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    fila.usuario = quien.usuario
    return _detalle(fila)


@router.get(
    "",
    response_model=list[CargaResumen],
    summary="Historial de cargas",
    description="Las cargas más recientes primero, aplicadas y rechazadas.",
)
async def listar_cargas(
    _: Annotated[Autenticado, Depends(usuario_actual)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[CargaZTracking]:
    filas = await db.scalars(
        select(CargaZTracking)
        .options(selectinload(CargaZTracking.usuario))
        .order_by(CargaZTracking.realizada_en.desc(), CargaZTracking.id.desc())
        .limit(limite)
    )
    return list(filas)


# Antes de `/{id_carga}`: si no, «plantilla» se intentaría leer como número de carga.
@router.get(
    "/plantilla",
    response_class=Response,
    summary="Descargar la plantilla vacía del Z-tracking (US-59)",
    description=(
        "Un Excel con las hojas PRODUCCION e IDA y solo el encabezado, en el orden y con los "
        "rótulos del archivo real (WK43), incluidas las columnas de referencia de embarque. "
        "Llenada sin cambiarle la estructura, la carga la acepta sin diferencias. Solo Compras "
        "y el Administrador."
    ),
    responses={200: {"content": {plantilla.TIPO_XLSX: {}}}},
)
async def descargar_plantilla(_: Annotated[Autenticado, Depends(compras)]) -> Response:
    return Response(
        plantilla.generar_plantilla(),
        media_type=plantilla.TIPO_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{plantilla.NOMBRE_ARCHIVO}"'},
    )


# También antes de `/{id_carga}`.
@router.get(
    "/exportacion",
    response_class=Response,
    summary="Descargar los pedidos activos en Excel (US-68)",
    description=(
        "Todos los pedidos activos, los de la grilla sin filtros, en un Excel de dos hojas: "
        "«Grilla», con las columnas del panel, y «PRODUCCION», con las de la plantilla del "
        "Z-tracking, que se puede volver a cargar en otro equipo. En «PRODUCCION» van solo "
        "las líneas con referencia de embarque, porque sin ella la carga las rechaza. Solo "
        "Compras y el Administrador."
    ),
    responses={200: {"content": {plantilla.TIPO_XLSX: {}}}},
)
async def descargar_pedidos(
    _: Annotated[Autenticado, Depends(compras)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    ahora = dt.datetime.now(frescura.ZONA_CR)
    pedidos = await consulta_pedidos.activos(db)
    return Response(
        exportacion.generar(pedidos, ahora),
        media_type=plantilla.TIPO_XLSX,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{exportacion.nombre_archivo(ahora.date())}"'
            )
        },
    )


@router.get(
    "/estado",
    response_model=EstadoCargas,
    summary="¿Está cargado el Z-tracking de esta semana?",
    description=(
        "SAP se actualiza los lunes y Compras carga el Z-tracking a más tardar el día límite "
        "(`dia_limite_carga`, martes por omisión; acuerdo del 22/10/2026). Lo usa el "
        "encabezado del panel (`US-23`). Cualquier rol lo ve."
    ),
)
async def estado_cargas(
    _: Annotated[Autenticado, Depends(usuario_actual)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EstadoCargas:
    estado = await frescura.estado_semanal(db)
    return EstadoCargas(
        situacion=estado.situacion,
        ultima=CargaResumen.model_validate(estado.ultima) if estado.ultima else None,
        semana_desde=estado.semana_desde,
        dia_limite=estado.dia_limite,
    )


@router.get(
    "/{id_carga}",
    response_model=CargaDetalle,
    summary="Una carga con su informe",
    responses={404: {"description": "No existe la carga."}},
)
async def detalle_carga(
    id_carga: int,
    _: Annotated[Autenticado, Depends(usuario_actual)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CargaDetalle:
    fila = await db.scalar(
        select(CargaZTracking)
        .options(selectinload(CargaZTracking.usuario))
        .where(CargaZTracking.id == id_carga)
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la carga.")
    return _detalle(fila)


__all__ = ["resolutor_de_destinos", "router"]
