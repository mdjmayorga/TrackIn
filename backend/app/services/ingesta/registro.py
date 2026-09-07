"""Selección de la fuente de pedidos según la configuración.

`TASK-03`. Es el único punto del sistema que conoce las implementaciones
concretas: el resto depende del puerto `FuentePedidos`. Añadir la fuente del
archivo de Logística (`US-31`) es registrar una entrada más en `_FUENTES`.

**Que no haya fuente configurada no es un error.** El tercer criterio de la
tarea lo pide explícitamente: el sistema arranca igual y lo reporta en el
healthcheck. Es lo correcto para un despliegue en el que la carga todavía no se
ha conectado —exactamente la situación que dejó el riesgo R2—, porque un
arranque fallido escondería el problema en vez de mostrarlo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.config import Settings, settings as settings_global
from app.services.ingesta.base import FuentePedidos
from app.services.ingesta.semilla import FuenteSemilla

logger = logging.getLogger(__name__)

#: Fuentes disponibles, por el nombre que se declara en `INGESTA_ADAPTADOR`.
_FUENTES: dict[str, Callable[[], FuentePedidos]] = {
    "semilla": FuenteSemilla,
}


def obtener_fuente(settings: Settings | None = None) -> FuentePedidos | None:
    """Devuelve la fuente configurada, o `None` si no hay ninguna.

    Un nombre desconocido se trata como «sin fuente» y se registra en el log:
    vale lo mismo que el caso anterior, y tumbar el arranque por una errata en
    una variable de entorno sería peor que reportarlo.
    """
    cfg = settings or settings_global
    nombre = (cfg.INGESTA_ADAPTADOR or "").strip().lower()

    if nombre in {"", "ninguno", "none"}:
        logger.info("Ingesta: sin fuente configurada; se reporta en el healthcheck.")
        return None

    constructor = _FUENTES.get(nombre)
    if constructor is None:
        logger.warning(
            "Ingesta: adaptador %r desconocido. Disponibles: %s. Se arranca sin fuente.",
            nombre,
            ", ".join(sorted(_FUENTES)) or "(ninguno)",
        )
        return None

    if nombre == "semilla" and cfg.is_production:
        # No se bloquea —el arranque no debe depender de esto—, pero que quede
        # dicho: la semilla son datos inventados y no deben verse en producción.
        logger.warning(
            "Ingesta: la fuente 'semilla' está activa en un entorno de producción."
        )

    return constructor()


__all__ = ["obtener_fuente"]
