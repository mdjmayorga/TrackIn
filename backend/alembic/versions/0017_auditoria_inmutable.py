"""La auditoría no se altera — `US-15` / RF-14, RNF-06.

Segundo criterio de `US-15`: «dado un registro de auditoría, cuando intento
alterarlo, entonces la operación se rechaza». Se garantiza en la base y no solo
en el código: un `UPDATE` hecho a mano, desde otra herramienta o por un error
del propio sistema tiene que fallar igual.

Es el mismo patrón que `historial_tracking` (migración `0003`): un disparador
que rechaza `UPDATE` y `DELETE` fila por fila, más uno de sentencia para
`TRUNCATE`, que no dispara los de fila.

Para borrar de verdad —una depuración autorizada, las pruebas que limpian su
propia transacción— hay que desactivar el disparador **dentro de la
transacción**: `ALTER TABLE ... DISABLE TRIGGER`, que exige ser dueño de la
tabla y se revierte con ella.

Revision ID: 0017_auditoria_inmutable
Revises: 0016_sesiones
"""

from __future__ import annotations

from alembic import op

revision = "0017_auditoria_inmutable"
down_revision = "0016_sesiones"
branch_labels = None
depends_on = None

_FUNCION = """
CREATE OR REPLACE FUNCTION auditoria_intervenciones_inmutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'auditoria_intervenciones es inmutable: % rechazado',
        TG_OP
        USING HINT = 'La auditoria de RF-14 solo admite INSERT (US-15). Una correccion '
                     'se registra como una intervencion nueva, no editando la anterior.',
              ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_FUNCION)
    op.execute(
        "CREATE TRIGGER trg_auditoria_inmutable "
        "BEFORE UPDATE OR DELETE ON auditoria_intervenciones "
        "FOR EACH ROW EXECUTE FUNCTION auditoria_intervenciones_inmutable()"
    )
    op.execute(
        "CREATE TRIGGER trg_auditoria_sin_truncate "
        "BEFORE TRUNCATE ON auditoria_intervenciones "
        "FOR EACH STATEMENT EXECUTE FUNCTION auditoria_intervenciones_inmutable()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_auditoria_sin_truncate ON auditoria_intervenciones")
    op.execute("DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON auditoria_intervenciones")
    op.execute("DROP FUNCTION IF EXISTS auditoria_intervenciones_inmutable()")
