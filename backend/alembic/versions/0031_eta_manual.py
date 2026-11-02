"""La ETA a Costa Rica registrada a mano — `US-67`.

La guía `78469391954` (pedido 4500018865) terminó en París: ShipsGo la da por
llegada a su destino y no informa el tramo a San José. Sin ETA de ninguna
fuente el pedido no tenía fecha proyectada, y sin ella tampoco se podían
ajustar días (02/11/2026). Compras registra la ETA en el detalle; se audita
como `ETA_MANUAL`.

Revision ID: 0031_eta_manual
Revises: 0030_referencia_fuente
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_eta_manual"
down_revision = "0030_referencia_fuente"
branch_labels = None
depends_on = None

_RESTRICCION = "ck_auditoria_intervenciones_tipo_intervencion"
_TIPOS = (
    "'CONFIRMACION_DESEMBARCO', 'PASO_A_ADUANAL', 'RECEPCION_PLANTA', 'LIBERACION_CALIDAD', "
    "'TRANSBORDO', 'AJUSTE_MANUAL', 'CIERRE_FORZADO', 'ASOCIACION_TRACKING'"
)


def upgrade() -> None:
    op.add_column("pedidos_transito", sa.Column("eta_manual", sa.Date(), nullable=True))
    op.drop_constraint(op.f(_RESTRICCION), "auditoria_intervenciones", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION),
        "auditoria_intervenciones",
        f"tipo_intervencion IN ({_TIPOS}, 'ETA_MANUAL')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM auditoria_intervenciones WHERE tipo_intervencion = 'ETA_MANUAL'")
    op.drop_constraint(op.f(_RESTRICCION), "auditoria_intervenciones", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION), "auditoria_intervenciones", f"tipo_intervencion IN ({_TIPOS})"
    )
    op.drop_column("pedidos_transito", "eta_manual")
