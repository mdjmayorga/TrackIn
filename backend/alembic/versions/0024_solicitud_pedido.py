"""Número de la solicitud de pedido (SOLPED) de cada línea — `US-63`.

Reunión con Compras del 22/10/2026: la pantalla de planta muestra OC, POS y
SOLPED. El Z-tracking ya traía la columna «Solicitud de pedido»; el lector no la
leía. Nullable: una línea sin SOLPED entra igual, y las ya cargadas la reciben
en la siguiente carga.

Revision ID: 0024_solicitud_pedido
Revises: 0023_dia_limite_carga
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_solicitud_pedido"
down_revision = "0023_dia_limite_carga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pedidos_transito", sa.Column("solicitud_pedido", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("pedidos_transito", "solicitud_pedido")
