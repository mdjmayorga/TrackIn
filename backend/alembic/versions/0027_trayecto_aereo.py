"""El trayecto de los vuelos, para estimar la posición aérea — `US-26`.

ShipsGo no da la posición de un avión, pero sí los vuelos de cada embarque con
su horario y su trazado. Se guardan en el elemento rastreado y el mapa estima
la posición en el momento en que se mira (decisión del 06/10/2026).

Revision ID: 0027_trayecto_aereo
Revises: 0026_integracion_sap
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027_trayecto_aereo"
down_revision = "0026_integracion_sap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "elementos_rastreados",
        sa.Column("trayecto_aereo", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("elementos_rastreados", "trayecto_aereo")
