"""`usuarios` — autenticación y autoría de la auditoría (RF-14, RNF-05).

Ver `docs/data-model.md` §7.

**Ampliado el 03/09/2026.** La autenticación entró al alcance: el modelo del
Sprint 2 preveía tres roles y dejaba anotado que haría falta un cuarto si algún
perfil administrara cuentas. Con login real ese cuarto existe —`ADMINISTRADOR`—
y la autoría de RF-14 deja de tomarse de un selector manual para venir de la
sesión autenticada, lo que revierte la decisión B5.

Los usuarios **no se borran, se desactivan**: un `DELETE` rompería la
trazabilidad de la auditoría, que referencia al usuario de cada intervención.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ROLES, check_in
from app.models.mixins import TimestampMixin


class Usuario(Base, TimestampMixin):
    """Usuario del sistema, con su rol y su credencial."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(check_in("rol", ROLES), name="rol"),
        {"comment": "Usuarios con credencial propia. Sin SSO ni Active Directory."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    nombre_completo: Mapped[str] = mapped_column(String(120), nullable=False)
    correo: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)

    #: Hash con sal (argon2id o bcrypt), **nunca** la contraseña. El nombre de la
    #: columna hace evidente qué contiene. RNF-24.
    hash_contrasena: Mapped[str] = mapped_column(String(255), nullable=False)

    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    ultimo_acceso: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Usuario {self.usuario!r} rol={self.rol}>"


__all__ = ["Usuario"]
