"""La ETA que viene declarada en el archivo — `US-09`.

RN-01 proyecta desde una ETA o una ATA, y `US-09` necesita que el pedido tenga
alguna. Hoy las fuentes posibles son cuatro y solo tres tenían dónde vivir:

| Fuente | Dónde vive |
|---|---|
| ATA confirmada a mano | `pedidos_transito.ata_confirmada` |
| ATA inferida por hito o geocerca | `pedidos_transito.ata_inferida` |
| ETA de la fuente de rastreo | `elementos_rastreados.eta_api` |
| **ETA declarada en el archivo** | **no existía** |

La cuarta no cabía en ninguna de las otras. `eta_api` cuelga del elemento
rastreado, y un pedido `SIN_TRACKING` no tiene elemento — que es justamente el
caso de las 82 líneas que hoy entran. Y `eta_utilizada` es otra cosa: es la
**instantánea de la que se usó** en el último recálculo, la escribe `US-09` y
confundirla con un dato de entrada haría que una recarga del archivo pisara el
desglose de un cálculo ya hecho.

> **Medido sobre la muestra del 03/09, y conviene no hacerse ilusiones:** la
> columna `ETA CR` trae una fecha usable en **18 de 429 líneas**. Las demás
> vienen vacías (264), con `PENDIENTE` (131) o con `N/A` (12). La columna
> existe, se ingesta y se audita; lo que no hay es el dato. Es el argumento más
> concreto a favor de contratar la fuente comercial, y el motivo de que `US-09`
> señale «sin fecha base» en vez de inventar una.

Va **sin índice** a propósito: no se filtra ni se ordena por ella. Lo que el
dashboard consulta es `fecha_proyectada_disponible`, que ya lo tiene.

Revision ID: 0006_eta_declarada
Revises: 0005_presencia_en_la_carga
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_eta_declarada"
down_revision = "0005_presencia_en_la_carga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pedidos_transito",
        sa.Column(
            "eta_declarada",
            sa.Date(),
            nullable=True,
            comment=(
                "ETA tal como la declara el archivo de Logística (columna "
                "'ETA CR'). Última en la precedencia de RN-14: la mantiene una "
                "persona a mano y es justo lo que TrackIn viene a reemplazar."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("pedidos_transito", "eta_declarada")
