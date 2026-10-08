"""Registro de las cargas del Excel del Z-tracking — `US-58`.

El 07/10/2026 se descartó la API de SAP: el Excel es la vía definitiva de
entrada y la carga pasa a la interfaz, en manos de Compras. Esta tabla guarda
cada subida —también las rechazadas— con quién la hizo, cuándo, el resultado y
el informe completo.

Revision ID: 0021_cargas_ztracking
Revises: 0020_liberacion_calidad
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_cargas_ztracking"
down_revision = "0020_liberacion_calidad"
branch_labels = None
depends_on = None

TABLA = "cargas_ztracking"


def _contador(nombre: str) -> sa.Column:
    return sa.Column(nombre, sa.Integer(), server_default=sa.text("0"), nullable=False)


def upgrade() -> None:
    op.create_table(
        TABLA,
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("id_usuario", sa.BigInteger(), nullable=False),
        sa.Column("archivo", sa.String(length=255), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("realizada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(length=10), nullable=False),
        sa.Column("motivo_rechazo", sa.String(length=500), nullable=True),
        _contador("recibidas"),
        _contador("insertadas"),
        _contador("actualizadas"),
        _contador("sin_cambios"),
        _contador("ausentes"),
        _contador("no_entraron"),
        _contador("entraron_sin_rastreo"),
        sa.Column("informe", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "estado IN ('APLICADA', 'RECHAZADA')", name=op.f("ck_cargas_ztracking_estado")
        ),
        sa.ForeignKeyConstraint(
            ["id_usuario"],
            ["usuarios.id"],
            name=op.f("fk_cargas_ztracking_id_usuario_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cargas_ztracking")),
        comment="Subidas del Excel del Z-tracking desde la interfaz (US-58).",
    )
    op.create_index("ix_cargas_ztracking_realizada_en", TABLA, ["realizada_en"])


def downgrade() -> None:
    op.drop_index("ix_cargas_ztracking_realizada_en", table_name=TABLA)
    op.drop_table(TABLA)
