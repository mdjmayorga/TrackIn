"""Los países de tránsito en el maestro — la línea de tiempo en castellano.

Los hitos del viaje (`US-29`) dicen el país de cada escala con el nombre del
maestro, y si no lo tiene, con el de ShipsGo, en inglés: «Panama», «Peru». El
maestro tenía solo los países de los proveedores (`0002`). Se agregan los de
las escalas habituales de las rutas a Costa Rica, marítimas y aéreas: los que
ya aparecieron (Colombia, Panamá y Perú, 03/11/2026) y los hubs de carga
frecuentes, para no tener que volver a tocarlo con cada escala nueva.

Son países reales: también valen como país de origen si un proveedor lo es.

Revision ID: 0033_paises_de_transito
Revises: 0032_trayecto_maritimo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033_paises_de_transito"
down_revision = "0032_trayecto_maritimo"
branch_labels = None
depends_on = None

PAISES: tuple[tuple[str, str], ...] = (
    # América: los puertos de transbordo del Caribe y del Pacífico.
    ("PA", "Panamá"),
    ("CO", "Colombia"),
    ("PE", "Perú"),
    ("CL", "Chile"),
    ("EC", "Ecuador"),
    ("SV", "El Salvador"),
    ("HN", "Honduras"),
    ("NI", "Nicaragua"),
    ("JM", "Jamaica"),
    ("DO", "República Dominicana"),
    ("BS", "Bahamas"),
    ("CA", "Canadá"),
    # Europa: puertos y hubs de carga aérea.
    ("NL", "Países Bajos"),
    ("GB", "Reino Unido"),
    ("PT", "Portugal"),
    ("LU", "Luxemburgo"),
    ("TR", "Turquía"),
    # Asia y Medio Oriente: hubs de carga aérea y de transbordo.
    ("AE", "Emiratos Árabes Unidos"),
    ("QA", "Catar"),
    ("SG", "Singapur"),
    ("HK", "Hong Kong"),
    ("KR", "Corea del Sur"),
    ("JP", "Japón"),
    ("TW", "Taiwán"),
    ("MY", "Malasia"),
)


def upgrade() -> None:
    conexion = op.get_bind()
    for codigo, nombre in PAISES:
        conexion.execute(
            sa.text(
                "INSERT INTO maestro_paises (codigo, nombre) VALUES (:codigo, :nombre) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"codigo": codigo, "nombre": nombre},
        )


def downgrade() -> None:
    # Solo los que ningún pedido usa como país de origen.
    op.get_bind().execute(
        sa.text(
            "DELETE FROM maestro_paises m WHERE m.codigo = ANY(:codigos) "
            "AND NOT EXISTS (SELECT 1 FROM pedidos_transito p WHERE p.id_pais_origen = m.id)"
        ),
        {"codigos": [codigo for codigo, _ in PAISES]},
    )
