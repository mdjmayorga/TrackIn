"""Rol `PLANTA`: la pantalla permanente de planta, de solo lectura — `US-43`.

La pantalla de planta (RNF-11) queda encendida y desatendida en un lugar
común. Con la cuenta de un rol operativo, cualquiera que se acercara podría
confirmar desembarcos o cargar un Z-tracking. Con `PLANTA` solo se lee: el rol
no figura en ningún `requiere_rol` de la API, así que toda escritura responde
403. Al entrar, el frontend lo lleva a la grilla simple del Figma.

Revision ID: 0022_rol_planta
Revises: 0021_cargas_ztracking
"""

from __future__ import annotations

from alembic import op

revision = "0022_rol_planta"
down_revision = "0021_cargas_ztracking"
branch_labels = None
depends_on = None

NOMBRE = "ck_usuarios_rol"
NUEVA = "rol IN ('COMPRAS', 'LOGISTICA', 'PLANIFICACION', 'ADMINISTRADOR', 'PLANTA')"
ANTERIOR = "rol IN ('COMPRAS', 'LOGISTICA', 'PLANIFICACION', 'ADMINISTRADOR')"


# SQL directo y no `op.drop_constraint`: la convención de nombres de `Base`
# volvería a anteponer el prefijo `ck_usuarios_` al nombre completo (`0018`).
def upgrade() -> None:
    op.execute(f"ALTER TABLE usuarios DROP CONSTRAINT {NOMBRE}")
    op.execute(f"ALTER TABLE usuarios ADD CONSTRAINT {NOMBRE} CHECK ({NUEVA})")


def downgrade() -> None:
    # Falla si quedan cuentas PLANTA: hay que desactivarlas y cambiarles el rol
    # antes. Los usuarios no se borran (la auditoría los referencia).
    op.execute(f"ALTER TABLE usuarios DROP CONSTRAINT {NOMBRE}")
    op.execute(f"ALTER TABLE usuarios ADD CONSTRAINT {NOMBRE} CHECK ({ANTERIOR})")
