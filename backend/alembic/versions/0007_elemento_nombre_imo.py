"""Nombre e IMO de la nave rastreada — `US-45`, y deuda de `US-02`.

Dos historias han chocado con el mismo hueco, y la segunda lo vuelve
bloqueante:

- **`US-02`, cerrada el 08/09.** `colector_ais._aplicar_estatico` lo dejó
  escrito: *«no hay columna para el nombre del buque, ni para el IMO, ni para el
  destino»*. Se aceptó como deuda porque el mensaje estático de AIS traía la ETA,
  que sí tenía dónde ir.
- **`US-45`.** Su criterio es explícito: *«dada una respuesta con buque, cuando
  la proceso, entonces relleno `elementos_rastreados` con nombre e IMO»*. Y
  ShipsGo los entrega en los tres embarques marítimos medidos, siempre.

Aguas abajo hay dos consumidores esperando: la información emergente de los
marcadores del mapa (`US-27`) y el detalle del pedido (`US-44`). Ninguno de los
dos puede mostrar «va en el MAERSK CHACHAI» leyendo un JSONB del historial.

**El destino declarado sigue sin columna, y es deliberado.** AIS lo trae como
texto libre que escribe la tripulación —`"CRMOB"`, `"MOIN CR"`, `"COSTA RICA"`—
y no es el destino del pedido, que vive en `maestro_destinos` y es dato
verificado. Guardarlo invitaría a confundirlos.

`imo` va como `INTEGER` y no como texto: son siete dígitos con su propio dígito
verificador, y ShipsGo ya lo entrega numérico (`9525388`).

Revision ID: 0007_elemento_nombre_imo
Revises: 0006_eta_declarada
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_elemento_nombre_imo"
down_revision = "0006_eta_declarada"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "elementos_rastreados",
        sa.Column(
            "nombre",
            sa.String(length=120),
            nullable=True,
            comment="Nombre de la nave o vuelo, tal como lo reporta la fuente.",
        ),
    )
    op.add_column(
        "elementos_rastreados",
        sa.Column(
            "imo",
            sa.Integer(),
            nullable=True,
            comment="Identificador OMI de la nave (siete dígitos). Solo vía marítima.",
        ),
    )


def downgrade() -> None:
    op.drop_column("elementos_rastreados", "imo")
    op.drop_column("elementos_rastreados", "nombre")
