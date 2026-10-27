"""`cargas_ztracking` — cada vez que alguien sube el Excel del Z-tracking (`US-58`).

Desde el 07/10/2026 el Excel es la vía definitiva de entrada: la API de SAP no
va a existir. La carga la hace Compras desde la interfaz, y esta tabla responde
lo que antes nadie podía responder: **quién cargó, cuándo, qué archivo y qué
pasó**. También las cargas rechazadas, que son las que más explican por qué un
pedido no aparece.

El informe completo de la carga (`InformeValidacion.como_dict`) se guarda en
`informe`, para poder volver a mostrarlo sin repetir la carga.

**Desde el 27/10/2026 también los lotes de la API de SAP** (`US-65`): `origen`
dice de dónde vino la carga. Un lote de SAP no lo sube una persona, así que no
tiene usuario; una carga del Excel siempre lo tiene (`ck_cargas_ztracking_autor`).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import check_in

if TYPE_CHECKING:
    from app.models.usuario import Usuario

APLICADA: Final = "APLICADA"
RECHAZADA: Final = "RECHAZADA"
ESTADOS_CARGA: Final[tuple[str, ...]] = (APLICADA, RECHAZADA)

EXCEL: Final = "EXCEL"
API_SAP: Final = "API_SAP"
ORIGENES_CARGA: Final[tuple[str, ...]] = (EXCEL, API_SAP)


class CargaZTracking(Base):
    """Una subida del Excel. `RECHAZADA` no tocó ningún pedido."""

    __tablename__ = "cargas_ztracking"
    __table_args__ = (
        CheckConstraint(check_in("estado", ESTADOS_CARGA), name="estado"),
        CheckConstraint(check_in("origen", ORIGENES_CARGA), name="origen"),
        CheckConstraint("origen = 'API_SAP' OR id_usuario IS NOT NULL", name="autor"),
        Index("ix_cargas_ztracking_realizada_en", "realizada_en"),
        {"comment": "Subidas del Excel del Z-tracking desde la interfaz (US-58)."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: Quién subió el Excel. Nulo en los lotes de SAP, que no los sube nadie.
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    origen: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=EXCEL,
        comment="EXCEL (subido por una persona) o API_SAP (US-65).",
    )
    #: El nombre con que se subió, para reconocerlo: «2026 - SEPTIEMBRE - WK38.xlsx».
    #: En un lote de SAP, «Lote <id del lote>».
    archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    realizada_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(10), nullable=False)
    #: Por qué se rechazó el archivo entero. Nulo en las aplicadas.
    motivo_rechazo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    recibidas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    insertadas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    actualizadas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sin_cambios: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ausentes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    no_entraron: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    entraron_sin_rastreo: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    informe: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    usuario: Mapped[Usuario | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<CargaZTracking {self.id} {self.estado} {self.archivo!r}>"


__all__ = [
    "API_SAP",
    "APLICADA",
    "ESTADOS_CARGA",
    "EXCEL",
    "ORIGENES_CARGA",
    "RECHAZADA",
    "CargaZTracking",
]
