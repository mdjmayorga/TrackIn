"""La tolerancia de la recepción en planta — `US-18` / RN-10.

RN-10: la recepción es conforme cuando lo recibido *«satisface la cantidad
pedida dentro de un margen de tolerancia del diez por ciento»*. El modelo lo
dejó como parámetro y no como `CHECK` (`data-model.md` §1.5), porque es una
regla de negocio que puede cambiar; faltaba sembrarlo.

Revision ID: 0019_tolerancia_recepcion
Revises: 0018_arribo_sin_rastreo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_tolerancia_recepcion"
down_revision = "0018_arribo_sin_rastreo"
branch_labels = None
depends_on = None

_CLAVE = "tolerancia_recepcion_pct"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO parametros_sistema (clave, valor, tipo_dato, descripcion) "
            "VALUES (:clave, '10', 'DECIMAL', :descripcion) ON CONFLICT (clave) DO NOTHING"
        ),
        {
            "clave": _CLAVE,
            "descripcion": "Porcentaje bajo lo pedido que aún es recepción conforme (RN-10).",
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"), {"clave": _CLAVE}
    )
