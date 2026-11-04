"""Cierre de los pedidos sin referencia de embarque — 04/11/2026.

Pedido del supervisor: un pedido sin BL, contenedor, booking ni guía aérea no se
puede seguir, y varios que ya habían llegado a planta seguían en el panel como
«Sin tracking». Desde ahora la carga rechaza la línea que no trae referencia, y
una carga completa cierra los pedidos activos que siguen sin una, con el motivo
`SIN_REFERENCIA` (estado `CERRADO`).

Revision ID: 0034_cierre_sin_referencia
Revises: 0033_paises_de_transito
"""

from __future__ import annotations

from alembic import op

revision = "0034_cierre_sin_referencia"
down_revision = "0033_paises_de_transito"
branch_labels = None
depends_on = None

_RESTRICCION = "ck_pedidos_transito_motivo_cierre"
_MOTIVOS = "'RECEPCION_CONFORME', 'CIERRE_FORZADO', 'CANCELACION'"


def upgrade() -> None:
    op.drop_constraint(op.f(_RESTRICCION), "pedidos_transito", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION),
        "pedidos_transito",
        f"motivo_cierre IS NULL OR motivo_cierre IN ({_MOTIVOS}, 'SIN_REFERENCIA')",
    )


def downgrade() -> None:
    # Los cerrados por falta de referencia vuelven a quedar activos: el motivo ya
    # no existiría.
    op.execute(
        "UPDATE pedidos_transito SET motivo_cierre = NULL, estado_calculado = etapa_viaje "
        "WHERE motivo_cierre = 'SIN_REFERENCIA'"
    )
    op.drop_constraint(op.f(_RESTRICCION), "pedidos_transito", type_="check")
    op.create_check_constraint(
        op.f(_RESTRICCION),
        "pedidos_transito",
        f"motivo_cierre IS NULL OR motivo_cierre IN ({_MOTIVOS})",
    )
