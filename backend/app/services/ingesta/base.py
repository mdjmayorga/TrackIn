"""El puerto de ingesta: la interfaz que toda fuente de pedidos implementa.

`TASK-03`. Su razón de ser es el segundo criterio de la tarea: *cuando se
implemente el adaptador definitivo, no debe requerir cambios en el motor de
cálculo ni en la API REST*. El motor y la API dependen de esta interfaz, nunca
de una fuente concreta.

Hoy existe una implementación —`FuenteSemilla`— y están previstas dos más:

- **`FuenteZTracking`** (`US-31`), que lee el archivo de seguimiento de
  Logística. Es la vía **oficial** de entrada desde la decisión del 03/09/2026
  que formalizó `RF-31`.
- **`FuenteSAP`**, si el Centro de Competencias llega a exponer el servicio.
  Quedó como evolución futura, fuera del alcance de la práctica.

Ninguna de las tres obliga a tocar nada aguas abajo: cambian la fuente, no el
contrato.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.ingesta.dto import PedidoCrudo


@runtime_checkable
class FuentePedidos(Protocol):
    """Origen desde el que TrackIn obtiene las líneas de orden de compra."""

    @property
    def nombre(self) -> str:
        """Identificador corto de la fuente. Se reporta en el healthcheck."""
        ...

    @property
    def descripcion(self) -> str:
        """Qué es esta fuente, en una línea, para diagnóstico."""
        ...

    async def obtener_pedidos(self) -> list[PedidoCrudo]:
        """Devuelve las líneas disponibles, sin normalizar ni persistir.

        Quien llama decide qué hacer con ellas. Una fuente **no** escribe en la
        base: separar la obtención de la persistencia es lo que permite validar
        un lote entero antes de tocar nada (`US-32`).
        """
        ...


__all__ = ["FuentePedidos"]
