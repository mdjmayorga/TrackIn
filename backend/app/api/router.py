"""Router agregador de la API versionada.

Los routers de dominio se montan acá a medida que avanzan los sprints.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.pedidos import router as pedidos_router

api_router = APIRouter()
api_router.include_router(pedidos_router)


@api_router.get("/", tags=["meta"], summary="Índice de la API v1")
async def api_index() -> dict[str, str]:
    """Los recursos disponibles, para quien llega sin leer `/docs`."""
    return {
        "message": "TrackIn API v1",
        "pedidos": "/pedidos",
    }


__all__ = ["api_router"]
