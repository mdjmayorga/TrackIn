"""`pedido_elemento_rastreado` — asociativa de tramos. Ver §8.1 del modelo.

Sin esta tabla el transbordo rompe el trayecto: el FK único del pedido apunta
solo a la nave vigente, y a lo largo del tiempo la relación pedido-elemento es
N:M. Es lo que hace cumplibles a la vez RF-26 —conservar el historial de la nave
anterior asociado a su tramo— y RF-22 —consultar el trayecto completo—.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PedidoElementoRastreado(Base):
    """Tramo de un pedido a bordo de un elemento rastreado."""

    __tablename__ = "pedido_elemento_rastreado"
    __table_args__ = (
        UniqueConstraint("id_pedido", "tramo", name="tramo"),
        CheckConstraint("tramo > 0", name="tramo_positivo"),
        CheckConstraint(
            "fecha_hasta IS NULL OR fecha_hasta >= fecha_desde", name="rango"
        ),
        # Impide que un pedido tenga dos tramos vigentes a la vez.
        Index(
            "uq_pedido_elemento_rastreado_vigente",
            "id_pedido",
            unique=True,
            postgresql_where=text("fecha_hasta IS NULL"),
        ),
        {"comment": "Tramos de un pedido: 1 el original, +1 por cada transbordo."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pedidos_transito.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_elemento_rastreado: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("elementos_rastreados.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tramo: Mapped[int] = mapped_column(Integer, nullable=False)

    fecha_desde: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    #: `NULL` = tramo vigente.
    fecha_hasta: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: RF-26 pide el puerto y la fecha de la notificación como datos propios,
    #: no como texto libre dentro del motivo.
    puerto_transbordo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fecha_notificacion: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Tramo {self.tramo} pedido={self.id_pedido}>"


__all__ = ["PedidoElementoRastreado"]
