"""Selección de la fuente de pedidos según la configuración.

`TASK-03`. Es el único punto del sistema que conoce las implementaciones
concretas: el resto depende del puerto `FuentePedidos`.

**Quién valida el nombre del adaptador — resuelto el 22/09/2026.** El 08/09 se
detectó que este módulo y `Settings` se contradecían: acá se documentaba que un
nombre mal escrito «no debe tumbar el arranque» y degradaba a «sin fuente»,
mientras que `Settings.INGESTA_ADAPTADOR` es un `Literal` que pydantic rechaza
antes, de modo que la rama defensiva era inalcanzable por la vía normal.

**Manda el `Literal`.** Una errata en la variable de entorno detiene el
arranque. El razonamiento: «sin fuente» es un estado legítimo —el tercer
criterio de `TASK-03` lo exige, y es la situación real mientras la carga no se
conecta—, y precisamente por eso no puede ser también el resultado de un typo.
Si `ztraking` degradara a «sin fuente», el healthcheck informaría lo mismo que
una instalación configurada a propósito sin fuente, y el operador no tendría
cómo distinguirlas.

Las ramas defensivas de `obtener_fuente` se conservan porque siguen siendo el
contrato del módulo cuando se le pasa un objeto de configuración construido a
mano, pero quedan documentadas como **inalcanzables vía `Settings`**.

Las fuentes se construyen **con la configuración**, no sin argumentos: `US-31`
añadió `ztracking`, que necesita saber qué archivo leer.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.config import Settings
from app.core.config import settings as settings_global
from app.services.ingesta.base import FuentePedidos
from app.services.ingesta.semilla import FuenteSemilla
from app.services.ingesta.ztracking import FuenteZTracking

logger = logging.getLogger(__name__)


def _construir_semilla(_cfg: Settings) -> FuentePedidos:
    """La semilla no necesita configuración; recibe `Settings` por uniformidad."""
    return FuenteSemilla()


def _construir_ztracking(cfg: Settings) -> FuentePedidos:
    """La fuente del archivo de Logística.

    `Settings` ya garantiza que la ruta está definida cuando el adaptador es
    `ztracking` (validador `_ztracking_exige_ruta`); la comprobación de acá
    cubre el caso de una configuración construida a mano, igual que las demás
    ramas defensivas del módulo.
    """
    if cfg.ZTRACKING_RUTA is None:
        raise ValueError("La fuente 'ztracking' exige ZTRACKING_RUTA en la configuración.")
    return FuenteZTracking(ruta=cfg.ZTRACKING_RUTA)


#: Fuentes disponibles, por el nombre que se declara en `INGESTA_ADAPTADOR`.
#: Toda entrada nueva tiene que aparecer **también** en el `Literal` de
#: `Settings.INGESTA_ADAPTADOR`, que es quien decide qué nombres existen.
_FUENTES: dict[str, Callable[[Settings], FuentePedidos]] = {
    "semilla": _construir_semilla,
    "ztracking": _construir_ztracking,
}


def obtener_fuente(settings: Settings | None = None) -> FuentePedidos | None:
    """Devuelve la fuente configurada, o `None` si no hay ninguna.

    `None` significa «configurado sin fuente», nunca «el nombre estaba mal»:
    eso último lo detiene `Settings` al construirse.
    """
    cfg = settings or settings_global
    nombre = (cfg.INGESTA_ADAPTADOR or "").strip().lower()

    if nombre in {"", "ninguno", "none"}:
        logger.info("Ingesta: sin fuente configurada; se reporta en el healthcheck.")
        return None

    constructor = _FUENTES.get(nombre)
    if constructor is None:
        # Inalcanzable vía `Settings`: el `Literal` rechaza el valor antes.
        logger.warning(
            "Ingesta: adaptador %r desconocido. Disponibles: %s. Se arranca sin fuente.",
            nombre,
            ", ".join(sorted(_FUENTES)) or "(ninguno)",
        )
        return None

    if nombre == "semilla" and cfg.is_production:
        # No se bloquea —el arranque no debe depender de esto—, pero que quede
        # dicho: la semilla son datos inventados y no deben verse en producción.
        logger.warning("Ingesta: la fuente 'semilla' está activa en un entorno de producción.")

    return constructor(cfg)


__all__ = ["obtener_fuente"]
