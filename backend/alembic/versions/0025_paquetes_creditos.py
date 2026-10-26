"""Paquetes de créditos de ShipsGo — `US-57`.

Acuerdo del 06/10/2026: Gutis compra los créditos de ShipsGo por paquete anual.
TrackIn registra cada compra para llevar el saldo —lo disponible menos las altas
que costaron, según la auditoría— y avisar antes de que se agoten o venzan.

Revision ID: 0025_paquetes_creditos
Revises: 0024_solicitud_pedido
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_paquetes_creditos"
down_revision = "0024_solicitud_pedido"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paquetes_creditos",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("saldo_arrastrado", sa.Integer(), server_default="0", nullable=False),
        sa.Column("comprado_en", sa.Date(), nullable=False),
        sa.Column("vence_en", sa.Date(), nullable=True),
        sa.Column(
            "registrado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id_usuario", sa.BigInteger(), nullable=False),
        sa.Column("nota", sa.String(length=300), nullable=True),
        sa.CheckConstraint("cantidad > 0", name=op.f("ck_paquetes_creditos_cantidad")),
        sa.CheckConstraint(
            "saldo_arrastrado >= 0", name=op.f("ck_paquetes_creditos_saldo_arrastrado")
        ),
        sa.CheckConstraint(
            "vence_en IS NULL OR vence_en >= comprado_en",
            name=op.f("ck_paquetes_creditos_vencimiento"),
        ),
        sa.ForeignKeyConstraint(
            ["id_usuario"],
            ["usuarios.id"],
            name=op.f("fk_paquetes_creditos_id_usuario_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paquetes_creditos")),
        comment="Paquetes de créditos de ShipsGo comprados (US-57).",
    )


def downgrade() -> None:
    op.drop_table("paquetes_creditos")
