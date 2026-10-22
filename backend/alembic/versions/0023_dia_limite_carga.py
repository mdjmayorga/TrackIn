"""El día límite de la carga semanal del Z-tracking — `US-23`.

Reunión con Compras del 22/10/2026: SAP se actualiza los lunes y el Z-tracking
se carga en TrackIn a más tardar el martes. El encabezado del panel lo usa para
recordar la carga y avisar cuando falta.

Revision ID: 0023_dia_limite_carga
Revises: 0022_rol_planta
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_dia_limite_carga"
down_revision = "0022_rol_planta"
branch_labels = None
depends_on = None

_CLAVE = "dia_limite_carga"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO parametros_sistema (clave, valor, tipo_dato, descripcion) "
            "VALUES (:clave, '2', 'ENTERO', :descripcion) ON CONFLICT (clave) DO NOTHING"
        ),
        {
            "clave": _CLAVE,
            "descripcion": (
                "Último día para cargar el Z-tracking de la semana: 1 lunes … 7 domingo "
                "(US-23, acuerdo con Compras del 22/10/2026: martes)."
            ),
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"), {"clave": _CLAVE}
    )
