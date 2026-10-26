"""Paquetes de créditos de ShipsGo comprados por Gutis — `US-57`.

ShipsGo cobra un crédito por embarque dado de alta, y los créditos se compran por
paquete anual (acuerdo del 06/10/2026: 1 100 a US$ 1,70, válidos 12 meses). Cada
fila es una compra registrada en TrackIn; **la última es el paquete vigente**.

El saldo no se guarda: se calcula. Es lo disponible al registrar el paquete
—`cantidad` más lo que se arrastró del anterior— menos las altas que costaron
crédito desde `registrado_en`, que vienen de la auditoría (RF-14). Así el saldo
no puede desincronizarse de lo que de verdad se gastó.

**El arrastre** es la condición que ShipsGo confirmó el 07/10/2026: los créditos
sin usar pasan al período siguiente si la compra nueva es de al menos el 50 % del
paquete anterior. `saldo_arrastrado` guarda lo que se sumó, para que el cálculo
no dependa de cómo estaba el paquete anterior en otro momento.

Las filas no se borran ni se editan: son la historia de lo que se compró.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class PaqueteCreditos(Base):
    """Una compra de créditos de ShipsGo. La más reciente es la vigente."""

    __tablename__ = "paquetes_creditos"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad"),
        CheckConstraint("saldo_arrastrado >= 0", name="saldo_arrastrado"),
        CheckConstraint("vence_en IS NULL OR vence_en >= comprado_en", name="vencimiento"),
        {"comment": "Paquetes de créditos de ShipsGo comprados (US-57)."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: Créditos del paquete comprado.
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Lo que quedaba del paquete anterior y se sumó a este (regla del 50 %).
    saldo_arrastrado: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    comprado_en: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: Nulo si no vence: los créditos de prueba del 23/09/2026 no tienen fecha.
    vence_en: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    #: Desde aquí se descuentan las altas: lo de antes es del paquete anterior.
    registrado_en: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    nota: Mapped[str | None] = mapped_column(String(300), nullable=True)

    usuario: Mapped[Usuario] = relationship()

    @property
    def disponible(self) -> int:
        """Lo que había al registrarlo: el paquete más lo arrastrado."""
        return self.cantidad + self.saldo_arrastrado

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<PaqueteCreditos {self.id} {self.cantidad}+{self.saldo_arrastrado}>"


__all__ = ["PaqueteCreditos"]
