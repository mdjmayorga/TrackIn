"""`sesiones` — una por login, en la base y no en un JWT (`US-42`).

Ver la migración `0016` para el porqué: cierre por inactividad, cuenta
compartida con sesiones simultáneas y revocación al desactivar un usuario.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Sesion(Base):
    """Una sesión abierta. `cerrada_en` no nulo es una sesión terminada."""

    __tablename__ = "sesiones"
    __table_args__ = (
        Index("ix_sesiones_id_usuario", "id_usuario"),
        {"comment": "Sesiones abiertas por el login (US-42). Se guarda el hash del token."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    #: SHA-256 del token en hexadecimal. El token solo lo conoce el cliente.
    hash_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: «Recordar sesión»: no cierra por inactividad sino al cumplir su duración.
    recordada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    creada_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ultimo_uso: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cerrada_en: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped[Usuario] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Sesion {self.id} usuario={self.id_usuario}>"


__all__ = ["Sesion"]
