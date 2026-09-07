"""Mixins compartidos por los modelos ORM."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """`creado_en` y `actualizado_en` en UTC.

    Son metadatos de la fila. **No sustituyen** a `auditoria_intervenciones`,
    que registra quién hizo cada intervención manual y con qué motivo (RF-14).

    El `default` y el `onupdate` se declaran del lado del servidor para que una
    carga masiva o un `UPDATE` hecho fuera del ORM también los mantengan.
    """

    creado_en: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actualizado_en: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["TimestampMixin"]
