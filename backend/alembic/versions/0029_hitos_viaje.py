"""Los hitos del viaje, para la línea de tiempo del detalle — `US-29`.

ShipsGo informa en cada consulta los movimientos del embarque: salidas,
llegadas, descargas. Hasta ahora quedaban solo dentro del payload del historial,
y únicamente cuando la lectura traía posición. Se guarda la lista vigente en el
elemento rastreado y se reemplaza en cada lectura: un hito que la fuente corrige
o retira no queda duplicado (segundo criterio de `US-29`).

Revision ID: 0029_hitos_viaje
Revises: 0028_transbordos
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029_hitos_viaje"
down_revision = "0028_transbordos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "elementos_rastreados",
        sa.Column("hitos_viaje", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("elementos_rastreados", "hitos_viaje")
