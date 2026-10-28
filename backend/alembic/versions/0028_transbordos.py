"""Los transbordos que informa ShipsGo — `US-30`.

Replanteo del 22/10/2026: el transbordo de un embarque que sigue ShipsGo se
registra solo, una vez por embarque, a partir del cambio de nave entre los
hitos. Ver `app/models/transbordo.py`.

Revision ID: 0028_transbordos
Revises: 0027_trayecto_aereo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_transbordos"
down_revision = "0027_trayecto_aereo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transbordos",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("id_elemento_rastreado", sa.BigInteger(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("vehiculo_anterior", sa.String(length=120), nullable=False),
        sa.Column("vehiculo_nuevo", sa.String(length=120), nullable=False),
        sa.Column("puerto", sa.String(length=10), nullable=True),
        sa.Column("puerto_nombre", sa.String(length=120), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ocurrido", sa.Boolean(), nullable=False),
        sa.Column(
            "detectado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_elemento_rastreado"],
            ["elementos_rastreados.id"],
            name=op.f("fk_transbordos_id_elemento_rastreado_elementos_rastreados"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transbordos")),
        sa.UniqueConstraint(
            "id_elemento_rastreado",
            "vehiculo_anterior",
            "vehiculo_nuevo",
            name=op.f("uq_transbordos_cambio"),
        ),
        comment="Cambios de nave o vuelo informados por ShipsGo (US-30).",
    )
    op.create_index(
        op.f("ix_transbordos_id_elemento_rastreado"),
        "transbordos",
        ["id_elemento_rastreado"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transbordos_id_elemento_rastreado"), table_name="transbordos")
    op.drop_table("transbordos")
