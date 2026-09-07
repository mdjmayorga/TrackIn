"""Ingesta de pedidos: el puerto y sus adaptadores.

`TASK-03`, habilitador de RF-01 y RF-31.

    from app.services.ingesta import obtener_fuente

    fuente = obtener_fuente()
    if fuente is not None:
        pedidos = await fuente.obtener_pedidos()

El motor de cálculo y la API dependen de `FuentePedidos`, nunca de una fuente
concreta: cambiar de semilla a archivo, o a un servicio, no los toca.
"""

from app.services.ingesta.base import FuentePedidos
from app.services.ingesta.dto import PedidoCrudo
from app.services.ingesta.registro import obtener_fuente
from app.services.ingesta.semilla import PEDIDOS_SEMILLA, FuenteSemilla

__all__ = [
    "PEDIDOS_SEMILLA",
    "FuentePedidos",
    "FuenteSemilla",
    "PedidoCrudo",
    "obtener_fuente",
]
