"""El aviso de altas se ajusta al presupuesto que existe — `US-45` / `US-07`.

La migración `0008` sembró `altas_maximas_dia` en **20** con un razonamiento
hipotético: a 2 USD el crédito, veinte altas en un día olían a un registro en
bucle. Entonces no había presupuesto y el número era una intuición.

Ahora hay uno. Planificación compró **50 créditos** el 23/09/2026, con 150 más
previstos para diciembre. Contra 50 créditos, veinte altas en un día son el
**40 % del presupuesto**: el umbral avisaría cuando ya casi no queda nada que
proteger. Baja a **5**, que es el 10 %.

Por qué el número sale del presupuesto y no del ritmo de trabajo
-----------------------------------------------------------------

Podría argumentarse que cinco es poco: hoy el archivo entrega 110 líneas
marítimas, y si mañana llegaran con referencia habría que dar de alta más de
cinco en un día para ponerse al día. Es cierto, y aun así el umbral **no avisa
del ritmo, avisa del gasto**. Un día de 110 altas cuesta 220 USD y agota el
presupuesto más de dos veces; que eso levante la mano es exactamente lo que se
quiere, aunque sea deliberado.

Cuando entren los 150 de diciembre este valor vuelve a quedar chico, y se
cambia donde se tiene que cambiar: en `parametros_sistema`, editable sin
desplegar (`US-13`). Esta migración fija el punto de partida, no la política.

El identificador va corto a propósito: `alembic_version.version_num` es
`varchar(32)` y un `revision` más largo revienta al aplicar la migración,
no al escribirla.

Revision ID: 0011_altas_maximas_presupuesto
Revises: 0010_lead_time_aereo_real
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_altas_maximas_presupuesto"
down_revision = "0010_lead_time_aereo_real"
branch_labels = None
depends_on = None

_CLAVE = "altas_maximas_dia"
_ANTERIOR = "20"
_NUEVO = "5"

_DESCRIPCION = (
    "Altas diarias por encima de las cuales el planificador avisa (cuestan dinero). "
    "Fijado en 5 el 24/09/2026: es el 10% de los 50 creditos comprados."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE parametros_sistema "
            "SET valor = :nuevo, descripcion = :descripcion "
            "WHERE clave = :clave"
        ),
        {"nuevo": _NUEVO, "descripcion": _DESCRIPCION, "clave": _CLAVE},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE parametros_sistema SET valor = :anterior WHERE clave = :clave"),
        {"anterior": _ANTERIOR, "clave": _CLAVE},
    )
