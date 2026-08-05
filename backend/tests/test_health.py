"""Smoke tests del esqueleto de la API.

Los tests de esta sección NO requieren base de datos: `/health` está diseñado
para responder 200 aunque Postgres esté caído. La verificación de que PostGIS
realmente está activo va marcada como `integration`.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def test_root_devuelve_metadatos(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "TrackIn API"
    assert body["docs"] == "/docs"


async def test_health_responde_aunque_la_base_este_caida(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["version"] == "0.1.0"


async def test_openapi_se_genera(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "TrackIn API"
    assert "/health" in schema["paths"]


@pytest.mark.integration
async def test_postgis_esta_activo(client: AsyncClient) -> None:
    """Requiere `docker compose up -d postgres`."""
    response = await client.get("/health")
    body = response.json()

    if body["database"] == "down":
        pytest.skip(f"PostgreSQL no disponible: {body.get('detail')}")

    assert body["status"] == "ok"
    assert body["postgis"] is not None
    assert body["postgis"].startswith("3.")
