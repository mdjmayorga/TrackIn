"""`proveedores` — normalización del proveedor. Ver `docs/data-model.md` §5.

El Z-tracking confirmó el 03/09/2026 que el origen entrega **código y nombre**
del proveedor (`1007052` + razón social), así que la normalización se resuelve
por código y **no hace falta coincidencia difusa**. Cierra la duda D3.

`fabricante` no vive aquí: el archivo lo trae como un campo aparte del pedido,
porque el fabricante del material puede no ser quien lo vende.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Proveedor(Base, TimestampMixin):
    """Proveedor de una línea de orden de compra."""

    __tablename__ = "proveedores"
    __table_args__ = (
        CheckConstraint("pais IS NULL OR pais ~ '^[A-Z]{2}$'", name="pais"),
        {"comment": "Maestro de proveedores, normalizado desde el código de origen."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    #: ISO 3166-1 alfa-2. Habilita el análisis de desempeño por origen.
    pais: Mapped[str | None] = mapped_column(String(2), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Proveedor {self.codigo} {self.nombre!r}>"


__all__ = ["Proveedor"]
