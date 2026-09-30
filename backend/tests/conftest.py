"""Fixtures compartidas de pytest."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import AsyncSessionLocal, dispose_engine
from app.main import app
from app.models.sesion import Sesion
from app.models.usuario import Usuario


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


def usuario_de_prueba(rol: str = "COMPRAS") -> Autenticado:
    """Un usuario autenticado sin tocar la base, para probar lo que no es el login."""
    usuario = Usuario(
        id=0, usuario=f"prueba-{rol.lower()}", nombre_completo="Prueba", rol=rol, activo=True
    )
    return Autenticado(usuario=usuario, sesion=Sesion(id=0, id_usuario=0))


@pytest.fixture
def como_rol() -> Iterator[Callable[[str], None]]:
    """`como_rol("LOGISTICA")` hace que la API vea a ese rol autenticado (`US-42`).

    Sustituye solo `usuario_actual`: `requiere_rol` sigue decidiendo con el rol
    que se le pase, así que las restricciones por rol se prueban de verdad.
    """

    def _como(rol: str) -> None:
        app.dependency_overrides[usuario_actual] = lambda: usuario_de_prueba(rol)

    yield _como
    app.dependency_overrides.pop(usuario_actual, None)


@pytest.fixture
async def cliente_compras(client: AsyncClient, como_rol) -> AsyncClient:
    """El cliente HTTP con una sesión de Compras, sin base de datos."""
    como_rol("COMPRAS")
    return client
