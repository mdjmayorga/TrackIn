"""`maestro_destinos` — puertos y aeropuertos de entrada, con su geocerca.

Ver `docs/data-model.md` §2.

**Corregido el 04/09/2026.** El 03/09 se dio por hecho que el destino era único
—la planta de Gutis— porque el Z-tracking trae `CR10` en el cien por ciento de
las líneas. Planeación aclaró que `CR10` es el **centro contable**, no el punto
de entrada: la carga entra por **Caldera, Moín, Limón o Juan Santamaría**.

De ahí que `radio_geocerca_km` sea por destino y no global: Moín y Limón distan
seis kilómetros, así que el radio de 50 km del parámetro general los solaparía y
el sistema no podría decir a cuál de los dos llegó el buque (RN-05).
"""

from __future__ import annotations

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VIAS_TRANSPORTE, check_in
from app.models.mixins import TimestampMixin


class MaestroDestino(Base, TimestampMixin):
    """Punto de entrada de la carga al país, con su lead time y su geocerca."""

    __tablename__ = "maestro_destinos"
    __table_args__ = (
        CheckConstraint(check_in("via_transporte", VIAS_TRANSPORTE), name="via_transporte"),
        CheckConstraint("lead_time_dias >= 0", name="lead_time"),
        CheckConstraint(
            "radio_geocerca_km IS NULL OR radio_geocerca_km > 0", name="radio"
        ),
        CheckConstraint("pais ~ '^[A-Z]{2}$'", name="pais"),
        {"comment": "Puertos y aeropuertos de entrada (TASK-13, repuesto en TASK-31)."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    #: UN/LOCODE del puerto o código OACI del aeropuerto. Clave natural.
    codigo: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    pais: Mapped[str] = mapped_column(String(2), nullable=False)
    via_transporte: Mapped[str] = mapped_column(String(10), nullable=False)

    #: WGS84. `GEOGRAPHY` y no `GEOMETRY` para que las distancias den metros.
    ubicacion: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    #: Radio propio del destino. `NULL` = usar `radio_geocerca_km` de parámetros.
    radio_geocerca_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Días desde el arribo hasta que la carga está disponible en planta (RN-01).
    lead_time_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<MaestroDestino {self.codigo} {self.nombre!r}>"


__all__ = ["MaestroDestino"]
