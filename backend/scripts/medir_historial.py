"""Cuánto pesa y cuánto crece el historial de posiciones — `TASK-10`, RNF-22.

    python scripts/medir_historial.py

**Solo lee.** Responde lo que la política del 28/10/2026 deja para revisar: si
el historial llegara a crecer tanto que conviniera una retención. Esa decisión
fue **no borrar** —el volumen con ShipsGo es chico y RNF-13 pide conservar el
payload—, y este reporte es la forma de comprobar con el tiempo que sigue
siendo cierto. Umbral de alerta orientativo: 5 GB, o 2 millones de filas.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402

#: Por encima de esto vale la pena reabrir la decisión de no borrar.
ALERTA_BYTES = 5 * 1024**3
ALERTA_FILAS = 2_000_000

_RESUMEN = text(
    """
    SELECT
        count(*)                                                   AS filas,
        count(*) FILTER (WHERE fecha_registro > now() - interval '30 days') AS ultimos_30,
        count(DISTINCT id_elemento_rastreado)                       AS embarques,
        min(fecha_registro)                                         AS desde,
        coalesce(avg(pg_column_size(payload_api)), 0)               AS payload_medio,
        pg_total_relation_size('historial_tracking')                AS total_bytes,
        pg_indexes_size('historial_tracking')                       AS indices_bytes
    FROM historial_tracking
    """
)

_POR_VIA = text(
    """
    SELECT e.via_transporte, count(*)
    FROM historial_tracking h
    JOIN elementos_rastreados e ON e.id = h.id_elemento_rastreado
    GROUP BY 1 ORDER BY 1
    """
)


def _mb(bytes_: float) -> str:
    return f"{bytes_ / 1024**2:,.1f} MB"


async def principal() -> int:
    async with AsyncSessionLocal() as sesion:
        fila = (await sesion.execute(_RESUMEN)).one()
        por_via = (await sesion.execute(_POR_VIA)).all()
    await dispose_engine()

    print("Historial de posiciones (historial_tracking)")
    print(f"  Filas:               {fila.filas:,}  ({fila.embarques} embarques)")
    print(f"  Desde:               {fila.desde or '—'}")
    for via, cantidad in por_via:
        print(f"    {via:<10}         {cantidad:,}")
    print(f"  Tamaño total:        {_mb(fila.total_bytes)}  (índices: {_mb(fila.indices_bytes)})")
    print(f"  Payload medio:       {fila.payload_medio:,.0f} bytes")
    # Proyección: el ritmo de los últimos 30 días, llevado a un año.
    por_anio = fila.ultimos_30 * 365 / 30
    bytes_por_fila = fila.total_bytes / fila.filas if fila.filas else 0
    print(
        f"  Ritmo actual:        {fila.ultimos_30:,} filas en 30 días -> "
        f"~{por_anio:,.0f} al año (~{_mb(por_anio * bytes_por_fila)})"
    )

    if fila.total_bytes > ALERTA_BYTES or fila.filas > ALERTA_FILAS:
        print(
            "  AVISO: pasa el umbral orientativo: conviene reabrir TASK-10 y evaluar una "
            "retención (ver el backlog)."
        )
        return 2
    print("  Dentro de lo previsto: no hace falta retención (decisión del 28/10/2026).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(principal()))
