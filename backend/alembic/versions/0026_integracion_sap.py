"""Escucha de la API de SAP — `US-65` y `US-66`.

Reunión de entrega del Informe 2 (27/10/2026): dejar TrackIn listo para recibir
los pedidos de SAP el día que la API exista, con la escucha apagada.

- `cargas_ztracking` registra también los lotes de SAP: `origen` dice de dónde
  vino la carga, y `id_usuario` pasa a ser opcional porque un lote de SAP no lo
  sube una persona. Una carga del Excel sigue exigiendo usuario.
- `sap_escucha_habilitada` arranca en `false`: el Administrador la enciende desde
  la interfaz (`US-66`).

Revision ID: 0026_integracion_sap
Revises: 0025_paquetes_creditos
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_integracion_sap"
down_revision = "0025_paquetes_creditos"
branch_labels = None
depends_on = None

_CLAVE = "sap_escucha_habilitada"


def upgrade() -> None:
    op.add_column(
        "cargas_ztracking",
        sa.Column(
            "origen",
            sa.String(length=10),
            server_default="EXCEL",
            nullable=False,
            comment="EXCEL (subido por una persona) o API_SAP (US-65).",
        ),
    )
    op.create_check_constraint(
        op.f("ck_cargas_ztracking_origen"), "cargas_ztracking", "origen IN ('EXCEL', 'API_SAP')"
    )
    op.alter_column("cargas_ztracking", "id_usuario", existing_type=sa.BigInteger(), nullable=True)
    op.create_check_constraint(
        op.f("ck_cargas_ztracking_autor"),
        "cargas_ztracking",
        "origen = 'API_SAP' OR id_usuario IS NOT NULL",
    )

    op.get_bind().execute(
        sa.text(
            "INSERT INTO parametros_sistema (clave, valor, tipo_dato, descripcion) "
            "VALUES (:clave, 'false', 'BOOLEANO', :descripcion) ON CONFLICT (clave) DO NOTHING"
        ),
        {
            "clave": _CLAVE,
            "descripcion": (
                "Si TrackIn acepta los pedidos que envíe la API de SAP (US-65). Apagada hasta "
                "que la API exista; la enciende el Administrador (US-66)."
            ),
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"), {"clave": _CLAVE}
    )
    # Las cargas de SAP no tienen usuario: sin borrarlas, el NOT NULL no vuelve.
    op.execute("DELETE FROM cargas_ztracking WHERE origen = 'API_SAP'")
    op.drop_constraint(op.f("ck_cargas_ztracking_autor"), "cargas_ztracking", type_="check")
    op.alter_column("cargas_ztracking", "id_usuario", existing_type=sa.BigInteger(), nullable=False)
    op.drop_constraint(op.f("ck_cargas_ztracking_origen"), "cargas_ztracking", type_="check")
    op.drop_column("cargas_ztracking", "origen")
