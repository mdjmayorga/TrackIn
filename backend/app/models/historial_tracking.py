"""`historial_tracking` — secuencia inmutable de posiciones. Ver §3 del modelo.

Cuelga del **elemento rastreado**, no del pedido: varias líneas de OC viajan en
el mismo buque y duplicar la posición por pedido multiplicaría la tabla sin
aportar nada.

`latitud` y `longitud` no existen como columnas: el propio SRS §8.6 dice que los
valores numéricos sueltos son insuficientes para las consultas espaciales, y
propone la columna geoespacial. Los valores crudos siguen íntegros dentro de
`payload_api`, que es lo que exige RNF-13.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HistorialTracking(Base):
    """Una lectura de posición de un elemento rastreado."""

    __tablename__ = "historial_tracking"
    __table_args__ = (
        CheckConstraint("velocidad IS NULL OR velocidad >= 0", name="velocidad"),
        CheckConstraint(
            "rumbo IS NULL OR (rumbo >= 0 AND rumbo < 360)", name="rumbo"
        ),
        # Idempotencia de la ingesta (§3.4): la misma lectura no se guarda dos
        # veces si el worker reprocesa o la fuente reenvía.
        Index(
            "uq_historial_tracking_lectura",
            "id_elemento_rastreado",
            "fecha_registro",
            unique=True,
        ),
        # Recuperar el trayecto de un elemento en orden cronológico (RF-22).
        Index(
            "ix_historial_tracking_elemento_fecha",
            "id_elemento_rastreado",
            "fecha_registro",
        ),
        {"comment": "Bitácora inmutable de posiciones. No se actualiza ni se borra."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_elemento_rastreado: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("elementos_rastreados.id", ondelete="RESTRICT"), nullable=False
    )
    #: Instante que reporta la fuente, no el de inserción.
    fecha_registro: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    posicion: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    #: Nudos. Anulable porque AIS no siempre la reporta, pero una fila sin
    #: velocidad no sirve para inferir arribo (RN-05) ni estimar ETA (RN-16).
    velocidad: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    rumbo: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    estado_api: Mapped[str | None] = mapped_column(String(40), nullable=True)

    #: Respuesta completa de la fuente, para auditoría (RNF-13).
    payload_api: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<HistorialTracking elem={self.id_elemento_rastreado} {self.fecha_registro}>"


__all__ = ["HistorialTracking"]
