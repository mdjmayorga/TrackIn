"""`parametros_sistema` — umbrales fuera del código. Ver §8.3 del modelo.

Dos reglas de negocio la nombran textualmente: RN-05 exige que el radio de la
geocerca y el umbral de velocidad «residan en la tabla de mantenimiento de
parámetros», y RN-11 lo mismo para el umbral de riesgo, «de modo que pueda
ajustarse sin modificar el código fuente».

Usa **clave natural** y no sustituta: es un catálogo de configuración que se
consulta por nombre, y un `id` numérico solo añadiría una indirección.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TIPOS_DATO_PARAMETRO, check_in


class ParametroSistema(Base):
    """Un parámetro de configuración del sistema."""

    __tablename__ = "parametros_sistema"
    __table_args__ = (
        CheckConstraint(check_in("tipo_dato", TIPOS_DATO_PARAMETRO), name="tipo_dato"),
        {"comment": "Umbrales y frecuencias ajustables sin tocar el código."},
    )

    #: PK natural. Ej.: `radio_geocerca_km`, `umbral_riesgo_horas`.
    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_dato: Mapped[str] = mapped_column(String(15), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)

    id_usuario_modificacion: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    actualizado_en: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<ParametroSistema {self.clave}={self.valor!r}>"


__all__ = ["ParametroSistema"]
