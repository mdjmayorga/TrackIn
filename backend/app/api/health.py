"""Endpoint de salud: verifica que la app responde y que PostGIS está activo."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Estado del servicio y de sus dependencias."""

    status: Literal["ok", "degraded"] = Field(
        description="`ok` si la app y la base responden; `degraded` si la base falla."
    )
    version: str
    environment: str
    database: Literal["up", "down"]
    postgis: str | None = Field(
        default=None,
        description="Versión de PostGIS reportada por la base, o null si no hay conexión.",
    )
    detail: str | None = Field(
        default=None, description="Motivo del estado degradado, cuando aplica."
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Devuelve 200 siempre que el proceso esté vivo. Si la base de datos no "
        "responde, el campo `status` pasa a `degraded` y `detail` explica por qué."
    ),
)
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]) -> HealthResponse:
    """Consulta `postgis_version()` para probar conexión y extensión de una sola vez."""
    try:
        result = await db.execute(text("SELECT postgis_version();"))
        postgis_version = result.scalar_one()
    # Se captura Exception a propósito: un health check nunca debe propagar
    # un fallo de la base como error 500 del servicio.
    except Exception as exc:
        logger.warning("Health check: la base no respondió: %s", exc)
        return HealthResponse(
            status="degraded",
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            database="down",
            postgis=None,
            detail=f"{type(exc).__name__}: {exc}",
        )

    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database="up",
        postgis=str(postgis_version),
    )
