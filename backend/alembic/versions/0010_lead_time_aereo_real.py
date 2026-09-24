"""El aeropuerto también son 7 días — RN-01.

La migración `0009` subió los tres puertos de 5 a 7 días y dejó el aeropuerto en
2, porque la respuesta de Planificación no distinguía la vía y subirlo por
analogía habría sido inventar el dato.

Planificación lo aclaró el 23/09/2026: **los 7 días son para las dos vías**, y
son una **media que ya contempla el riesgo** —accidentes en carretera, permisos
de salud—, no el caso sin trabas. Puede durar más o menos; 7 es el centro.

Por qué eso importa más allá del número
----------------------------------------

Que la media **incluya** el riesgo la vuelve un estimador sin sesgo, que es lo
que RN-01 necesita: una fecha proyectada que se equivoque hacia los dos lados
por igual. Si los 7 días hubieran sido el caso limpio, la fecha se habría
quedado corta siempre en la misma dirección, y un sistema que falla siempre
hacia el mismo lado enseña a desconfiar de él.

Lo que queda abierto es la **dispersión**, no el centro: `umbral_riesgo_dias`
—hoy 2 días— es lo que absorbe esa varianza en el semáforo. Si la cola real es
bastante mayor que dos días, el estado va a oscilar entre `A_TIEMPO` y
`EN_RIESGO` sin que pase nada nuevo. Se mide cuando haya histórico y se ajusta
el parámetro, sin desplegar.

Revision ID: 0010_lead_time_aereo_real
Revises: 0009_lead_time_maritimo_real
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_lead_time_aereo_real"
down_revision = "0009_lead_time_maritimo_real"
branch_labels = None
depends_on = None

_AEROPUERTO = "MROC"
_ANTERIOR = 2
_NUEVO = 7


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE maestro_destinos "
            "SET lead_time_dias = :nuevo, "
            "    observacion = replace(observacion, "
            "        'Lead time PROVISIONAL, pendiente de la duda C1.', "
            "        'Lead time de 7 dias, igual que los puertos: media de puerto a "
            "planta confirmada por Planificacion el 23/09/2026, con el riesgo de "
            "accidentes y permisos ya contemplado.') "
            "WHERE codigo = :codigo"
        ),
        {"nuevo": _NUEVO, "codigo": _AEROPUERTO},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE maestro_destinos SET lead_time_dias = :anterior WHERE codigo = :codigo"),
        {"anterior": _ANTERIOR, "codigo": _AEROPUERTO},
    )
