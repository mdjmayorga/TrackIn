"""Entorno de migraciones de Alembic para TrackIn.

Adaptado de la plantilla `async`:
  - la URL de la base se toma de `app.core.config`, no del alembic.ini,
    para no duplicar credenciales ni versionar secretos;
  - `target_metadata` apunta al Base de la app para soportar --autogenerate.
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic corre este archivo como script suelto: sin esto, `import app` falla.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importar app.models registra las tablas en Base.metadata. Mientras
# `app.models` esté vacío el autogenerate no detectará nada, que es lo
# esperado hasta el modelo de datos de Sprint 1-2.
import app.models
from app.core.config import settings
from app.db.base import Base

config = context.config

# La URL real nunca vive en alembic.ini: se inyecta acá desde el entorno.
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base (`alembic upgrade head --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Sin esto, cambios de tipo o de default no aparecen en el autogenerate.
        compare_type=True,
        compare_server_default=True,
        # PostGIS crea sus propias tablas y vistas de sistema; si no se
        # excluyen, el autogenerate propone borrarlas.
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


_TABLAS_POSTGIS = {"spatial_ref_sys", "geography_columns", "geometry_columns"}


def _include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Deja fuera del autogenerate los objetos que gestiona PostGIS."""
    return not (type_ == "table" and name in _TABLAS_POSTGIS)


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
