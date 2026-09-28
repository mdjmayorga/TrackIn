"""Guías hijas rastreadas por la aduana (TICA) — `US-49`.

Gutis recibe la guía hija (HAWB) del agente de carga, y ninguna fuente comercial
la sigue: la aerolínea solo conoce la guía madre. El 28/09/2026 se comprobó que
la consulta pública de TICA sí la encuentra en el manifiesto de carga y
devuelve la llegada real a Costa Rica y la guía madre.

Tres cambios:

1. `HAWB` entra al CHECK de `elementos_rastreados.tipo_tracking_externo`.
2. `elementos_rastreados` gana `guia_madre`, `manifiesto_aduana` y
   `payload_aduana`. El payload no puede ir a `historial_tracking`, que exige
   coordenadas, y TICA no las da.
3. Se siembran `frecuencia_tica_min` y `ventana_tica_dias`, con los mismos
   valores que `parametros.CATALOGO`.

Revision ID: 0012_guia_hija_tica
Revises: 0011_altas_maximas_presupuesto
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_guia_hija_tica"
down_revision = "0011_altas_maximas_presupuesto"
branch_labels = None
depends_on = None

_TABLA = "elementos_rastreados"
_CHECK = "ck_elementos_rastreados_tipo_tracking"
_TIPOS_ANTES = ("MMSI", "IMO", "BUQUE", "VUELO", "CONTENEDOR", "BL", "BOOKING", "MAWB")
_TIPOS_DESPUES = (*_TIPOS_ANTES, "HAWB")

#: Deben coincidir con `parametros.CATALOGO`.
_PARAMETROS = [
    (
        "frecuencia_tica_min",
        "360",
        "ENTERO",
        "Minutos entre consultas a TICA de una misma guia hija.",
    ),
    (
        "ventana_tica_dias",
        "60",
        "ENTERO",
        "Dias hacia atras en que se busca el arribo de una guia en TICA.",
    ),
]


def _check(tipos: tuple[str, ...]) -> str:
    return "tipo_tracking_externo IN (" + ", ".join(f"'{t}'" for t in tipos) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(_CHECK), _TABLA, type_="check")
    op.create_check_constraint(op.f(_CHECK), _TABLA, _check(_TIPOS_DESPUES))

    op.add_column(_TABLA, sa.Column("guia_madre", sa.String(length=25), nullable=True))
    op.add_column(_TABLA, sa.Column("manifiesto_aduana", sa.String(length=30), nullable=True))
    op.add_column(
        _TABLA,
        sa.Column("payload_aduana", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    conexion = op.get_bind()
    for clave, valor, tipo_dato, descripcion in _PARAMETROS:
        conexion.execute(
            sa.text(
                "INSERT INTO parametros_sistema (clave, valor, tipo_dato, descripcion) "
                "VALUES (:clave, :valor, :tipo_dato, :descripcion) "
                "ON CONFLICT (clave) DO NOTHING"
            ),
            {"clave": clave, "valor": valor, "tipo_dato": tipo_dato, "descripcion": descripcion},
        )


def downgrade() -> None:
    conexion = op.get_bind()
    # Un HAWB registrado haría fallar el CHECK viejo. Borrarlo perdería la traza
    # de lo rastreado y rompería las claves foráneas de los pedidos, así que la
    # reversión se niega y pide resolverlo a mano.
    hawb = conexion.scalar(
        sa.text(f"SELECT count(*) FROM {_TABLA} WHERE tipo_tracking_externo = 'HAWB'")
    )
    if hawb:
        raise RuntimeError(
            f"Hay {hawb} guías hijas registradas; reasígnelas antes de revertir 0012."
        )

    for clave, *_ in _PARAMETROS:
        conexion.execute(
            sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"), {"clave": clave}
        )

    op.drop_column(_TABLA, "payload_aduana")
    op.drop_column(_TABLA, "manifiesto_aduana")
    op.drop_column(_TABLA, "guia_madre")

    op.drop_constraint(op.f(_CHECK), _TABLA, type_="check")
    op.create_check_constraint(op.f(_CHECK), _TABLA, _check(_TIPOS_ANTES))
