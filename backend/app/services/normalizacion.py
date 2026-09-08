"""Normalización de los campos de dominio del archivo de origen — RN-17.

`TASK-29`. El Z-tracking trae país, vía de transporte, incoterm y temperatura
como **texto libre sucio**. Lo que se observó en la muestra real del 03/09/2026:

- Conviven `USA` y `ESTADOS UNIDOS` para el mismo país.
- Mayúsculas mezcladas: `Exw` junto a `EXW`, `Terrestre` junto a `TERRESTRE`.
- Erratas: `PEDIENTE` por `PENDIENTE`.
- Valores que no son datos: `PENDIENTE`, `N/A`.
- Columnas desplazadas: `INDIA` aparece dentro de la vía de transporte.
- Multivalor: `AEREO\\nMARITIMO` en una misma celda.

La regla de RN-17 es que **nada de esto aborta la carga**: lo que no resuelve se
marca para revisión y el resto del lote entra.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VIAS_TRANSPORTE
from app.models.maestro_pais import AliasPais, MaestroPais

#: Marcadores de «todavía no se sabe». No son datos y no deben normalizarse a
#: un valor de dominio: la columna queda nula y la línea sigue su curso.
VALORES_NO_DATO: frozenset[str] = frozenset(
    {"", "PENDIENTE", "PEDIENTE", "PENDENTE", "N/A", "NA", "NONE", "-", "SIN DATO"}
)

#: Incoterms de Incoterms 2020 que aparecen en el archivo, más el valor `LOCAL`
#: que Gutis usa para las compras nacionales.
INCOTERMS: frozenset[str] = frozenset(
    {"EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP", "LOCAL"}
)


def normalizar_texto(valor: str | None) -> str | None:
    """Mayúsculas, sin tildes y sin espacios de sobra.

    Devuelve `None` para lo que no es un dato. Es la entrada de todas las demás
    funciones del módulo y de la búsqueda de alias de país.
    """
    if valor is None:
        return None
    # NFD separa la tilde de la letra; se descartan los diacríticos (Mn).
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", str(valor)) if unicodedata.category(c) != "Mn"
    )
    limpio = re.sub(r"\s+", " ", sin_tildes).strip().upper()
    return None if limpio in VALORES_NO_DATO else limpio


def normalizar_via(valor: str | None) -> str | None:
    """Resuelve la vía de transporte, o `None` si hay que revisar la línea.

    Devuelve `None` a propósito en dos casos que la muestra real produce: un
    valor que no es una vía —como el `INDIA` de la columna desplazada— y una
    celda con **dos** vías, que no se puede resolver sin decidir cuál manda.
    """
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    encontradas = {via for via in VIAS_TRANSPORTE if via in texto}
    # Una sola coincidencia es una vía; dos es un multivalor que hay que revisar.
    return encontradas.pop() if len(encontradas) == 1 else None


def normalizar_incoterm(valor: str | None) -> str | None:
    """Devuelve el código de tres letras, descartando el lugar convenido.

    `CIF LIMON` y `CIF TERRESTRE` son ambos `CIF`: el incoterm es el código, y
    lo que sigue es el lugar. Lo que importa para TrackIn es quién controla el
    flete, y eso lo dice el código.
    """
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    primera = texto.split(" ")[0]
    return primera if primera in INCOTERMS else None


def normalizar_temperatura(valor: str | None) -> str | None:
    """Unifica la condición de almacenamiento.

    Solo distingue lo que la operación necesita: si el material exige cadena de
    frío o viaja a temperatura ambiente. El rango exacto se conserva tal cual
    llegó cuando no es ninguno de los dos casos conocidos.
    """
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    if "AMBIENTE" in texto:
        return "AMBIENTE"
    if "2" in texto and "8" in texto:
        return "2-8 C"
    if "15" in texto and "25" in texto:
        return "15-25 C"
    return texto


async def resolver_pais(sesion: AsyncSession, valor: str | None) -> MaestroPais | None:
    """Devuelve el país del maestro que corresponde a la grafía recibida.

    Busca primero por código ISO y luego por alias, ambos ya normalizados. Un
    `None` significa «hay que revisar esta línea», no «error»: la carga sigue.
    """
    texto = normalizar_texto(valor)
    if texto is None:
        return None

    if len(texto) == 2:
        encontrado = await sesion.scalar(select(MaestroPais).where(MaestroPais.codigo == texto))
        if encontrado is not None:
            return encontrado

    return await sesion.scalar(select(MaestroPais).join(AliasPais).where(AliasPais.alias == texto))


__all__ = [
    "INCOTERMS",
    "VALORES_NO_DATO",
    "normalizar_incoterm",
    "normalizar_temperatura",
    "normalizar_texto",
    "normalizar_via",
    "resolver_pais",
]
