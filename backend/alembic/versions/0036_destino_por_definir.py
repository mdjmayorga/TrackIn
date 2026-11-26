"""Destino por definir y destino asignado a mano (26/11/2026).

Corrida en vivo con Compras: muchos pedidos marítimos todavía no tienen incoterm,
y sin puerto la carga los rechazaba. Desde ahora entran con el destino vacío
(«Por definir») y Compras o Logística lo asignan en el detalle.

- `id_destino` y `lead_time_destino_dias` pasan a anulables: sin destino no hay
  lead time, y la proyección ya sabía decir «sin lead time».
- `ASIGNACION_DESTINO` entra en la bitácora de intervenciones.
- `destino_manual` marca el destino que eligió una persona: una carga posterior
  no lo pisa con lo que diga el archivo; solo ShipsGo, que manda (`US-54`).

Revision ID: 0036_destino_por_definir
Revises: 0035_cierre_ausentes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036_destino_por_definir"
down_revision = "0035_cierre_ausentes"
branch_labels = None
depends_on = None

_RESTRICCION = "ck_auditoria_intervenciones_tipo_intervencion"
_TIPOS = (
    "'CONFIRMACION_DESEMBARCO', 'PASO_A_ADUANAL', 'RECEPCION_PLANTA', 'LIBERACION_CALIDAD', "
    "'TRANSBORDO', 'AJUSTE_MANUAL', 'CIERRE_FORZADO', 'ASOCIACION_TRACKING', 'ETA_MANUAL'"
)


def upgrade() -> None:
    op.alter_column("pedidos_transito", "id_destino", nullable=True)
    op.alter_column("pedidos_transito", "lead_time_destino_dias", nullable=True)
    op.add_column(
        "pedidos_transito",
        sa.Column("destino_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint(op.f(_RESTRICCION), "auditoria_intervenciones", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION),
        "auditoria_intervenciones",
        f"tipo_intervencion IN ({_TIPOS}, 'ASIGNACION_DESTINO')",
    )


def downgrade() -> None:
    # Volver atrás exige que todos tengan destino: los «Por definir» no caben en
    # el esquema anterior. Se avisa en vez de inventarles un puerto.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pedidos_transito WHERE id_destino IS NULL) "
        "THEN RAISE EXCEPTION 'Hay pedidos con destino por definir: asígnelos antes de "
        "volver a 0035'; END IF; END $$"
    )
    op.execute(
        "DELETE FROM auditoria_intervenciones WHERE tipo_intervencion = 'ASIGNACION_DESTINO'"
    )
    op.drop_constraint(op.f(_RESTRICCION), "auditoria_intervenciones", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION), "auditoria_intervenciones", f"tipo_intervencion IN ({_TIPOS})"
    )
    op.drop_column("pedidos_transito", "destino_manual")
    op.alter_column("pedidos_transito", "lead_time_destino_dias", nullable=False)
    op.alter_column("pedidos_transito", "id_destino", nullable=False)
