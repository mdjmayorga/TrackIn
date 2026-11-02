"""Los hitos del viaje, dichos para la línea de tiempo del detalle — `US-29`.

`colector_shipsgo.hitos_del_viaje` guarda en el elemento rastreado los hitos
ocurridos de la última lectura. Este módulo los pone en castellano:

| Evento | Marítimo | Aéreo |
|---|---|---|
| Salida | `DEPA` «Zarpó de…» | `DEP` «Despegó de…» |
| Llegada | `ARRV` «Arribó a…» | `ARR` «Aterrizó en…» |
| Descarga o recepción | `DISC` «Descargado en…» | `RCF` «Recibido del vuelo en…» |
| Entrega | — | `DLV` «Entregado al agente en…» |

**La primera salida es la «Salida del origen»** (decisión del 02/11/2026): el
primer hito de la línea, con el lugar y el país reales de donde partió la carga.
Puede no coincidir con el país de origen del pedido, que es el del proveedor.
**La primera llegada a uno de nuestros destinos es la «Llegada a destino»**; las
llegadas anteriores son transbordos.

El país se dice con el nombre del maestro (`TASK-29`), en castellano, a partir
del código ISO que trae ShipsGo. El maestro tiene los países de los
proveedores, no los de transbordo: si no lo tiene, el nombre de ShipsGo.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maestro_pais import MaestroPais

_VERBOS: Final[dict[str, str]] = {
    "DEPA": "Zarpó de",
    "ARRV": "Arribó a",
    "DISC": "Descargado en",
    "DEP": "Despegó de",
    "ARR": "Aterrizó en",
    "RCF": "Recibido del vuelo en",
    "DLV": "Entregado al agente en",
}
_SALIDAS: Final = frozenset({"DEPA", "DEP"})
_PAIS_ENTRE_PARENTESIS: Final = re.compile(r"\s*\([^)]*\)$")
_AEREOS: Final = frozenset({"DEP", "ARR", "RCF", "DLV"})


@dataclass(frozen=True, slots=True)
class HitoDescrito:
    instante: dt.datetime
    evento: str
    texto: str
    #: «Vuelo LH518» o «Nave MAERSK CHACHAI», si la fuente lo dio.
    vehiculo: str | None


async def nombres_de_paises(sesion: AsyncSession) -> dict[str, str]:
    """Código ISO → nombre en castellano, del maestro."""
    filas = await sesion.execute(select(MaestroPais.codigo, MaestroPais.nombre))
    return dict(filas.tuples().all())


def describir(hitos: list[dict[str, Any]] | None, paises: dict[str, str]) -> list[HitoDescrito]:
    """Los hitos guardados, en orden y en castellano."""
    descritos: list[HitoDescrito] = []
    hubo_salida = hubo_llegada = False
    for hito in hitos or []:
        evento = str(hito.get("evento") or "")
        verbo = _VERBOS.get(evento)
        instante = _instante(hito.get("instante"))
        if verbo is None or instante is None:
            continue
        texto = f"{verbo} {_lugar(hito, paises)}"
        if evento in _SALIDAS and not hubo_salida:
            hubo_salida = True
            texto = f"Salida del origen: {_minuscula(texto)}"
        elif hito.get("destino_final") and not hubo_llegada:
            hubo_llegada = True
            texto = f"Llegada a destino: {_minuscula(texto)}"
        vehiculo = hito.get("vehiculo")
        descritos.append(
            HitoDescrito(
                instante=instante,
                evento=evento,
                texto=texto,
                vehiculo=(
                    f"{'Vuelo' if evento in _AEREOS else 'Nave'} {vehiculo}" if vehiculo else None
                ),
            )
        )
    return descritos


def _lugar(hito: dict[str, Any], paises: dict[str, str]) -> str:
    """«Fráncfort (FRA), Alemania»: el nombre de la fuente, el código y el país."""
    codigo = hito.get("puerto")
    nombre = hito.get("puerto_nombre")
    if isinstance(nombre, str):
        # ShipsGo a veces repite el país en el nombre: «Cartagena (Colombia)».
        nombre = _PAIS_ENTRE_PARENTESIS.sub("", nombre).strip()
        if nombre.isupper():
            # Las navieras escriben el puerto en mayúsculas: «SANTOS».
            nombre = nombre.title()
    lugar = f"{nombre} ({codigo})" if nombre and codigo else (nombre or codigo or "lugar sin dato")
    pais = hito.get("pais")
    if isinstance(pais, str) and pais:
        lugar = f"{lugar}, {paises.get(pais) or hito.get('pais_nombre') or pais}"
    return lugar


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def _instante(valor: Any) -> dt.datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        return dt.datetime.fromisoformat(valor)
    except ValueError:
        return None


__all__ = ["HitoDescrito", "describir", "nombres_de_paises"]
