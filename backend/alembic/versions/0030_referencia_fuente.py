"""El número del embarque tal como lo registró ShipsGo — mapa del detalle.

El mapa embebido de ShipsGo busca el embarque por texto exacto, y ShipsGo no
siempre guarda el número como TrackIn: los BL de Maersk dados de alta desde su
web van sin `MAEU` (`271108898`), y las MAWB con guion (`784-69391954`) aunque
el Z-tracking las traiga sin él. Con el número de TrackIn el mapa salía vacío
(02/11/2026: 2 de 5 BL y 3 de 5 MAWB). Se guarda el de ShipsGo en cada lectura.

Revision ID: 0030_referencia_fuente
Revises: 0029_hitos_viaje
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030_referencia_fuente"
down_revision = "0029_hitos_viaje"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "elementos_rastreados",
        sa.Column("referencia_fuente", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("elementos_rastreados", "referencia_fuente")
