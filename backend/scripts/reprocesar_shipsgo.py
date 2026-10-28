"""Vuelve a leer de ShipsGo los embarques ya arribados — `US-30`, `US-26`.

    python scripts/reprocesar_shipsgo.py --ensayo     # lee, aplica y revierte
    python scripts/reprocesar_shipsgo.py              # lee y guarda

El worker deja de consultar un embarque cuando arriba (`activo = false`), para no
gastar consultas en lo terminado. Por eso lo que se agrega al colector **después**
de que un embarque arribó —los transbordos de `US-30`, el trayecto aéreo de
`US-26`— nunca le llega: su última lectura fue con el código anterior, y
`historial_tracking` no guardó el payload si la lectura vino sin posición.

Este script los pasa una vez por el mismo `colector_shipsgo.procesar` que usa el
worker. **Leer es gratis en ShipsGo** (solo el alta cuesta crédito). No reactiva
nada ni recalcula pedidos: solo completa lo que el colector guarda del embarque.
Solo toma los embarques que están en la cuenta de ShipsGo.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402
from app.models.elemento_rastreado import ElementoRastreado  # noqa: E402
from app.services import transbordos  # noqa: E402
from app.services.rastreo import colector_shipsgo, transporte_http  # noqa: E402
from app.services.rastreo.indice_shipsgo import clave_referencia, indice_shipsgo  # noqa: E402

#: Los tipos que sigue ShipsGo (`referencia._FUENTE_POR_TIPO`).
TIPOS_SHIPSGO = ("BL", "CONTENEDOR", "BOOKING", "MAWB")


async def principal(ensayo: bool) -> int:
    if not settings.SHIPSGO_API_TOKEN:
        print("Falta SHIPSGO_API_TOKEN en el .env del backend.", file=sys.stderr)
        return 1

    async with transporte_http.crear_cliente_http() as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, settings.SHIPSGO_API_TOKEN)
        indice = await indice_shipsgo(cliente)

        async with AsyncSessionLocal() as sesion:
            await sesion.begin()
            elementos = list(
                await sesion.scalars(
                    select(ElementoRastreado)
                    .where(
                        ElementoRastreado.activo.is_(False),
                        ElementoRastreado.tipo_tracking_externo.in_(TIPOS_SHIPSGO),
                    )
                    .order_by(ElementoRastreado.id)
                )
            )
            print(f"{len(elementos)} embarque(s) arribado(s) de ShipsGo en la base.")
            for elemento in elementos:
                registrado = indice.get(clave_referencia(elemento.tracking_externo) or "")
                etiqueta = f"{elemento.tipo_tracking_externo} {elemento.tracking_externo}"
                if registrado is None:
                    print(f"  {etiqueta}: no está en la cuenta de ShipsGo; se salta.")
                    continue
                id_embarque, aereo = registrado
                shipment = await cliente.leer(id_embarque, aereo=aereo)
                geojson = await cliente.leer_geojson(id_embarque, aereo=aereo)
                resultado = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
                hechos = await transbordos.del_elemento(sesion, elemento.id)
                detalle = (
                    "; ".join(
                        f"{t.vehiculo_anterior} -> {t.vehiculo_nuevo}"
                        f" en {t.puerto_nombre or t.puerto or '?'}"
                        f"{'' if t.ocurrido else ' (previsto)'}"
                        for t in hechos
                    )
                    or "sin transbordos"
                )
                tramos = len(elemento.trayecto_aereo or [])
                print(
                    f"  {etiqueta}: {resultado.motivo} · {detalle}"
                    + (f" · {tramos} tramo(s) de vuelo" if aereo else "")
                )

            if ensayo:
                await sesion.rollback()
                print("Ensayo: no se guardó nada.")
            else:
                await sesion.commit()
                print("Guardado.")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ensayo", action="store_true", help="aplica y revierte")
    sys.exit(asyncio.run(principal(parser.parse_args().ensayo)))
