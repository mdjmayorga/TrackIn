"""Un destino no se repite por nombre y vía — `US-13`.

El cuarto criterio de `US-13` pide impedir un destino duplicado en nombre y
vía. Hasta ahora solo el código era único: «Puerto Limón» se podía dar de alta
dos veces con códigos distintos, y la ingesta —que ubica por el nombre que
aparece en el incoterm— no sabría a cuál mandar la línea.

El índice compara el nombre **sin mayúsculas**: «Puerto Moín» y «puerto moín»
son el mismo puerto. El servicio lo valida antes con un mensaje claro; el
índice es lo que lo garantiza si dos altas llegan a la vez.

Revision ID: 0015_destino_nombre_unico
Revises: 0014_destino_segun_fuente
"""

from __future__ import annotations

from alembic import op

revision = "0015_destino_nombre_unico"
down_revision = "0014_destino_segun_fuente"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_maestro_destinos_nombre_via "
        "ON maestro_destinos (lower(nombre), via_transporte)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_maestro_destinos_nombre_via")
