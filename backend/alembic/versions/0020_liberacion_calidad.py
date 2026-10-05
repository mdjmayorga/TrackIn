"""La liberación de Control de Calidad — `US-47` / RN-10, RN-19, RF-32.

Desde el 04/09 la recepción en planta no cierra el pedido: lo cierra Calidad
cuando libera el material. Cuatro columnas nuevas en `pedidos_transito`:

- `fecha_liberacion_estimada_desde` y `_hasta`: la ventana de RN-19, en días
  hábiles desde la recepción. **Es un rango**, no una fecha, y se guarda como
  instantánea al recibir, igual que `lead_time_destino_dias`: cambiar el
  parámetro no reescribe lo que ya se estimó.
- `cantidad_liberada`: lo liberado hasta ahora. Calidad puede liberar por
  partes; la línea sigue activa hasta que lo liberado llega a lo recibido.
- `fecha_liberacion_calidad`: cuándo se liberó el total, que es cuando cierra.

Revision ID: 0020_liberacion_calidad
Revises: 0019_tolerancia_recepcion
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_liberacion_calidad"
down_revision = "0019_tolerancia_recepcion"
branch_labels = None
depends_on = None

TABLA = "pedidos_transito"
CHECK = "ck_pedidos_transito_cantidad_liberada"


def upgrade() -> None:
    op.add_column(TABLA, sa.Column("fecha_liberacion_estimada_desde", sa.Date(), nullable=True))
    op.add_column(TABLA, sa.Column("fecha_liberacion_estimada_hasta", sa.Date(), nullable=True))
    op.add_column(TABLA, sa.Column("cantidad_liberada", sa.Numeric(14, 3), nullable=True))
    op.add_column(
        TABLA, sa.Column("fecha_liberacion_calidad", sa.DateTime(timezone=True), nullable=True)
    )
    # SQL directo: la convención de nombres de `Base` antepondría otra vez el prefijo.
    op.execute(
        f"ALTER TABLE {TABLA} ADD CONSTRAINT {CHECK} "
        "CHECK (cantidad_liberada IS NULL OR cantidad_liberada >= 0)"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE {TABLA} DROP CONSTRAINT {CHECK}")
    op.drop_column(TABLA, "fecha_liberacion_calidad")
    op.drop_column(TABLA, "cantidad_liberada")
    op.drop_column(TABLA, "fecha_liberacion_estimada_hasta")
    op.drop_column(TABLA, "fecha_liberacion_estimada_desde")
