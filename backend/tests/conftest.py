"""Fixtures compartidas de pytest."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, dispose_engine
from app.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP que habla directo con la app ASGI, sin levantar servidor.

    El pool de conexiones vive a nivel de módulo en `app.db.session`, pero cada
    test corre en su propio event loop (`asyncio_default_fixture_loop_scope`).
    Una conexión de asyncpg queda atada al loop donde se abrió, así que si el
    pool sobrevive al test la siguiente prueba la reutiliza contra un loop
    muerto y falla con `'NoneType' object has no attribute 'send'`. Descartar
    el pool al final de cada test mantiene los loops aislados.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dispose_engine()


@pytest.fixture
async def sesion() -> AsyncGenerator[AsyncSession, None]:
    """Sesión contra la base real, con *rollback* garantizado al terminar.

    Requiere PostgreSQL corriendo con las migraciones aplicadas: las pruebas que
    la usan van marcadas `integration`. Todo lo que escriba el test se deshace,
    de modo que los datos semilla de `0002` quedan intactos y el orden de
    ejecución no importa.

    Se descarta el pool al final por el mismo motivo que en `client`: una
    conexión de asyncpg queda atada al event loop donde se abrió.
    """
    async with AsyncSessionLocal() as sesion_bd:
        await sesion_bd.begin()
        try:
            yield sesion_bd
        finally:
            await sesion_bd.rollback()
    await dispose_engine()
