"""`auditoria_intervenciones` — bitácora de intervenciones manuales (RF-14).

Ver §8.2 del modelo. Sin esta tabla, RF-14 y RNF-06 no se pueden cumplir:

    «El sistema debe registrar, por cada intervención manual sobre un pedido, el
    usuario que la ejecutó, la fecha y hora, el valor anterior, el valor nuevo y
    el motivo declarado.»

**Desde el 03/09/2026 `id_usuario` sale de la sesión autenticada**, no de un
selector manual: con login real la autoría deja de ser declarativa, lo que
revierte la decisión B5.

El FK a `usuarios` es `RESTRICT` a propósito: borrar un usuario dejaría
registros de auditoría sin autor y la trazabilidad perdería sentido.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TIPOS_INTERVENCION, check_in


class AuditoriaIntervencion(Base):
    """Una intervención manual sobre un pedido."""

    __tablename__ = "auditoria_intervenciones"
    __table_args__ = (
        CheckConstraint(
            check_in("tipo_intervencion", TIPOS_INTERVENCION), name="tipo_intervencion"
        ),
        Index("ix_auditoria_intervenciones_pedido_fecha", "id_pedido", "fecha_hora"),
        {"comment": "Bitácora de intervenciones manuales exigida por RF-14."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pedidos_transito.id", ondelete="RESTRICT"), nullable=False
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fecha_hora: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tipo_intervencion: Mapped[str] = mapped_column(String(30), nullable=False)
    campo_afectado: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: RF-14 lo exige declarado, por eso no es anulable.
    motivo: Mapped[str] = mapped_column(String(300), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Auditoria {self.tipo_intervencion} pedido={self.id_pedido}>"


__all__ = ["AuditoriaIntervencion"]
