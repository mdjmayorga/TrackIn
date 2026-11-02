"""Revisa los arribos que dio ShipsGo con la regla del destino final — 02/11/2026.

    python scripts/revisar_arribos.py --ensayo     # revisa, aplica y revierte
    python scripts/revisar_arribos.py              # revisa y guarda

Hasta el 02/11/2026 la ATA salía de la primera llegada al destino **que declara
ShipsGo** en la ruta. La guía `78469391954` (pedido 4500018865) trae solo los
vuelos Nanjing → Cantón → París, ShipsGo declara París como destino, y la
llegada a CDG la dio por arribada a Costa Rica: el pedido quedó «En destino» y
el embarque se apagó, así que el worker ya no lo iba a corregir solo.

Este script vuelve a leer cada embarque de ShipsGo con ATA —leer es gratis— y le
aplica la regla nueva (`colector_shipsgo.llegada_a_destino_final`). Si no hubo
llegada a uno de nuestros destinos:

- borra la ATA y reactiva el embarque, para que el worker lo siga;
- devuelve a «En tránsito» los pedidos que estaban «En destino» **solo por la
  fuente**: no toca los confirmados a mano, los inferidos por geocerca ni los que
  ya avanzaron (aduana, planta), que son decisiones de una persona;
- vuelve a procesar la lectura y recalcula esos pedidos.
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
from app.models.pedido_transito import PedidoTransito  # noqa: E402
from app.services import recalculo  # noqa: E402
from app.services.arribo import ETAPA_EN_DESTINO  # noqa: E402
from app.services.rastreo import colector_shipsgo, shipsgo, transporte_http  # noqa: E402
from app.services.rastreo.indice_shipsgo import buscar, indice_shipsgo  # noqa: E402

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
                        ElementoRastreado.ata_api.is_not(None),
                        ElementoRastreado.tipo_tracking_externo.in_(TIPOS_SHIPSGO),
                    )
                    .order_by(ElementoRastreado.id)
                )
            )
            print(f"{len(elementos)} embarque(s) de ShipsGo con ATA en la base.")
            revertidos = 0
            for elemento in elementos:
                etiqueta = f"{elemento.tipo_tracking_externo} {elemento.tracking_externo}"
                registrado = buscar(indice, elemento.tracking_externo)
                if registrado is None:
                    print(f"  {etiqueta}: no está en la cuenta de ShipsGo; se salta.")
                    continue
                id_embarque, aereo = registrado
                shipment = await cliente.leer(id_embarque, aereo=aereo)
                geojson = await cliente.leer_geojson(id_embarque, aereo=aereo)
                lectura = shipsgo.interpretar(shipment, geojson)
                destinos = await colector_shipsgo.destinos_finales(sesion, elemento.via_transporte)
                if colector_shipsgo.llegada_a_destino_final(lectura, destinos) is not None:
                    print(f"  {etiqueta}: llegó a Costa Rica; se deja.")
                    continue

                otro_activo = await sesion.scalar(
                    select(ElementoRastreado.id).where(
                        ElementoRastreado.activo.is_(True),
                        ElementoRastreado.tipo_tracking_externo == elemento.tipo_tracking_externo,
                        ElementoRastreado.tracking_externo == elemento.tracking_externo,
                        ElementoRastreado.id != elemento.id,
                    )
                )
                elemento.ata_api = None
                if otro_activo is None:
                    elemento.activo = True
                pedidos = list(
                    await sesion.scalars(
                        select(PedidoTransito).where(
                            PedidoTransito.id_elemento_rastreado == elemento.id,
                            PedidoTransito.motivo_cierre.is_(None),
                            PedidoTransito.etapa_viaje == ETAPA_EN_DESTINO,
                            PedidoTransito.ata_confirmada.is_(None),
                            PedidoTransito.ata_inferida.is_(None),
                        )
                    )
                )
                for pedido in pedidos:
                    pedido.etapa_viaje = "EN_TRANSITO"
                await sesion.flush()
                await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
                await recalculo.recalcular_lote(sesion, pedidos)
                revertidos += 1
                ultimo = next((h for h in reversed(lectura.hitos) if h.ocurrido and h.puerto), None)
                print(
                    f"  {etiqueta}: NO llegó a Costa Rica (último evento: "
                    f"{ultimo.evento + ' en ' + ultimo.puerto if ultimo and ultimo.puerto else '?'})"
                    f" · ATA borrada, embarque reactivado · "
                    + (
                        ", ".join(
                            f"{p.oc_numero}-{p.posicion_oc} -> {p.etapa_viaje}/{p.estado_calculado}"
                            for p in pedidos
                        )
                        or "ningún pedido «En destino» por la fuente"
                    )
                )

            print(f"{revertidos} embarque(s) corregido(s).")
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
    parser.add_argument("--ensayo", action="store_true", help="revisa, aplica y revierte")
    sys.exit(asyncio.run(principal(parser.parse_args().ensayo)))
