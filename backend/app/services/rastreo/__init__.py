"""Fuentes de rastreo externas.

Una por proveedor, todas sobre la misma política de resiliencia
(`app.services.resiliencia` y `app.services.salud_fuentes`, `US-03`): el
adaptador solo traduce los errores de *su* proveedor a una clase de fallo, y
nunca lleva su propio backoff.

- `aisstream` — AIS marítimo por WebSocket (`US-02`). **Respaldo del mapa**
  desde el Plan A del 04/09: enriquece el trayecto entre hitos, no confirma
  arribos, porque no hay cobertura en la costa caribe de Costa Rica.
- Vizion (`US-45`), Portcast (`US-46`) y OpenSky (`US-05`) entran acá cuando
  les toque.
"""

from __future__ import annotations

from app.services.rastreo import aisstream
from app.services.rastreo.colector_ais import ColectorAIS, procesar_mensaje

__all__ = ["ColectorAIS", "aisstream", "procesar_mensaje"]
