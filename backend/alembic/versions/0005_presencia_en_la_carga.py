"""Marca de presencia de cada línea en la última carga del archivo.

`US-31`, segundo criterio: *«dado un pedido que ya no figura en el archivo,
cuando cargo, entonces lo señalo para revisión manual y NO lo elimino»*.

**Por qué hacen falta dos columnas y no un booleano.** «Señalar para revisión»
solo sirve si alguien puede encontrar lo señalado y saber desde cuándo lo está.
Un booleano diría que la línea falta, pero no si falta desde ayer —un archivo
recortado por error— o desde hace tres semanas, que es la diferencia entre
investigar y archivar.

- `fecha_ultima_carga` — cuándo se vio por última vez en un archivo.
- `ausente_desde` — cuándo dejó de aparecer. `NULL` significa presente, y es la
  condición que consulta la bandeja de revisión.

**Por qué no se borra.** Un pedido que desaparece del archivo casi nunca es un
pedido que dejó de existir: es una línea que Compras cerró en SAP, un archivo
exportado con otro filtro, o una hoja que alguien recortó. Borrarlo destruiría
su historial de tracking —que es inmutable por RNF-13— y no habría forma de
distinguir un cierre legítimo de un error de exportación.

El índice es **parcial** sobre lo ausente: es un conjunto pequeño y siempre se
consulta con el mismo filtro, igual que los índices vivos de `0001`.

Revision ID: 0005_presencia_en_la_carga
Revises: 0004_parametros_resiliencia
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_presencia_en_la_carga"
down_revision = "0004_parametros_resiliencia"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pedidos_transito",
        sa.Column(
            "fecha_ultima_carga",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Última vez que la línea vino en un archivo de carga (US-31).",
        ),
    )
    op.add_column(
        "pedidos_transito",
        sa.Column(
            "ausente_desde",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Desde cuándo dejó de figurar en el archivo. NULL = presente (US-31).",
        ),
    )
    op.create_index(
        "ix_pedidos_transito_ausentes",
        "pedidos_transito",
        ["ausente_desde"],
        postgresql_where=sa.text("ausente_desde IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_pedidos_transito_ausentes", table_name="pedidos_transito")
    op.drop_column("pedidos_transito", "ausente_desde")
    op.drop_column("pedidos_transito", "fecha_ultima_carga")
