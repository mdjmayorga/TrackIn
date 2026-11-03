"""Une los embarques repetidos en `elementos_rastreados` — 03/11/2026.

    python scripts/unir_elementos_duplicados.py --ensayo     # muestra, aplica y revierte
    python scripts/unir_elementos_duplicados.py              # une y guarda

Hasta el 03/11/2026, `asociacion.obtener_o_crear_elemento` reutilizaba un
elemento solo si estaba activo. Un BL que ya había llegado queda inactivo, y al
volver a asociarlo —una corrección de referencia, otra carga del Z-tracking— se
creaba una fila nueva con el mismo número: `MAEU274029064` y `COSU6508789000`
quedaron dos veces, y el mapa los dibujaba como dos embarques en el mismo lugar.

Por cada referencia repetida (BL, contenedor, booking, guía; no MMSI ni ICAO24,
que sí se reciclan) se queda con **la fila de la lectura más reciente** de la
fuente, le pasa los pedidos, los tramos, el historial de posiciones y los
transbordos de las otras, y borra las otras. Si alguna estaba activa, la que
queda también lo está.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, exists, func, select, update  # noqa: E402
from sqlalchemy.orm import aliased  # noqa: E402

from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402
from app.models.elemento_rastreado import ElementoRastreado  # noqa: E402
from app.models.historial_tracking import HistorialTracking  # noqa: E402
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado  # noqa: E402
from app.models.pedido_transito import PedidoTransito  # noqa: E402
from app.models.transbordo import Transbordo  # noqa: E402

#: Los identificadores de un vehículo se reciclan: dos filas pueden ser legítimas.
RECICLABLES = ("MMSI", "ICAO24")

#: Las tablas que apuntan a un elemento, su columna y lo que es único por
#: elemento: la misma lectura o el mismo transbordo, registrados en las dos
#: copias, quedan una sola vez.
REFERENCIAS = (
    (PedidoTransito, PedidoTransito.id_elemento_rastreado, ()),
    (PedidoElementoRastreado, PedidoElementoRastreado.id_elemento_rastreado, ()),
    (
        HistorialTracking,
        HistorialTracking.id_elemento_rastreado,
        (HistorialTracking.fecha_registro,),
    ),
    (
        Transbordo,
        Transbordo.id_elemento_rastreado,
        (Transbordo.vehiculo_anterior, Transbordo.vehiculo_nuevo),
    ),
)


def _la_que_queda(filas: list[ElementoRastreado]) -> ElementoRastreado:
    """La de la lectura más reciente; sin lecturas, la más nueva."""
    return max(
        filas,
        key=lambda e: (
            e.ultima_actualizacion_api is not None,
            e.ultima_actualizacion_api or e.creado_en,
            e.id,
        ),
    )


async def principal(ensayo: bool) -> int:
    async with AsyncSessionLocal() as sesion:
        await sesion.begin()
        repetidas = (
            select(ElementoRastreado.tipo_tracking_externo, ElementoRastreado.tracking_externo)
            .where(ElementoRastreado.tipo_tracking_externo.not_in(RECICLABLES))
            .group_by(ElementoRastreado.tipo_tracking_externo, ElementoRastreado.tracking_externo)
            .having(func.count() > 1)
        )
        claves = set((await sesion.execute(repetidas)).tuples().all())
        grupos: dict[tuple[str, str], list[ElementoRastreado]] = defaultdict(list)
        for elemento in await sesion.scalars(
            select(ElementoRastreado).where(
                ElementoRastreado.tipo_tracking_externo.not_in(RECICLABLES)
            )
        ):
            clave = (elemento.tipo_tracking_externo, elemento.tracking_externo)
            if clave in claves:
                grupos[clave].append(elemento)

        if not grupos:
            print("No hay embarques repetidos.")
        for (tipo, numero), filas in sorted(grupos.items()):
            queda = _la_que_queda(filas)
            sobran = [e for e in filas if e.id != queda.id]
            activo = any(e.activo for e in filas)
            movidos: list[str] = []
            for elemento in sobran:
                # El índice único es *mientras esté activo*: primero se apagan.
                elemento.activo = False
            await sesion.flush()
            for modelo, columna, unicos in REFERENCIAS:
                if unicos:
                    # Lo que la que queda ya tiene se borra en vez de moverse.
                    propia = aliased(modelo)
                    repetidos = await sesion.execute(
                        delete(modelo).where(
                            columna.in_([e.id for e in sobran]),
                            exists().where(
                                getattr(propia, columna.key) == queda.id,
                                *(getattr(propia, u.key) == u for u in unicos),
                            ),
                        )
                    )
                    if repetidos.rowcount:
                        movidos.append(f"{repetidos.rowcount} {modelo.__tablename__} repetidos")
                resultado = await sesion.execute(
                    update(modelo)
                    .where(columna.in_([e.id for e in sobran]))
                    .values({columna.key: queda.id})
                )
                if resultado.rowcount:
                    movidos.append(f"{resultado.rowcount} {modelo.__tablename__}")
            await sesion.execute(
                delete(ElementoRastreado).where(ElementoRastreado.id.in_([e.id for e in sobran]))
            )
            queda.activo = activo
            await sesion.flush()
            print(
                f"  {tipo} {numero}: queda {queda.id}, se borran "
                f"{', '.join(str(e.id) for e in sobran)} · movido: {', '.join(movidos) or 'nada'}"
                f"{' · activo' if activo else ''}"
            )

        print(f"{len(grupos)} referencia(s) unida(s).")
        if ensayo:
            await sesion.rollback()
            print("Ensayo: no se guardó nada.")
        else:
            await sesion.commit()
            print("Guardado.")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.WARNING)
    # En desarrollo el engine va con `echo=True`: sin esto, el SQL tapa el informe.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ensayo", action="store_true", help="muestra, aplica y revierte")
    sys.exit(asyncio.run(principal(parser.parse_args().ensayo)))
