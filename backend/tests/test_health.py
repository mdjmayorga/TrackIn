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


@pytest.fixture
async def salud_vacia():
    """`salud_fuentes` vacía, **confirmado**: el cliente usa su propia sesión.

    Lo que escriba la prueba se borra al terminar. En la base de desarrollo eso
    solo borra la última foto del worker, que la vuelve a escribir en su
    siguiente ciclo.
    """
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal, dispose_engine
    from app.models.salud_fuente import SaludFuente
    from app.services.salud_fuentes import registro as registro_salud

    async def vaciar() -> None:
        async with AsyncSessionLocal() as sesion:
            await sesion.execute(delete(SaludFuente))
            await sesion.commit()

    registro_salud.olvidar_todo()
    await vaciar()
    yield
    await vaciar()
    registro_salud.olvidar_todo()
    await dispose_engine()


@pytest.mark.integration
async def test_health_reporta_las_fuentes_externas(client: AsyncClient, salud_vacia) -> None:
    """La lista vacía es el estado normal mientras el worker no consultó nada."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["fuentes"] == []


@pytest.mark.integration
async def test_una_fuente_caida_no_degrada_el_servicio(client: AsyncClient, salud_vacia) -> None:
    """El quinto principio de `US-03`, que es la historia entera en una prueba:
    el dashboard lee de la base y no de la fuente, así que una API caída se
    informa pero **no** puede hacer que el servicio responda con un error.

    Desde `US-51` el estado lo escribe **otro proceso**: se simula al worker
    publicando en `salud_fuentes` con su propio registro, que la API no ve.
    """
    import datetime as dt

    from app.db.session import AsyncSessionLocal
    from app.services.resiliencia import ClaseFallo
    from app.services.salud_fuentes import RegistroSalud, guardar

    del_worker = RegistroSalud()
    fuente = del_worker.estado("tica")
    fuente.registrar_exito(instante=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=10))
    fuente.registrar_fallo(
        instante=dt.datetime.now(dt.UTC),
        clase=ClaseFallo.PERMANENTE,
        motivo="acceso_bloqueado",
    )
    async with AsyncSessionLocal() as sesion:
        await guardar(sesion, del_worker.estados())
        await sesion.commit()

    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    # `status` mira la base, no las fuentes externas.
    assert body["status"] == "ok"
    (reportada,) = body["fuentes"]
    assert reportada["fuente"] == "tica"
    assert reportada["degradada"] is True
    assert reportada["motivo_ultimo_fallo"] == "acceso_bloqueado"
    # RNF-12: se dice de cuándo es el último dato bueno, no solo que falló.
    assert reportada["antiguedad_s"] == pytest.approx(600, abs=30)
    assert reportada["reportado_en"] is not None


@pytest.mark.integration
async def test_la_memoria_de_la_api_no_manda_sobre_la_base(
    client: AsyncClient, salud_vacia
) -> None:
    """La API no consulta fuentes: si algo quedara en su memoria, no es lo que
    pasa en el worker. Con la base arriba, manda lo publicado."""
    import datetime as dt

    from app.services.resiliencia import ClaseFallo
    from app.services.salud_fuentes import registro as registro_salud

    registro_salud.estado("vizion").registrar_fallo(
        instante=dt.datetime.now(dt.UTC),
        clase=ClaseFallo.PERMANENTE,
        motivo="credencial_invalida",
    )

    response = await client.get("/health")

    assert response.json()["fuentes"] == []


async def test_el_esquema_documenta_las_fuentes(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    esquema = response.json()["components"]["schemas"]["HealthResponse"]
    assert "fuentes" in esquema["properties"]


@pytest.mark.integration
async def test_si_no_se_puede_leer_la_tabla_la_base_no_se_da_por_caida(
    client: AsyncClient, salud_vacia, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una migración sin aplicar no es una base caída: `status` sigue `ok` y se
    cae a lo que haya en memoria."""
    from app.api import health

    async def falla(*_args, **_kwargs):
        raise RuntimeError('relation "salud_fuentes" does not exist')

    monkeypatch.setattr(health, "leer_resumen", falla)

    body = (await client.get("/health")).json()

    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["fuentes"] == []
