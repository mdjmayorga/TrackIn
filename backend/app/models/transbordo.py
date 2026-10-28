"""`transbordos` — los cambios de nave (o de vuelo) que informa ShipsGo — `US-30`.

Replanteo del 22/10/2026: con ShipsGo se rastrea **el embarque** —BL,
contenedor o MAWB—, que no cambia en un transbordo, y la fuente informa la nave
nueva. Nadie lo captura: el worker lo deduce del cambio de nave entre los
hitos y lo guarda acá, **una vez por embarque**. Todas las líneas de OC del
mismo BL lo comparten, porque comparten el elemento rastreado.

Medido en los envíos del spike `TASK-28`: el transbordo aparece en el primer
hito de la nave nueva —la salida desde el puerto de transbordo—, con su puerto
y su fecha (`MAERSK CHACHAI → MAERSK NACALA` en Cartagena, `… → MAERSK MONTE
PASCOAL` en Manzanillo). ShipsGo también informa los **previstos** (estimados):
se guardan con `ocurrido = false` y se actualizan cuando suceden.

No va a `auditoria_intervenciones`: esa tabla es de intervenciones humanas y
exige un usuario. El paso manual de guía hija a guía madre sí es una
intervención, y se audita allí como `TRANSBORDO`.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transbordo(Base):
    """Un cambio de nave o de vuelo dentro de un embarque."""

    __tablename__ = "transbordos"
    __table_args__ = (
        # Una vez por embarque: la misma pareja de naves no se registra dos veces.
        UniqueConstraint(
            "id_elemento_rastreado", "vehiculo_anterior", "vehiculo_nuevo", name="cambio"
        ),
        {"comment": "Cambios de nave o vuelo informados por ShipsGo (US-30)."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    id_elemento_rastreado: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("elementos_rastreados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Orden dentro del trayecto: 1 el primer transbordo.
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    vehiculo_anterior: Mapped[str] = mapped_column(String(120), nullable=False)
    vehiculo_nuevo: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Código UN/LOCODE o IATA del puerto o aeropuerto, y su nombre.
    puerto: Mapped[str | None] = mapped_column(String(10), nullable=True)
    puerto_nombre: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Cuándo salió la nave nueva, según la fuente. Estimada si no `ocurrido`.
    fecha: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ocurrido: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detectado_en: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Transbordo {self.vehiculo_anterior} → {self.vehiculo_nuevo}>"


__all__ = ["Transbordo"]
