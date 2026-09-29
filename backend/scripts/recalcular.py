"""Recalcula fecha proyectada y estado a mano — `US-12`.

    python scripts/recalcular.py                         # todos los activos
    python scripts/recalcular.py --destino CRMOB         # los de un destino
    python scripts/recalcular.py --destino CRMOB --lead-time 5
    python scripts/recalcular.py --ensayo                # calcula y revierte

Lo normal es no necesitarlo: el worker recalcula al llegar una lectura, la
carga del archivo al cambiar una línea y `destinos.cambiar_lead_time` al
cambiar el maestro. Existe para lo que llega **por fuera** de esos caminos:

- una **migración** que cambia datos, como `0009` y `0010`, que movieron los
  lead time el 24/09 y dejaron fechas hechas con el valor viejo;
- un **parámetro** editado en `parametros_sistema`, como el umbral de riesgo.

`--lead-time` cambia el maestro por el camino de `US-12`: guarda y recalcula
en la misma transacción.
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

from app.db.session import AsyncSessionLocal, dispose_engine, engine  # noqa: E402
from app.models.maestro_destino import MaestroDestino  # noqa: E402
from app.services import destinos, recalculo  # noqa: E402


async def principal(codigo: str | None, lead_time: int | None, ensayo: bool) -> int:
    async with AsyncSessionLocal() as sesion:
        await sesion.begin()
        destino = None
        if codigo is not None:
            destino = await sesion.scalar(
                select(MaestroDestino).where(MaestroDestino.codigo == codigo.upper())
            )
            if destino is None:
                print(f"No existe el destino {codigo}.", file=sys.stderr)
                return 1

        if lead_time is not None:
            assert destino is not None
            try:
                cambio = await destinos.cambiar_lead_time(sesion, destino.id, lead_time)
            except destinos.LeadTimeInvalido as exc:
                print(exc, file=sys.stderr)
                return 1
            print(f"Lead time de {cambio.destino}: {cambio.anterior} → {cambio.nuevo} días.")
            resumen = cambio.recalculo
            if resumen is None:
                print("No cambió: no hay nada que recalcular.")
        elif destino is not None:
            resumen = await recalculo.recalcular_destino(sesion, destino.id)
        else:
            resumen = await recalculo.recalcular_todos(sesion)

        if resumen is not None:
            print(f"Recálculo: {resumen.texto()}.")
            for estado, n in sorted((resumen.por_estado or {}).items()):
                print(f"  {estado:<20} {n:>6}")
            for motivo, n in (resumen.por_motivo_sin_fecha or {}).items():
                print(f"  sin fecha ({n}): {motivo}")
            for nombre in resumen.fallidos:
                print(f"  falló {nombre}: queda como estaba, ver el log")

        if ensayo:
            await sesion.rollback()
            print("--ensayo: nada se guardó.")
        else:
            await sesion.commit()
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(
        description="Recalcula la fecha proyectada y el estado de los pedidos activos."
    )
    analizador.add_argument("--destino", help="Código del destino (CRMOB, MROC…).")
    analizador.add_argument(
        "--lead-time", type=int, help="Nuevo lead time del destino, en días. Exige --destino."
    )
    analizador.add_argument(
        "--ensayo", action="store_true", help="Calcula y muestra, pero no guarda nada."
    )
    argumentos = analizador.parse_args()
    if argumentos.lead_time is not None and argumentos.destino is None:
        analizador.error("--lead-time exige --destino")

    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    # Mismo motivo que en `cargar_semilla.py`: el eco de SQL tapa el informe.
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    async def _correr() -> int:
        try:
            return await principal(argumentos.destino, argumentos.lead_time, argumentos.ensayo)
        finally:
            await dispose_engine()

    return asyncio.run(_correr())


if __name__ == "__main__":
    raise SystemExit(main())
