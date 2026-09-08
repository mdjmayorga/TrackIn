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


# --- Salud de las fuentes externas (`US-03`, RNF-12) -----------------------


async def test_health_reporta_las_fuentes_externas(client: AsyncClient) -> None:
    """La lista vacía es el estado normal mientras los adaptadores esperan a
    `TASK-28`: ninguna fuente se ha consultado todavía."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["fuentes"] == []


async def test_una_fuente_caida_no_degrada_el_servicio(client: AsyncClient) -> None:
    """El quinto principio de `US-03`, que es la historia entera en una prueba:
    el dashboard lee de la base y no de la fuente, así que una API caída se
    informa pero **no** puede hacer que el servicio responda con un error."""
    import datetime as dt

    from app.services.resiliencia import ClaseFallo
    from app.services.salud_fuentes import registro as registro_salud

    registro_salud.olvidar_todo()
    fuente = registro_salud.estado("vizion")
    fuente.registrar_exito(instante=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=10))
    fuente.registrar_fallo(
        instante=dt.datetime.now(dt.UTC),
        clase=ClaseFallo.PERMANENTE,
        motivo="credencial_invalida",
    )

    try:
        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        # `status` mira la base, no las fuentes externas.
        assert body["status"] in {"ok", "degraded"}
        assert body["detail"] is None or "vizion" not in body["detail"]

        (reportada,) = body["fuentes"]
        assert reportada["fuente"] == "vizion"
        assert reportada["degradada"] is True
        assert reportada["motivo_ultimo_fallo"] == "credencial_invalida"
        # RNF-12: se dice de cuándo es el último dato bueno, no solo que falló.
        assert reportada["antiguedad_s"] == pytest.approx(600, abs=30)
    finally:
        registro_salud.olvidar_todo()


async def test_el_esquema_documenta_las_fuentes(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    esquema = response.json()["components"]["schemas"]["HealthResponse"]
    assert "fuentes" in esquema["properties"]
