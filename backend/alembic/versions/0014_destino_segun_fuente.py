"""De dónde salió el destino del pedido — `US-54`.

Desde la reunión con Compras del 29/09/2026, el puerto de descarga que declara
la naviera en ShipsGo manda sobre el del incoterm, que Compras escribe en SAP.
Para respetar eso también cuando ShipsGo **no responde** —una carga con
`--sin-shipsgo`, una caída, un embarque que madura— hay que saber si el destino
guardado vino de la fuente: si vino, el archivo no lo pisa.

Anular la columna no aportaría nada: todo destino salió de un lado o del otro.
Las filas existentes quedan en `false`, que es lo que eran hasta hoy salvo las
que entraron por `US-52`; esas se corrigen solas en la próxima carga con
ShipsGo.

Revision ID: 0014_destino_segun_fuente
Revises: 0013_salud_fuentes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_destino_segun_fuente"
down_revision = "0013_salud_fuentes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pedidos_transito",
        sa.Column(
            "destino_segun_fuente",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="true si el destino es el puerto que declaró la fuente de rastreo (US-54).",
        ),
    )


def downgrade() -> None:
    op.drop_column("pedidos_transito", "destino_segun_fuente")
