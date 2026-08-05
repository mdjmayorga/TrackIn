"""Lógica de negocio y clientes de servicios externos.

Acá viven, a partir de sprints posteriores:
  - ingesta de los Excel de compras,
  - cliente de AISStream (WebSocket, tracking marítimo),
  - cliente de OpenSky Network (REST, tracking aéreo),
  - cálculo de estados de los pedidos.

Los endpoints de `app.api` no deben contener reglas de negocio: delegan acá.
"""

__all__: list[str] = []
