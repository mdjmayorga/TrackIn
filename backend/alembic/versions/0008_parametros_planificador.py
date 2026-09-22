"""Siembra los parámetros del planificador de consultas.

`US-07` (RF-08), primer criterio: *«dado el parámetro de frecuencia aérea,
cuando lo modifico, entonces el planificador aplica el nuevo intervalo **sin
reiniciar el servicio**»*.

Vale la misma regla que `0003` y `0004`: el código **no depende** de estas
filas. `app.services.parametros.CATALOGO` declara los mismos valores por
defecto, así que el planificador funciona con la tabla vacía. Se siembran para
que quien administre los descubra, que es la única forma de que un umbral
ajustable sea de verdad ajustable por alguien que no lee el código.

Las dos frecuencias son **provisionales**, y por motivos distintos:

- La **aérea** depende del ritmo al que ShipsGo Air refresca los hitos CIMP, y
  eso no se midió: el MAWB del spike llegó ya entregado.
- La **marítima** se fija larga a propósito. Un buque tarda semanas y sus hitos
  son escasos; consultar **no cuesta crédito** —el crédito se gasta en el
  alta—, así que el límite real es el de tasa, no el presupuesto.

`altas_maximas_dia` es el único que vigila dinero, y por eso existe: a 2 USD el
crédito y ~374 al año, veinte altas en un día son señal de que algo se está
registrando en bucle.

Revision ID: 0008_parametros_planificador
Revises: 0007_elemento_nombre_imo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_parametros_planificador"
down_revision = "0007_elemento_nombre_imo"
branch_labels = None
depends_on = None


#: Deben coincidir con `parametros.CATALOGO`. Una prueba lo verifica: si
#: divergen, el comportamiento cambiaría según hubiera corrido o no la
#: migración.
_PARAMETROS = [
    (
        "frecuencia_aerea_min",
        "60",
        "ENTERO",
        "Minutos entre consultas de un envio aereo, dentro de la ventana activa.",
    ),
    (
        "frecuencia_maritima_min",
        "360",
        "ENTERO",
        "Minutos entre consultas de un envio maritimo.",
    ),
    (
        "ventana_aerea_inicio_h",
        "6",
        "ENTERO",
        "Hora local a la que arranca la ventana activa del sondeo aereo.",
    ),
    (
        "ventana_aerea_fin_h",
        "22",
        "ENTERO",
        "Hora local a la que termina la ventana activa del sondeo aereo.",
    ),
    (
        "maduracion_reintento_s",
        "120",
        "ENTERO",
        "Segundos antes de reconsultar un embarque dado de alta pero sin datos.",
    ),
    (
        "altas_maximas_dia",
        "20",
        "ENTERO",
        "Altas diarias por encima de las cuales el planificador avisa (cuestan dinero).",
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
