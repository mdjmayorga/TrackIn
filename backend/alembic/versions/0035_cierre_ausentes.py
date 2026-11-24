"""Cierre de los pedidos que dejan de venir en el Z-tracking — 24/11/2026.

Pedido de Mariano: el Z-tracking trae los pedidos abiertos en SAP, así que el que
no viene se da por cerrado allá y no debe seguir en el panel. Desde ahora la
carga lo cierra con el motivo `AUSENTE_EN_CARGA` (estado `CERRADO`) y lo reabre
si vuelve a venir.

La migración cierra también los que **ya** estaban marcados ausentes y seguían
activos: son los mismos que la próxima carga cerraría, y esperar a ella los
dejaría en el panel hasta entonces. Sin asiento en la bitácora —no hay quién
cargó—; `ausente_desde` conserva desde cuándo faltan.

Revision ID: 0035_cierre_ausentes
Revises: 0034_cierre_sin_referencia
"""

from __future__ import annotations

from alembic import op

revision = "0035_cierre_ausentes"
down_revision = "0034_cierre_sin_referencia"
branch_labels = None
depends_on = None

_RESTRICCION = "ck_pedidos_transito_motivo_cierre"
_MOTIVOS = "'RECEPCION_CONFORME', 'CIERRE_FORZADO', 'CANCELACION', 'SIN_REFERENCIA'"


def upgrade() -> None:
    op.drop_constraint(op.f(_RESTRICCION), "pedidos_transito", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION),
        "pedidos_transito",
        f"motivo_cierre IS NULL OR motivo_cierre IN ({_MOTIVOS}, 'AUSENTE_EN_CARGA')",
    )
    op.execute(
        "UPDATE pedidos_transito SET motivo_cierre = 'AUSENTE_EN_CARGA', "
        "estado_calculado = 'CERRADO' "
        "WHERE motivo_cierre IS NULL AND ausente_desde IS NOT NULL "
        "AND fecha_ultima_carga IS NOT NULL"
    )


def downgrade() -> None:
    # Vuelven a quedar activos y marcados ausentes, como antes de esta regla.
    # El estado se recalcula en el siguiente ciclo del worker.
    op.execute(
        "UPDATE pedidos_transito SET motivo_cierre = NULL, estado_calculado = etapa_viaje "
        "WHERE motivo_cierre = 'AUSENTE_EN_CARGA'"
    )
    op.drop_constraint(op.f(_RESTRICCION), "pedidos_transito", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION),
        "pedidos_transito",
        f"motivo_cierre IS NULL OR motivo_cierre IN ({_MOTIVOS})",
    )
