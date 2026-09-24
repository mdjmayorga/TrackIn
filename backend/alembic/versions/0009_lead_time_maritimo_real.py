"""El lead time de puerto a planta deja de ser provisional — RN-01.

La migración `0002` sembró los cuatro destinos con lead times marcados
**PROVISIONAL, pendiente de la duda C1**. Planificación respondió el
23/09/2026: el tiempo medio de puerto a planta que manejan es de **una
semana**.

Los tres puertos pasan de 5 a **7 días**.

Qué NO se toca, y por qué
--------------------------

**El aeropuerto se queda en 2 días.** La respuesta habló del lead time en
general y no distinguió la vía, y las dos lecturas son defendibles: el permiso
sanitario no depende del modo —lo que empujaría el aéreo también a 7—, pero el
aéreo suele elegirse por urgencia y podría ir más rápido. Subirlo por analogía
sería inventar un dato que nadie dio. Queda como pregunta abierta y con su
valor provisional hasta que se confirme.

La varianza que la respuesta trae consigo
------------------------------------------

Planificación nombró accidentes en carretera y permisos de salud como factores.
Eso significa que 7 es una **media con cola**, y RN-01 produce una fecha
concreta contra la que alguien va a planificar producción. Queda por confirmar
si los 7 días incluyen la espera del permiso sanitario o son el caso sin
trabas: si lo excluyen y el permiso es lo que manda, la fecha proyectada se
quedará corta de forma sistemática.

Mientras tanto el valor vive donde tiene que vivir: en el maestro, editable sin
desplegar (`US-13`), y cada pedido guarda el que **usó** en su último recálculo
(`lead_time_destino_dias`), así que cambiarlo no reescribe desgloses ya hechos.

Revision ID: 0009_lead_time_maritimo_real
Revises: 0008_parametros_planificador
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_lead_time_maritimo_real"
down_revision = "0008_parametros_planificador"
branch_labels = None
depends_on = None

#: Los tres puertos. El aeropuerto (`MROC`) queda fuera a propósito.
_PUERTOS = ("CRMOB", "CRLIO", "CRCAL")

_ANTERIOR = 5
_NUEVO = 7


def upgrade() -> None:
    conexion = op.get_bind()
    conexion.execute(
        sa.text(
            "UPDATE maestro_destinos "
            "SET lead_time_dias = :nuevo, "
            "    observacion = replace(observacion, "
            "        'Lead time PROVISIONAL, pendiente de la duda C1.', "
            "        'Lead time de 7 dias: media de puerto a planta confirmada por "
            "Planificacion el 23/09/2026. Varianza por accidentes en carretera y "
            "permisos de salud.') "
            "WHERE codigo IN :codigos"
        ).bindparams(sa.bindparam("codigos", _PUERTOS, expanding=True)),
        {"nuevo": _NUEVO},
    )


def downgrade() -> None:
    conexion = op.get_bind()
    conexion.execute(
        sa.text(
            "UPDATE maestro_destinos SET lead_time_dias = :anterior WHERE codigo IN :codigos"
        ).bindparams(sa.bindparam("codigos", _PUERTOS, expanding=True)),
        {"anterior": _ANTERIOR},
    )
