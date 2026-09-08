"""Siembra los umbrales de la política de resiliencia.

`US-03` (RF-09 / RNF-12), sexto criterio: los umbrales de reintento tienen que
poder ajustarse **sin desplegar código**.

Vale la misma regla que estableció `0003`: el código **no depende** de estas
filas. `app.services.parametros.CATALOGO` declara los mismos valores por
defecto, así que el sistema arranca y reintenta correctamente con la tabla
vacía. Se siembran para que quien administre los descubra, que es la única
forma de que un umbral ajustable sea de verdad ajustable por alguien que no
lee el código.

Los cinco valores son **provisionales a propósito**. El bueno de cada uno
depende del proveedor que termine contratándose —Vizion y Portcast tienen sus
propios límites de tasa, y AISStream no tiene ninguno—, y eso se sabrá cuando
cierre `TASK-28`. Que sean parámetros es justamente lo que permite afinarlos
entonces sin tocar el código ni volver a desplegar.

Revision ID: 0004_parametros_resiliencia
Revises: 0003_historial_inmutable
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_parametros_resiliencia"
down_revision = "0003_historial_inmutable"
branch_labels = None
depends_on = None


#: Deben coincidir con `parametros.CATALOGO`. Una prueba lo verifica: si
#: divergen, el comportamiento cambiaría según hubiera corrido o no la
#: migración, que es exactamente el fallo que la prueba de `0003` ya impide.
_PARAMETROS = [
    (
        "resiliencia_espera_inicial_s",
        "5",
        "ENTERO",
        "Segundos de espera antes del primer reintento a una fuente externa (RF-09).",
    ),
    (
        "resiliencia_factor_espera",
        "2.0",
        "DECIMAL",
        "Factor de crecimiento de la espera entre reintentos consecutivos.",
    ),
    (
        "resiliencia_espera_maxima_s",
        "300",
        "ENTERO",
        "Tope de la espera creciente entre reintentos.",
    ),
    (
        "resiliencia_intentos_maximos",
        "5",
        "ENTERO",
        "Fallos transitorios seguidos tras los cuales la fuente queda degradada.",
    ),
    (
        "resiliencia_ruido_espera",
        "0.2",
        "DECIMAL",
        "Fraccion de la espera repartida al azar para dispersar los reintentos.",
    ),
]


def upgrade() -> None:
    conexion = op.get_bind()
    for clave, valor, tipo_dato, descripcion in _PARAMETROS:
        conexion.execute(
            sa.text(
                "INSERT INTO parametros_sistema (clave, valor, tipo_dato, descripcion) "
                "VALUES (:clave, :valor, :tipo_dato, :descripcion) "
                "ON CONFLICT (clave) DO NOTHING"
            ),
            {
                "clave": clave,
                "valor": valor,
                "tipo_dato": tipo_dato,
                "descripcion": descripcion,
            },
        )


def downgrade() -> None:
    conexion = op.get_bind()
    for clave, *_ in _PARAMETROS:
        conexion.execute(
            sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"),
            {"clave": clave},
        )
