"""Router agregador de la API versionada.

Los routers de dominio se van montando acá a medida que avanzan los sprints:

    from app.api.routes import pedidos, tracking_maritimo, tracking_aereo

    api_router.include_router(pedidos.router, prefix="/pedidos", tags=["pedidos"])
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/", tags=["meta"], summary="Índice de la API v1")
async def api_index() -> dict[str, str]:
    """Placeholder: se reemplaza cuando existan los primeros recursos."""
    return {
        "message": "TrackIn API v1",
        "status": "sin recursos todavía — pendiente de Sprint 1",
    }


__all__ = ["api_router"]
