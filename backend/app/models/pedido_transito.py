"""`pedidos_transito` — registro central. Ver `docs/data-model.md` §1.

La fila es la **línea** de orden de compra, no la orden: cinco líneas de una
misma OC pueden viajar en barcos distintos y llegar en fechas distintas.

**Ampliado el 03/09/2026** con los campos que aporta el Z-tracking real:
`incoterm`, `temperatura` (cadena de frío), `tipo_proveedor`, `fabricante` y el
país de origen normalizado. El incoterm no es decorativo: determina quién posee
la referencia de embarque y, por lo tanto, si el pedido se puede rastrear.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ESTADOS_CALCULADOS,
    ESTADOS_CUMPLIMIENTO,
    ETAPAS_VIAJE,
    MOTIVOS_CIERRE,
    TIPOS_PROVEEDOR,
    VIAS_TRANSPORTE,
    check_in,
)
from app.models.mixins import TimestampMixin


class PedidoTransito(Base, TimestampMixin):
    """Línea de orden de compra en tránsito."""

    __tablename__ = "pedidos_transito"
    __table_args__ = (
        UniqueConstraint("oc_numero", "posicion_oc", name="oc_numero"),
        CheckConstraint(check_in("via_transporte", VIAS_TRANSPORTE), name="via_transporte"),
        CheckConstraint(check_in("etapa_viaje", ETAPAS_VIAJE), name="etapa_viaje"),
        CheckConstraint(
            f"estado_cumplimiento IS NULL OR "
            f"{check_in('estado_cumplimiento', ESTADOS_CUMPLIMIENTO)}",
            name="estado_cumplimiento",
        ),
        CheckConstraint(check_in("estado_calculado", ESTADOS_CALCULADOS), name="estado_calculado"),
        CheckConstraint(
            f"motivo_cierre IS NULL OR {check_in('motivo_cierre', MOTIVOS_CIERRE)}",
            name="motivo_cierre",
        ),
        CheckConstraint(
            f"tipo_proveedor IS NULL OR " f"{check_in('tipo_proveedor', TIPOS_PROVEEDOR)}",
            name="tipo_proveedor",
        ),
        # --- Las tres que hacen trabajo real (§1.5) -------------------------
        # RN-02: no tener nave asociada *es* el estado SIN_TRACKING.
        CheckConstraint(
            "(id_elemento_rastreado IS NULL) = (etapa_viaje = 'SIN_TRACKING')",
            name="sin_tracking",
        ),
        # RN-13: los estados terminales y el motivo de cierre van juntos.
        CheckConstraint(
            "(motivo_cierre IS NULL) = " "(estado_calculado NOT IN ('CERRADO','CANCELADO'))",
            name="terminal",
        ),
        # RN-10: una recepción conforme exige fecha y cantidad recibidas.
        CheckConstraint(
            "motivo_cierre <> 'RECEPCION_CONFORME' OR "
            "(fecha_recepcion_planta IS NOT NULL AND cantidad_recibida IS NOT NULL)",
            name="recepcion",
        ),
        CheckConstraint("cantidad_pedida > 0", name="cantidad_pedida"),
        CheckConstraint(
            "cantidad_recibida IS NULL OR cantidad_recibida >= 0",
            name="cantidad_recibida",
        ),
        CheckConstraint("posicion_oc > 0", name="posicion_oc"),
        CheckConstraint("lead_time_destino_dias >= 0", name="lead_time"),
        # Búsqueda por prefijo de OC (decisión A5): el btree basta, no hace
        # falta la extensión pg_trgm.
        Index("ix_pedidos_transito_oc_numero", "oc_numero"),
        Index("ix_pedidos_transito_estado_calculado", "estado_calculado"),
        Index("ix_pedidos_transito_fecha_proyectada", "fecha_proyectada_disponible"),
        {"comment": "Línea de orden de compra en tránsito. Granularidad: la línea."},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # --- Identificación -----------------------------------------------------
    #: El Z-tracking confirmó diez dígitos exactos en las 2.045 líneas, pero se
    #: conserva VARCHAR(20) mientras la fuente siga siendo un archivo editable.
    oc_numero: Mapped[str] = mapped_column(String(20), nullable=False)
    posicion_oc: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Código interno que genera TrackIn en la ingesta. Clave alterna.
    tracking_interno: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

    # --- Datos maestros -----------------------------------------------------
    id_proveedor: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("proveedores.id"), nullable=False, index=True
    )
    id_material: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("materiales.id"), nullable=False, index=True
    )
    id_destino: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("maestro_destinos.id"), nullable=False, index=True
    )
    #: País de origen normalizado (TASK-29). Anulable: el archivo lo trae vacío
    #: en el 61 % de las líneas y la carga no debe abortar por eso (RN-17).
    id_pais_origen: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("maestro_paises.id"), nullable=True, index=True
    )

    via_transporte: Mapped[str] = mapped_column(String(10), nullable=False)
    cantidad_pedida: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unidad_medida: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_entrega_pedido: Mapped[dt.date] = mapped_column(Date, nullable=False)

    # --- Campos del Z-tracking (03/09/2026) ---------------------------------
    #: EXW, FOB, FCA → el flete lo controla Gutis y la referencia existe desde
    #: el booking. CIF, CIP, CPT → la tiene el proveedor y hay que exigírsela.
    incoterm: Mapped[str | None] = mapped_column(String(15), nullable=True)
    #: Cadena de frío: «Ambiente», «2-8 °C», «15-25 °C».
    temperatura: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tipo_proveedor: Mapped[str | None] = mapped_column(String(15), nullable=True)
    #: Puede diferir del proveedor: quien fabrica no siempre es quien vende.
    fabricante: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # --- Vínculo de rastreo -------------------------------------------------
    #: Único FK anulable de la entidad; su nulidad *es* `SIN_TRACKING` (RN-02).
    #: Apunta a la nave vigente; el historial de tramos vive en la asociativa.
    id_elemento_rastreado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("elementos_rastreados.id"), nullable=True, index=True
    )

    # --- Cálculo de la fecha proyectada (RN-01, RN-14, RN-16) ---------------
    #: Desnormalizado a propósito: guarda el valor **usado en el recálculo**,
    #: para que editar el maestro no reescriba el desglose ya calculado (RF-05).
    lead_time_destino_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    ajuste_manual_dias: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    eta_utilizada: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Los tres orígenes del arribo que RN-05 exige distinguir. El origen no
    #: necesita columna: se deriva por precedencia confirmada → api → inferida.
    ata_confirmada: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ata_inferida: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Anulable: RN-16 contempla el caso «ETA no estimable», en el que el
    #: sistema explícitamente no proyecta.
    fecha_proyectada_disponible: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    fecha_ultimo_recalculo: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Estado: dos dimensiones, no una (§1.4) -----------------------------
    etapa_viaje: Mapped[str] = mapped_column(String(20), nullable=False)
    #: `NULL` cuando no hay fecha proyectada: sin ETA estimable no se puede
    #: afirmar si llega a tiempo, y ningún valor del dominio dice eso.
    estado_cumplimiento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado_calculado: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- Cierre (RN-10, RN-13, RN-15) ---------------------------------------
    fecha_recepcion_planta: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cantidad_recibida: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    motivo_cierre: Mapped[str | None] = mapped_column(String(25), nullable=True)

    # --- Relaciones ---------------------------------------------------------
    proveedor: Mapped[Proveedor] = relationship()  # noqa: F821
    material: Mapped[Material] = relationship()  # noqa: F821
    destino: Mapped[MaestroDestino] = relationship()  # noqa: F821
    pais_origen: Mapped[MaestroPais | None] = relationship()  # noqa: F821
    elemento_rastreado: Mapped[ElementoRastreado | None] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<PedidoTransito {self.oc_numero}-{self.posicion_oc}>"


__all__ = ["PedidoTransito"]
