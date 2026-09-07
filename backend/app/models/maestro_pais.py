"""`maestro_paises` y sus alias — normalización del país de origen.

Entidad incorporada en `TASK-29` tras la entrega del Z-tracking (03/09/2026).
El archivo trae el país como **texto libre sucio**: conviven `USA` y
`ESTADOS UNIDOS`, `Mexico` sin tilde, y valores que no son países (`PENDIENTE`,
`N/A`). Sin catálogo, el filtro por origen y el mapa no son fiables.

`AliasPais` es lo que hace cumplible el criterio de `TASK-29`: varias grafías
resuelven al mismo país. La carga (`US-32`) consulta por alias normalizado y,
si no encuentra, marca la línea para revisión **sin abortar el lote** (RN-17).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MaestroPais(Base, TimestampMixin):
    """País de origen normalizado, con código ISO 3166-1 alfa-2."""

    __tablename__ = "maestro_paises"
    __table_args__ = (
        CheckConstraint("codigo ~ '^[A-Z]{2}$'", name="codigo_iso"),
        {"comment": "Catálogo de países de origen (TASK-29). ISO 3166-1 alfa-2."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    alias: Mapped[list["AliasPais"]] = relationship(
        back_populates="pais", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<MaestroPais {self.codigo} {self.nombre!r}>"


class AliasPais(Base):
    """Grafía alternativa con la que el archivo de origen nombra a un país.

    El alias se guarda **ya normalizado** —sin tildes, en mayúsculas y sin
    espacios de sobra— para que la búsqueda sea una igualdad y no un `LIKE`.
    """

    __tablename__ = "alias_paises"
    __table_args__ = {
        "comment": "Grafías alternativas del país en el archivo de origen (TASK-29)."
    }

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_pais: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("maestro_paises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)

    pais: Mapped[MaestroPais] = relationship(back_populates="alias")

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<AliasPais {self.alias!r} -> {self.id_pais}>"


__all__ = ["AliasPais", "MaestroPais"]
