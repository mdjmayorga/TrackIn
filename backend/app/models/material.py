"""`materiales` — normalización del material. Ver `docs/data-model.md` §6.

Separa el código de la descripción, que el SRS §8.2 tenía concatenados en un
solo `VARCHAR`. Así el filtro por material de RF-19 opera sobre el código en vez
de hacer `LIKE` sobre una cadena.

`unidad_medida` existe también en la línea de pedido: la del pedido es la de esa
línea concreta, que puede diferir de la unidad base del material.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Material(Base, TimestampMixin):
    """Material o insumo comprado."""

    __tablename__ = "materiales"
    __table_args__ = ({"comment": "Maestro de materiales, normalizado desde el código de origen."},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Unidad base del material (G, ML, MG, UN, CS…).
    unidad_medida: Mapped[str | None] = mapped_column(String(10), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Material {self.codigo} {self.descripcion!r}>"


__all__ = ["Material"]
