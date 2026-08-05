"""Base declarativa de SQLAlchemy.

Todos los modelos de `app.models` heredan de `Base`. Alembic importa este
módulo para descubrir el metadata al autogenerar migraciones.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Nombres de constraints determinísticos. Sin esto, Alembic genera migraciones
# con nombres autogenerados por Postgres y los downgrade no se pueden aplicar.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de todos los modelos ORM de TrackIn."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


__all__ = ["Base", "NAMING_CONVENTION"]
