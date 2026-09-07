"""Datos semilla de los maestros: países, sus alias y los destinos reales.

`TASK-29` (maestro de países y normalización) y `TASK-31` (reponer el maestro de
destinos), del Sprint 3.

**Países.** Los quince que aparecen en la muestra real del Z-tracking, más Costa
Rica. Los alias son las grafías con que el archivo los nombra —`USA` junto a
`ESTADOS UNIDOS`— ya normalizadas: mayúsculas, sin tildes y sin espacios de
sobra, para que la búsqueda sea una igualdad y no un `LIKE`.

**Destinos.** Los cuatro puntos de entrada que confirmó Planeación el
04/09/2026. El radio de la geocerca es **por destino** y no el global de 50 km:
Moín y Limón distan unos 5,5 km, así que un radio grande los solaparía y el
sistema no podría decir a cuál de los dos llegó el buque (RN-05).

El lead time queda con un **valor provisional documentado**: la duda C1 —a qué
nivel está definido— sigue abierta con Planeación, y el criterio de `TASK-31`
pide explícitamente que eso no bloquee la migración.

Revision ID: 0002_maestros_paises_destinos
Revises: 0001_esquema_inicial
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_maestros_paises_destinos"
down_revision = "0001_esquema_inicial"
branch_labels = None
depends_on = None


# (código ISO 3166-1 alfa-2, nombre, alias con que lo nombra el archivo)
PAISES: list[tuple[str, str, tuple[str, ...]]] = [
    ("IN", "India", ("INDIA",)),
    ("CN", "China", ("CHINA",)),
    ("BR", "Brasil", ("BRASIL", "BRAZIL")),
    ("ES", "España", ("ESPANA", "SPAIN")),
    ("DE", "Alemania", ("ALEMANIA", "GERMANY", "DEUTSCHLAND")),
    ("CH", "Suiza", ("SUIZA", "SWITZERLAND")),
    ("MX", "México", ("MEXICO",)),
    ("BE", "Bélgica", ("BELGICA", "BELGIUM")),
    ("GT", "Guatemala", ("GUATEMALA",)),
    ("US", "Estados Unidos", ("ESTADOS UNIDOS", "USA", "EEUU", "EE UU", "UNITED STATES")),
    ("IT", "Italia", ("ITALIA", "ITALY")),
    ("AT", "Austria", ("AUSTRIA",)),
    ("FR", "Francia", ("FRANCIA", "FRANCE")),
    ("HU", "Hungría", ("HUNGRIA", "HUNGARY")),
    ("CR", "Costa Rica", ("COSTA RICA",)),
]

# (código, nombre, vía, longitud, latitud, radio km, lead time días, observación)
DESTINOS: list[tuple[str, str, str, float, float, int, int, str]] = [
    (
        "CRMOB",
        "Moín",
        "MARITIMO",
        -83.0800,
        10.0000,
        2,
        5,
        "Terminal de contenedores del Caribe. Radio reducido a 2 km: Limón está "
        "a unos 5,5 km y con el radio global de 50 km ambas geocercas se "
        "solaparían. Lead time PROVISIONAL, pendiente de la duda C1.",
    ),
    (
        "CRLIO",
        "Puerto Limón",
        "MARITIMO",
        -83.0311,
        9.9908,
        2,
        5,
        "Instalación distinta de Moín, a unos 5,5 km. Radio reducido por la "
        "misma razón. Lead time PROVISIONAL, pendiente de la duda C1.",
    ),
    (
        "CRCAL",
        "Puerto Caldera",
        "MARITIMO",
        -84.7203,
        9.9139,
        10,
        5,
        "Costa del Pacífico, sin puerto vecino con el que confundirse, por eso "
        "admite un radio mayor. Su cobertura AIS se verifica en TASK-28. "
        "Lead time PROVISIONAL, pendiente de la duda C1.",
    ),
    (
        "MROC",
        "Aeropuerto Juan Santamaría",
        "AEREO",
        -84.2088,
        9.9939,
        5,
        2,
        "Código IATA SJO. Única vía aérea de entrada. Lead time PROVISIONAL, "
        "pendiente de la duda C1.",
    ),
]


def upgrade() -> None:
    conexion = op.get_bind()

    for codigo, nombre, alias in PAISES:
        id_pais = conexion.execute(
            sa.text(
                "INSERT INTO maestro_paises (codigo, nombre) "
                "VALUES (:codigo, :nombre) RETURNING id"
            ),
            {"codigo": codigo, "nombre": nombre},
        ).scalar_one()
        for grafia in alias:
            conexion.execute(
                sa.text(
                    "INSERT INTO alias_paises (id_pais, alias) VALUES (:id, :alias)"
                ),
                {"id": id_pais, "alias": grafia},
            )

    for codigo, nombre, via, lon, lat, radio, lead, observacion in DESTINOS:
        conexion.execute(
            sa.text(
                "INSERT INTO maestro_destinos "
                "(codigo, nombre, pais, via_transporte, ubicacion, "
                " radio_geocerca_km, lead_time_dias, observacion) "
                "VALUES (:codigo, :nombre, 'CR', :via, "
                " ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, "
                " :radio, :lead, :observacion)"
            ),
            {
                "codigo": codigo,
                "nombre": nombre,
                "via": via,
                "lon": lon,
                "lat": lat,
                "radio": radio,
                "lead": lead,
                "observacion": observacion,
            },
        )


def downgrade() -> None:
    conexion = op.get_bind()
    conexion.execute(
        sa.text("DELETE FROM maestro_destinos WHERE codigo IN :codigos").bindparams(
            sa.bindparam("codigos", [d[0] for d in DESTINOS], expanding=True)
        )
    )
    # `alias_paises` cae por el ON DELETE CASCADE del FK.
    conexion.execute(
        sa.text("DELETE FROM maestro_paises WHERE codigo IN :codigos").bindparams(
            sa.bindparam("codigos", [p[0] for p in PAISES], expanding=True)
        )
    )
