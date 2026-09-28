"""Qué embarques hay registrados en la cuenta de ShipsGo — `US-50`, `US-52`.

ShipsGo no guarda qué id le dio a cada referencia de nuestro lado, y nuestro
modelo tampoco lo guarda: el alta se hace una vez y a mano. Para leer un
embarque hace falta su id, así que se lista la cuenta —**gratis**: listar no
consume crédito— y se arma el índice referencia → id.

Lo usan dos piezas: el worker, que lee los embarques en cada ciclo (`US-50`), y
la carga del archivo, que le pregunta a ShipsGo el puerto de destino de las
líneas cuyo incoterm no lo nombra (`US-52`).
"""

from __future__ import annotations

import logging
from typing import Final

from app.services.rastreo.shipsgo_cliente import ClienteShipsGo

logger = logging.getLogger(__name__)

#: Páginas que se leen como mucho por listado. Con 25 por página son 1 250
#: embarques, tres veces lo que Gutis tendría en un año.
PAGINAS_MAXIMAS: Final = 50


def clave_referencia(numero: str | None) -> str | None:
    """Mayúsculas y sin guiones: `020-12345675` y `02012345675` son la misma guía."""
    if not numero:
        return None
    return str(numero).replace("-", "").replace(" ", "").upper() or None


async def indice_shipsgo(cliente: ClienteShipsGo) -> dict[str, tuple[int, bool]]:
    """Referencia → `(id del embarque, es aéreo)`, de lo registrado en la cuenta.

    Pagina con `skip` porque `take` no cambia el tamaño de página (medido en
    `TASK-28`: siempre 25).
    """
    indice: dict[str, tuple[int, bool]] = {}
    for ruta, aereo, campos in (
        ("/ocean/shipments", False, ("container_number", "booking_number")),
        ("/air/shipments", True, ("awb_number",)),
    ):
        vistos = 0
        for _ in range(PAGINAS_MAXIMAS):
            cuerpo = await cliente.consultar(f"{ruta}?skip={vistos}")
            lote = cuerpo.get("shipments") or []
            for embarque in lote:
                id_embarque = embarque.get("id")
                if id_embarque is None:
                    continue
                for campo in campos:
                    clave = clave_referencia(embarque.get(campo))
                    if clave:
                        indice.setdefault(clave, (int(id_embarque), aereo))
            vistos += len(lote)
            if not lote or not (cuerpo.get("meta") or {}).get("more"):
                break
        else:
            logger.warning(
                "ShipsGo: la cuenta tiene más de %d páginas en %s; el índice queda parcial.",
                PAGINAS_MAXIMAS,
                ruta,
            )
    return indice


__all__ = ["PAGINAS_MAXIMAS", "clave_referencia", "indice_shipsgo"]
