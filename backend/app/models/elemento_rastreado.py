"""`elementos_rastreados` — la nave, el vuelo o el contenedor que se sigue.

Ver `docs/data-model.md` §4.

Existe porque varias líneas de orden de compra viajan en el mismo buque y porque
una misma línea puede cambiar de nave por transbordo. Desacopla el identificador
externo, la ETA y la última posición del pedido individual.

**Ampliado el 04/09/2026** con los tipos de referencia del contrato de captura
(`TASK-30`): `CONTENEDOR`, `BL`, `BOOKING` y `MAWB` son las claves con que se
consulta a **ShipsGo** —Vizion y Portcast quedaron fuera el 14/09/2026 por no
responder—. Sin una de ellas el pedido queda `SIN_TRACKING`.

`posicion_actual` y `velocidad_actual` están desnormalizadas a propósito: el
motor de estados las necesita en cada recálculo y consultar `historial_tracking`
cada vez contradiría el dimensionamiento de §3.6.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TIPOS_TRACKING, VIAS_TRANSPORTE, check_in
from app.models.mixins import TimestampMixin


class ElementoRastreado(Base, TimestampMixin):
    """Objeto de seguimiento externo: buque, vuelo, contenedor o guía aérea."""

    __tablename__ = "elementos_rastreados"
    __table_args__ = (
        CheckConstraint(check_in("tipo_tracking_externo", TIPOS_TRACKING), name="tipo_tracking"),
        CheckConstraint(check_in("via_transporte", VIAS_TRANSPORTE), name="via_transporte"),
        CheckConstraint("velocidad_actual IS NULL OR velocidad_actual >= 0", name="velocidad"),
        # Clave natural **única mientras esté activo** (§4.3): un MMSI puede
        # reutilizarse años después; lo que no puede es haber dos filas activas
        # con el mismo identificador.
        Index(
            "uq_elementos_rastreados_natural_activo",
            "tipo_tracking_externo",
            "tracking_externo",
            unique=True,
            postgresql_where=text("activo"),
        ),
        {"comment": "Nave, vuelo o contenedor objeto de seguimiento."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tipo_tracking_externo: Mapped[str] = mapped_column(String(20), nullable=False)
    tracking_externo: Mapped[str] = mapped_column(String(50), nullable=False)
    via_transporte: Mapped[str] = mapped_column(String(10), nullable=False)

    #: ETA y ATA tal como las reporta la fuente externa. Se distinguen de la
    #: inferida por el sistema y de la confirmada a mano (RN-05).
    eta_api: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ata_api: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    posicion_actual: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    #: Nudos. RN-05 la usa para descartar el buque que pasa de largo.
    velocidad_actual: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    ultima_actualizacion_api: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: `US-11` lo pone en `false` al arribar, para no gastar cuota siguiendo
    #: naves que ya no llevan carga nuestra.
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<ElementoRastreado {self.tipo_tracking_externo}" f":{self.tracking_externo!r}>"


__all__ = ["ElementoRastreado"]
