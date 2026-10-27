"""`/api/v1/integraciones/sap` — TrackIn escucha a la API de SAP (`US-65`).

Reunión de entrega del Informe 2 (27/10/2026): la API de SAP todavía no existe,
pero cuando exista **SAP empuja** los pedidos a TrackIn. El contrato está en
`docs/integraciones/sap/` (`US-64`).

El orden de las guardas es parte del contrato (y de la colección de Postman):

1. **La clave** (`X-API-Key`), contra `SAP_INTEGRACION_CLAVE`. Sin clave en el
   servidor, todo se rechaza: no hay forma de usar la escucha sin configurarla.
2. **La escucha** (`sap_escucha_habilitada`), que arranca apagada: `503` sin
   leer el cuerpo ni tocar la base.
3. **El tamaño** del lote (`413`) y **el formato** (`422`). Un lote inválido se
   rechaza entero: nada a medias.

Por eso el cuerpo se lee a mano y no como parámetro de FastAPI: si no, la
validación correría antes que las dos primeras guardas.
"""

from __future__ import annotations

import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cargas import resolutor_de_destinos
from app.api.dependencias import ADMINISTRADOR, Autenticado, requiere_rol, usuario_actual
from app.core.config import settings
from app.db.session import get_db
from app.schemas.cargas import Autor, CargaResumen, Incidencia
from app.schemas.integracion_sap import (
    MAXIMO_PEDIDOS,
    CambioEscucha,
    EscuchaApagada,
    EstadoEscuchaOut,
    InformeLote,
    LoteSap,
)
from app.services.ingesta import carga_archivo, carga_sap
from app.services.ingesta.carga import ResolutorDestino

router = APIRouter(prefix="/integraciones/sap", tags=["integración SAP"])
#: Decisión del 27/10/2026: la escucha la enciende solo el Administrador.
solo_administrador = requiere_rol(ADMINISTRADOR)

_clave_en_encabezado = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clave de la integración con SAP (`SAP_INTEGRACION_CLAVE`).",
)


def clave_valida(
    clave: Annotated[str | None, Depends(_clave_en_encabezado)],
) -> None:
    """`401` si falta la clave, no coincide o el servidor no tiene ninguna."""
    esperada = settings.SAP_INTEGRACION_CLAVE
    # `compare_digest` tarda lo mismo acierte o no: no deja adivinar la clave
    # carácter por carácter midiendo el tiempo de respuesta.
    if not esperada or not clave or not hmac.compare_digest(clave.encode(), esperada.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Falta la clave de integración (encabezado X-API-Key) o no es válida.",
        )


def _errores(exc: ValidationError) -> list[dict[str, Any]]:
    # Sin `input` ni `ctx`: no se devuelve el dato recibido, solo dónde y por qué.
    return [{"loc": ["body", *e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]


@router.post(
    "/pedidos",
    response_model=InformeLote,
    summary="Recibir un lote de pedidos de SAP (US-65)",
    description=(
        "Lo llama SAP, no una persona. Carga los pedidos por el mismo camino que el Excel "
        "—normalización, carga idempotente por OC y posición, rechazo línea por línea, "
        "recálculo— **sin marcar ausentes** los que no vienen. Queda en el historial de "
        "cargas con origen API_SAP. Con la escucha apagada responde 503 sin tocar nada. "
        "Contrato: `docs/integraciones/sap/`."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": LoteSap.model_json_schema()}},
        }
    },
    responses={
        401: {"description": "Falta la clave de integración o no es válida."},
        409: {"description": "Hay otra carga en curso (Excel o SAP). Reintentar."},
        413: {"description": f"Más de {MAXIMO_PEDIDOS} pedidos: partir el lote."},
        422: {"description": "El lote no cumple el contrato. No se cargó nada."},
        503: {"model": EscuchaApagada, "description": "La escucha está apagada."},
    },
)
async def recibir_pedidos(
    request: Request,
    _: Annotated[None, Depends(clave_valida)],
    db: Annotated[AsyncSession, Depends(get_db)],
    resolutor: Annotated[ResolutorDestino | None, Depends(resolutor_de_destinos)],
) -> InformeLote | JSONResponse:
    if not await carga_sap.escucha_habilitada(db):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=EscuchaApagada(
                detail=(
                    "La escucha de la API de SAP está deshabilitada. Un administrador la "
                    "enciende en Configuración → Integración con SAP."
                )
            ).model_dump(),
        )

    cuerpo = await request.body()
    try:
        crudo = json.loads(cuerpo)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "El cuerpo no es un JSON válido."
        ) from exc
    pedidos = crudo.get("pedidos") if isinstance(crudo, dict) else None
    if isinstance(pedidos, list) and len(pedidos) > MAXIMO_PEDIDOS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El lote trae {len(pedidos)} pedidos; el máximo es {MAXIMO_PEDIDOS}. "
            "Envíelo en partes.",
        )
    try:
        lote = LoteSap.model_validate_json(cuerpo)
    except ValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": _errores(exc)}
        )

    try:
        fila = await carga_sap.cargar_lote(
            db, lote, tamano=len(cuerpo), resolutor_destino=resolutor
        )
    except carga_archivo.CargaEnCurso as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()

    informe = fila.informe or {}
    return InformeLote(
        id_carga=fila.id,
        lote_id=lote.lote.id,
        estado="APLICADA",
        recibidas=fila.recibidas,
        insertadas=fila.insertadas,
        actualizadas=fila.actualizadas,
        sin_cambios=fila.sin_cambios,
        no_entraron=fila.no_entraron,
        entraron_sin_rastreo=fila.entraron_sin_rastreo,
        incidencias=[Incidencia.model_validate(i) for i in informe.get("incidencias", [])],
    )


async def _estado(db: AsyncSession) -> EstadoEscuchaOut:
    estado = await carga_sap.estado_escucha(db)
    return EstadoEscuchaOut(
        habilitada=estado.habilitada,
        cambiada_por=Autor.model_validate(estado.cambiada_por) if estado.cambiada_por else None,
        cambiada_en=estado.cambiada_en,
        clave_configurada=bool(settings.SAP_INTEGRACION_CLAVE),
        ultima_recepcion=(
            CargaResumen.model_validate(estado.ultima_recepcion)
            if estado.ultima_recepcion
            else None
        ),
    )


@router.get(
    "/escucha",
    response_model=EstadoEscuchaOut,
    summary="¿Está encendida la escucha de SAP? (US-66)",
    description="Cualquier usuario la ve; solo el Administrador la cambia.",
)
async def ver_escucha(
    _: Annotated[Autenticado, Depends(usuario_actual)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EstadoEscuchaOut:
    return await _estado(db)


@router.put(
    "/escucha",
    response_model=EstadoEscuchaOut,
    summary="Encender o apagar la escucha de SAP (US-66)",
    description=(
        "Solo el Administrador (decisión del 27/10/2026). Queda registrado quién la cambió "
        "y cuándo. Apagarla no deshace lo que ya se cargó: solo deja de aceptar envíos."
    ),
)
async def cambiar_escucha(
    datos: CambioEscucha,
    quien: Annotated[Autenticado, Depends(solo_administrador)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EstadoEscuchaOut:
    await carga_sap.cambiar_escucha(db, habilitada=datos.habilitada, id_usuario=quien.usuario.id)
    await db.commit()
    return await _estado(db)


__all__ = ["clave_valida", "router"]
