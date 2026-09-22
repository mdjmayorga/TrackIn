"""Catálogo de aerolíneas de ShipsGo — `US-46`.

**La única forma de verificar cobertura sin pagar.** Es lo que separa a la vía
aérea de la marítima: en marítimo hay que dar de alta el embarque —y gastar el
crédito— para averiguar si la naviera está cubierta. En aéreo, `GET
/air/airlines` es una **consulta gratuita** que dice de antemano si el prefijo
de la guía resuelve a alguna aerolínea.

Lo que `TASK-28` midió el 14/09/2026
-------------------------------------

- **207 aerolíneas**, cada una con su código IATA y sus prefijos de tres
  dígitos. Lufthansa Cargo es `LH` con `020` y `220`.
- **22 de 22** prefijos de los MAWB de Gutis están cubiertos.
- El contraste que cerró la bifurcación: TrackingMore tiene **0 aerolíneas**
  en su catálogo de 1505 couriers, y con el mismo MAWB se quedó en `pending`
  bajo un courier que no podía resolverlo.

Por qué comprobar el prefijo antes del alta
--------------------------------------------

Porque ShipsGo **acepta y cobra cualquier cosa**. Un `POST` con una guía cuyo
prefijo no corresponde a ninguna aerolínea se registra igual, consume 2 USD y
después devuelve vacío — indistinguible de un envío sin novedades. Con el
catálogo en mano eso se detiene antes de tocar la red.

El catálogo se cachea en memoria: cambia con el ritmo al que nacen aerolíneas,
no con el de las consultas.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

logger = logging.getLogger(__name__)

RUTA_CATALOGO: Final = "/air/airlines"

#: Un MAWB son tres dígitos de prefijo más ocho de serie.
_PREFIJO = re.compile(r"^(\d{3})-?\d{8}$")


@dataclass(frozen=True, slots=True)
class Aerolinea:
    """Una aerolínea del catálogo, con los prefijos que emite."""

    iata: str
    nombre: str
    prefijos: tuple[str, ...]
    activa: bool = True


@dataclass
class CatalogoAerolineas:
    """Los prefijos que ShipsGo sabe resolver."""

    aerolineas: list[Aerolinea] = field(default_factory=list)

    @classmethod
    def desde_payload(cls, datos: list[dict[str, Any]]) -> CatalogoAerolineas:
        """Construye el catálogo desde lo que devuelve `GET /air/airlines`."""
        aerolineas: list[Aerolinea] = []
        for crudo in datos:
            if not isinstance(crudo, dict) or not crudo.get("iata"):
                continue
            prefijos = crudo.get("prefixes")
            aerolineas.append(
                Aerolinea(
                    iata=str(crudo["iata"]),
                    nombre=str(crudo.get("name") or crudo["iata"]),
                    prefijos=tuple(str(p) for p in prefijos or ()),
                    activa=crudo.get("status", "ACTIVE") == "ACTIVE",
                )
            )
        return cls(aerolineas)

    @property
    def por_prefijo(self) -> dict[str, Aerolinea]:
        """Índice de prefijo a aerolínea. Una puede tener varios."""
        indice: dict[str, Aerolinea] = {}
        for aerolinea in self.aerolineas:
            for prefijo in aerolinea.prefijos:
                indice.setdefault(prefijo, aerolinea)
        return indice

    def resolver(self, mawb: str) -> Aerolinea | None:
        """La aerolínea que emitió esa guía, o `None` si nadie la cubre."""
        prefijo = prefijo_de(mawb)
        if prefijo is None:
            return None
        return self.por_prefijo.get(prefijo)

    def cubre(self, mawb: str) -> bool:
        return self.resolver(mawb) is not None

    def __bool__(self) -> bool:
        """Un catálogo vacío no puede usarse para negar cobertura.

        Es la diferencia entre «ShipsGo no cubre esa aerolínea» y «no pude leer
        el catálogo». Negar el alta por lo segundo dejaría de rastrear envíos
        perfectamente válidos porque la consulta falló.
        """
        return bool(self.aerolineas)


def prefijo_de(mawb: str | None) -> str | None:
    """Los tres dígitos de aerolínea de un MAWB, o `None` si no tiene forma.

    Acepta el guion o su ausencia: el archivo trae las dos escrituras.
    """
    if not mawb:
        return None
    encontrado = _PREFIJO.match(str(mawb).strip())
    return encontrado.group(1) if encontrado else None


async def cargar(cliente: Any, paginas_maximas: int = 20) -> CatalogoAerolineas:
    """Lee el catálogo completo. **No consume crédito**: es una consulta.

    Pagina hasta agotar. El tope existe porque `TASK-28` midió que ShipsGo
    **ignora en silencio los parámetros que no conoce**: si el nombre del
    parámetro de paginación cambiara, la misma página volvería para siempre y
    esto giraría sin fin.
    """
    aerolineas: list[dict[str, Any]] = []
    vistas: set[str] = set()

    for pagina in range(paginas_maximas):
        cuerpo = await cliente.consultar(f"{RUTA_CATALOGO}?take=100&skip={pagina * 100}")
        lote = cuerpo.get("airlines") if isinstance(cuerpo, dict) else None
        if not lote:
            break
        # La guarda contra la paginación ignorada: si vuelve lo mismo, se corta.
        claves = {str(a.get("iata")) for a in lote if isinstance(a, dict)}
        if claves and claves <= vistas:
            logger.warning(
                "ShipsGo: la paginación de %s devolvió lo mismo; se corta en %d aerolíneas.",
                RUTA_CATALOGO,
                len(aerolineas),
            )
            break
        vistas |= claves
        aerolineas.extend(a for a in lote if isinstance(a, dict))

    catalogo = CatalogoAerolineas.desde_payload(aerolineas)
    logger.info(
        "ShipsGo: catálogo de %d aerolíneas, %d prefijos.",
        len(catalogo.aerolineas),
        len(catalogo.por_prefijo),
    )
    return catalogo


__all__ = [
    "RUTA_CATALOGO",
    "Aerolinea",
    "CatalogoAerolineas",
    "cargar",
    "prefijo_de",
]
