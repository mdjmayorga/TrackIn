"""Inmutabilidad del historial y siembra de parámetros del sistema.

`US-04` (RF-21 / RNF-13) y RF-24.

Dos cosas que van juntas porque las dos hacen falta para que `US-04` esté
completa: el historial tiene que ser de verdad *append-only*, y el intervalo de
submuestreo tiene que poder cambiarse sin desplegar código.

**Por qué un disparador y no una comprobación en el ORM.** El criterio dice que
modificar un registro del historial se rechaza «por ser inmutable». Si eso vive
en SQLAlchemy, se cumple solo para quien pase por el modelo: un `UPDATE` desde
`psql`, desde pgAdmin o desde un `bulk_update` lo salta sin resistencia. La
inmutabilidad de una bitácora de auditoría no puede depender de por dónde entre
la escritura, así que la impone la base.

`DELETE` se bloquea igual que `UPDATE`. La política de retención de `TASK-10`
—que sí borrará, cuando exista— tendrá que desactivar el disparador
explícitamente dentro de su transacción, y eso es exactamente lo que se quiere:
que borrar historial sea un acto deliberado y no un descuido.

Revision ID: 0003_historial_inmutable
Revises: 0002_maestros_paises_destinos
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_historial_inmutable"
down_revision = "0002_maestros_paises_destinos"
branch_labels = None
depends_on = None


# El disparador vive en su propia función para poder citarla en el `DROP`.
_FUNCION = """
CREATE OR REPLACE FUNCTION historial_tracking_inmutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'historial_tracking es inmutable: % rechazado sobre la fila %',
        TG_OP, OLD.id
        USING HINT = 'La bitacora es append-only (RNF-13). Para la retencion de '
                     'TASK-10, desactivar el disparador dentro de la transaccion.',
              ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""

_DISPARADOR = """
CREATE TRIGGER trg_historial_tracking_inmutable
BEFORE UPDATE OR DELETE ON historial_tracking
FOR EACH ROW EXECUTE FUNCTION historial_tracking_inmutable();
"""

#: Se siembran para que quien administre los descubra en la tabla. El código no
#: depende de estas filas: `app.services.parametros.CATALOGO` declara el mismo
#: valor por defecto y el sistema funciona con la tabla vacía.
_PARAMETROS = [
    (
        "intervalo_minimo_persistencia_s",
        "300",
        "ENTERO",
        "Segundos minimos entre dos posiciones guardadas del mismo elemento (RNF-13).",
    ),
    (
        "radio_geocerca_km",
        "50",
        "ENTERO",
        "Radio por defecto de la geocerca de arribo (RN-05).",
    ),
    (
        "umbral_riesgo_dias",
        "2",
        "ENTERO",
        "Dias de margen por debajo de los cuales un pedido pasa a EN_RIESGO (RN-07/RN-08).",
    ),
    (
        "ventana_calidad_habiles_min",
        "7",
        "ENTERO",
        "Dias habiles minimos de la liberacion de Control de Calidad (RN-19).",
    ),
    (
        "ventana_calidad_habiles_max",
        "15",
        "ENTERO",
        "Dias habiles maximos de la liberacion de Control de Calidad (RN-19).",
    ),
    (
        "velocidad_minima_eta_nudos",
        "1.0",
        "DECIMAL",
        "Debajo de esta velocidad no se estima ETA (RN-16). Provisional.",
    ),
    (
        "velocidad_maxima_arribo_nudos",
        "3.0",
        "DECIMAL",
        "Encima de esta velocidad una nave en la geocerca no se da por arribada (RN-05). Provisional.",
    ),
]


def upgrade() -> None:
    op.execute(_FUNCION)
    op.execute(_DISPARADOR)

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
    # El disparador impide el DELETE del historial, no el de los parámetros.
    for clave, *_ in _PARAMETROS:
        conexion.execute(
            sa.text("DELETE FROM parametros_sistema WHERE clave = :clave"),
            {"clave": clave},
        )

    op.execute("DROP TRIGGER IF EXISTS trg_historial_tracking_inmutable ON historial_tracking")
    op.execute("DROP FUNCTION IF EXISTS historial_tracking_inmutable()")
