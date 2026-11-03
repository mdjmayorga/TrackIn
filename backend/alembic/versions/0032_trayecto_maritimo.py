"""El trazado de las naves de un embarque marítimo — ruta en el mapa del panel.

El 03/11/2026 se pidió elegir un embarque en el mapa y ver su ruta, también en
el marítimo. ShipsGo ya mandaba el trazado de cada nave en el `geojson`, pero
TrackIn solo leía de ahí la posición actual. Se guarda como el de los vuelos.

Revision ID: 0032_trayecto_maritimo
Revises: 0031_eta_manual
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0032_trayecto_maritimo"
down_revision = "0031_eta_manual"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("elementos_rastreados", sa.Column("trayecto_maritimo", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("elementos_rastreados", "trayecto_maritimo")
