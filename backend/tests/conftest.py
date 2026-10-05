"""Fixtures compartidas de pytest.

**Las pruebas corren contra `trackin_test`, nunca contra `trackin_dev`.** La
base de desarrollo guarda datos reales —auditoría inmutable incluida— y las
pruebas que vacían `pedidos_transito` no pueden borrar un pedido auditado.
`POSTGRES_TEST_DB` permite apuntar a otra base; CI usa el mismo nombre.

La variable se fija antes de importar `app`: `settings` se construye al
importarse, y una variable de entorno real manda sobre el `.env`.

**La base de pruebas se migra sola** al empezar la sesión (`alembic upgrade
head`), así una migración nueva no deja las pruebas contra un esquema viejo.
Se omite con `-m "not integration"`, que no toca la base.
"""

from __future__ import annotations

import os

os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_TEST_DB", "trackin_test")

import subprocess
import sys
from collections.abc import AsyncGenerator, Callable, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import AsyncSessionLocal, dispose_engine
from app.main import app
from app.models.sesion import Sesion
from app.models.usuario import Usuario

BACKEND_DIR = Path(__file__).resolve().parent.parent


def pytest_sessionstart(session: pytest.Session) -> None:
    """Lleva la base de pruebas a la última migración antes de correr nada.

    En un proceso aparte: `alembic/env.py` abre su propio event loop. Si la
    base no responde no se aborta: las pruebas de integración fallarán con su
    propio error, y las demás corren igual.
    """
    if "not integration" in (session.config.option.markexpr or ""):
        return
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        ultima = (resultado.stderr.strip().splitlines() or ["sin detalle"])[-1]
        print(f"\n⚠ No se pudo migrar {os.environ['POSTGRES_DB']}: {ultima}", file=sys.stderr)


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


async def vaciar_auditoria(sesion: AsyncSession) -> None:
    """Borra la auditoría dentro de la transacción de la prueba (`US-15`).

    La tabla es inmutable por disparador (migración `0017`). Las pruebas que
    vacían pedidos necesitan borrarla antes —el FK es `RESTRICT`—, así que
    desactivan el disparador **dentro de su transacción**: el `ALTER TABLE` es
    transaccional en PostgreSQL y se revierte con el resto al terminar.
    """
    await sesion.execute(
        text("ALTER TABLE auditoria_intervenciones DISABLE TRIGGER trg_auditoria_inmutable")
    )
    await sesion.execute(text("DELETE FROM auditoria_intervenciones"))
    await sesion.execute(
        text("ALTER TABLE auditoria_intervenciones ENABLE TRIGGER trg_auditoria_inmutable")
    )
