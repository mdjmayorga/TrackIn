"""Un pedido sin rastreo puede llegar, si una persona lo confirma — `US-14`.

RN-02 se implementó como «no tener nave asociada **es** `SIN_TRACKING`», en
las dos direcciones:

    (id_elemento_rastreado IS NULL) = (etapa_viaje = 'SIN_TRACKING')

Con eso, un pedido sin referencia no podía pasar nunca a `EN_DESTINO`, ni
siquiera cuando alguien de Logística confirma que la carga llegó. Y esos son
casi todos: 106 de 107 en la base del 30/09. El 01/09 se decidió que `US-14` es
justo **el único mecanismo** que cierra ese paso para ellos.

La regla nueva conserva la dirección que importa y abre una sola excepción:

- Con elemento rastreado, la etapa **no** es `SIN_TRACKING` (como antes).
- Sin elemento, la etapa es `SIN_TRACKING` **salvo** que haya una llegada
  confirmada a mano (`ata_confirmada`): eso sí es información, y con ella el
  pedido avanza.

Revision ID: 0018_arribo_sin_rastreo
Revises: 0017_auditoria_inmutable
"""

from __future__ import annotations

from alembic import op

revision = "0018_arribo_sin_rastreo"
down_revision = "0017_auditoria_inmutable"
branch_labels = None
depends_on = None

NOMBRE = "ck_pedidos_transito_sin_tracking"
NUEVA = (
    "CASE WHEN id_elemento_rastreado IS NOT NULL THEN etapa_viaje <> 'SIN_TRACKING' "
    "ELSE (etapa_viaje = 'SIN_TRACKING' OR ata_confirmada IS NOT NULL) END"
)
ANTERIOR = "(id_elemento_rastreado IS NULL) = (etapa_viaje = 'SIN_TRACKING')"


# SQL directo y no `op.drop_constraint`: la convención de nombres de `Base`
# volvería a anteponer el prefijo `ck_pedidos_transito_` al nombre completo.
def upgrade() -> None:
    op.execute(f"ALTER TABLE pedidos_transito DROP CONSTRAINT {NOMBRE}")
    op.execute(f"ALTER TABLE pedidos_transito ADD CONSTRAINT {NOMBRE} CHECK ({NUEVA})")


def downgrade() -> None:
    op.execute(f"ALTER TABLE pedidos_transito DROP CONSTRAINT {NOMBRE}")
    op.execute(f"ALTER TABLE pedidos_transito ADD CONSTRAINT {NOMBRE} CHECK ({ANTERIOR})")
