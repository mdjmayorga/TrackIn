"""`salud_fuentes` — la salud de cada fuente externa, compartida entre procesos.

Ver `docs/data-model.md` §8 y `app.services.salud_fuentes`.

Existe desde que el rastreo corre en un worker aparte (`US-50`): el worker es el
que consulta las fuentes y lleva su `EstadoFuente` en memoria, pero `/health`
lo sirve la API, que es otro proceso y nunca ve esa memoria. RF-20 y `US-23`
necesitan que el encabezado del dashboard muestre qué fuente falló y de cuándo
es su último dato bueno, así que el estado tiene que pasar por la base, que es
el único estado compartido entre los dos procesos (`architecture.md` §1.4).

**No es la copia de trabajo.** El worker decide con el `EstadoFuente` en memoria
y vuelca aquí una foto al final de cada ciclo. Una fila por fuente, que se
sobrescribe: el historial de fallos no interesa, interesa el estado actual.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import check_in
from app.models.mixins import TimestampMixin

#: Los valores de `resiliencia.ClaseFallo`. Se repiten acá en vez de importarlos
#: para que el modelo no dependa de la capa de servicios; una prueba verifica
#: que coincidan.
CLASES_FALLO: tuple[str, ...] = ("ninguno", "transitorio", "permanente", "requiere_alta")


class SaludFuente(Base, TimestampMixin):
    """Última foto de la salud de una fuente externa, escrita por el worker."""

    __tablename__ = "salud_fuentes"
    __table_args__ = (
        CheckConstraint(check_in("clase_ultimo_fallo", CLASES_FALLO), name="clase_ultimo_fallo"),
        CheckConstraint("fallos_consecutivos >= 0", name="fallos_consecutivos"),
        {"comment": "Salud de cada fuente externa de rastreo, escrita por el worker."},
    )

    #: `shipsgo`, `tica`, `aisstream`... ya normalizado a minúsculas.
    nombre: Mapped[str] = mapped_column(String(40), primary_key=True)
    degradada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    clase_ultimo_fallo: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ninguno'")
    )
    motivo_ultimo_fallo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fallos_consecutivos: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    #: El último dato bueno: de acá sale la antigüedad que exige RNF-12.
    ultimo_contacto_ok: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_fallo: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Cuándo lo escribió el worker. `actualizado_en` del mixin lo pone la base;
    #: este lo pone el worker con la hora del ciclo, y es el que dice si el
    #: worker sigue vivo: si deja de avanzar, la foto está vieja.
    reportado_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<SaludFuente {self.nombre} degradada={self.degradada}>"


__all__ = ["CLASES_FALLO", "SaludFuente"]
