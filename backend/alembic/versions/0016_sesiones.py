"""Sesiones y bloqueo por intentos — `US-42` / RNF-05, RNF-24.

Las sesiones viven en la base y no en un JWT, por tres criterios de `US-42`:

- **Cierre por inactividad.** Un JWT no sabe cuándo se usó por última vez; una
  fila con `ultimo_uso` sí.
- **Cuenta compartida.** `compras@gutis.com` la usan varias personas a la vez
  (decisión del 30/09/2026): cada una tiene su sesión, y cerrar una no cierra
  las demás.
- **Revocación.** Desactivar un usuario tiene que cortar sus sesiones ya
  abiertas, cosa que un token firmado no permite hasta que expira.

Se guarda el **hash** del token, nunca el token: quien lea la tabla no puede
suplantar a nadie.

Revision ID: 0016_sesiones
Revises: 0015_destino_nombre_unico
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

#: Los cuatro parámetros de la sesión (`services/parametros.py`). Se siembran
#: para que quien administra los encuentre en la tabla sin leer el código.
_PARAMETROS = (
    (
        "login_intentos_maximos",
        "5",
        "ENTERO",
        "Intentos fallidos seguidos antes de bloquear la cuenta unos minutos.",
    ),
    ("login_bloqueo_min", "15", "ENTERO", "Minutos que dura el bloqueo por intentos fallidos."),
    (
        "sesion_inactividad_min",
        "30",
        "ENTERO",
        "Minutos sin actividad tras los que se cierra la sesión.",
    ),
    ("sesion_recordada_dias", "30", "ENTERO", "Duración de una sesión con «Recordar sesión»."),
)

revision = "0016_sesiones"
down_revision = "0015_destino_nombre_unico"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "intentos_fallidos",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Intentos fallidos seguidos; vuelve a 0 al entrar bien (US-42).",
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "bloqueado_hasta",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Hasta cuándo no se admite el ingreso tras superar los intentos.",
        ),
    )
    op.create_check_constraint(
        "ck_usuarios_intentos_fallidos", "usuarios", "intentos_fallidos >= 0"
    )

    op.create_table(
        "sesiones",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("id_usuario", sa.BigInteger(), nullable=False),
        sa.Column("hash_token", sa.String(length=64), nullable=False),
        sa.Column("recordada", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultimo_uso", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_usuario"],
            ["usuarios.id"],
            name=op.f("fk_sesiones_id_usuario_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sesiones")),
        sa.UniqueConstraint("hash_token", name=op.f("uq_sesiones_hash_token")),
        comment="Sesiones abiertas por el login (US-42). Se guarda el hash del token.",
    )
    op.create_index("ix_sesiones_id_usuario", "sesiones", ["id_usuario"])

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
    for clave, *_ in _PARAMETROS:
        conexion.execute(
            sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"), {"clave": clave}
        )
    op.drop_index("ix_sesiones_id_usuario", table_name="sesiones")
    op.drop_table("sesiones")
    op.drop_constraint("ck_usuarios_intentos_fallidos", "usuarios", type_="check")
    op.drop_column("usuarios", "bloqueado_hasta")
    op.drop_column("usuarios", "intentos_fallidos")
