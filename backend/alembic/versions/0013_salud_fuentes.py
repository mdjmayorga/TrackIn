"""La salud de las fuentes pasa a la base — `US-51` / RF-20, RNF-12.

Desde `US-50` el rastreo corre en un worker aparte de la API. El worker lleva
el `EstadoFuente` de cada fuente en memoria, y `/health` —que sirve la API,
otro proceso— nunca lo veía: el encabezado del dashboard no podía decir que
TICA estaba bloqueada ni de cuándo era el último dato de ShipsGo.

Una fila por fuente, que el worker sobrescribe al final de cada ciclo.

Revision ID: 0013_salud_fuentes
Revises: 0012_guia_hija_tica
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_salud_fuentes"
down_revision = "0012_guia_hija_tica"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "salud_fuentes",
        sa.Column("nombre", sa.String(length=40), nullable=False),
        sa.Column("degradada", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "clase_ultimo_fallo",
            sa.String(length=20),
            server_default=sa.text("'ninguno'"),
            nullable=False,
        ),
        sa.Column("motivo_ultimo_fallo", sa.String(length=60), nullable=True),
        sa.Column(
            "fallos_consecutivos", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("ultimo_contacto_ok", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_fallo", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reportado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "clase_ultimo_fallo IN ('ninguno', 'transitorio', 'permanente', 'requiere_alta')",
            name=op.f("ck_salud_fuentes_clase_ultimo_fallo"),
        ),
        sa.CheckConstraint(
            "fallos_consecutivos >= 0", name=op.f("ck_salud_fuentes_fallos_consecutivos")
        ),
        sa.PrimaryKeyConstraint("nombre", name=op.f("pk_salud_fuentes")),
        comment="Salud de cada fuente externa de rastreo, escrita por el worker.",
    )


def downgrade() -> None:
    op.drop_table("salud_fuentes")
