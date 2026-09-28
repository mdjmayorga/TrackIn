"""El puerto de destino, según ShipsGo — `US-52` / RF-01, RN-17.

La carga del archivo rechaza la línea cuyo destino no puede resolver: un
incoterm «CIF» sin puerto, con Caldera, Limón y Moín posibles. Es deliberado
—`carga.resolver_destino` no adivina—, y el 28/09/2026 se vio por qué: el BL
COSCO `COSU6508789000` de la OC 4500016185-10, con incoterm «CIF», **descarga en
Caldera**, en el Pacífico. Suponer el Caribe habría sido lo natural, y un error.

Pero si el embarque está registrado en ShipsGo, el destino no hay que
adivinarlo: **ShipsGo lo sabe**. Este módulo se lo pregunta. No es una
inferencia nuestra, es el puerto de descarga que declara la naviera.

Lo que no hace: gastar
-----------------------

**Solo lee embarques que ya están en la cuenta.** Listar y leer son gratis; dar
de alta cuesta un crédito y lo decide una persona. Una línea cuya referencia no
está registrada sigue rechazada igual que antes, con el mismo motivo.

Cuándo responde `None`
-----------------------

- La referencia no es de ShipsGo (una guía hija la rastrea TICA, no ShipsGo).
- No está registrada en la cuenta.
- Está registrada pero todavía madura: `NEW`, sin ruta. Medido el 28/09: hasta
  31 minutos tras el alta.
- ShipsGo no respondió. Un fallo aquí **no aborta la carga**: la línea queda
  rechazada con su motivo y el lote sigue (RN-17).

Los códigos casi coinciden
---------------------------

ShipsGo entrega el puerto en UN/LOCODE y el maestro usa el mismo sistema para
Caldera (`CRCAL`) y Limón (`CRLIO`). Hay dos excepciones medidas, y se traducen
explícitamente en `EQUIVALENCIAS` en vez de adivinar por parecido:

- **Moín**: ShipsGo reporta `CRPMN` («Puerto Moín», medido en los contenedores
  Maersk de `TASK-28`) y el maestro lo registra como `CRMOB`.
- **Juan Santamaría**: en aéreo ShipsGo usa el IATA `SJO` y el maestro el OACI
  `MROC`.

Un código fuera de la tabla y del maestro no se traduce: la línea queda
rechazada con el código a la vista, para que alguien lo agregue.
"""

from __future__ import annotations

import logging
from typing import Final

from app.services.rastreo import shipsgo
from app.services.rastreo.indice_shipsgo import clave_referencia, indice_shipsgo
from app.services.rastreo.shipsgo_cliente import CAMPO_POR_TIPO, ClienteShipsGo, ErrorShipsGo

logger = logging.getLogger(__name__)

#: Código de ShipsGo → código del maestro de destinos, cuando difieren.
EQUIVALENCIAS: Final[dict[str, str]] = {
    "CRPMN": "CRMOB",  # Puerto Moín
    "SJO": "MROC",  # Aeropuerto Juan Santamaría (IATA → OACI)
}


class ResolutorDestinoShipsGo:
    """`(tipo, número) → código de destino`, leyendo lo registrado en ShipsGo.

    Se usa como el `resolutor_destino` de `carga.cargar`. Arma el índice de la
    cuenta una sola vez, la primera vez que hace falta, y recuerda lo que ya
    resolvió: un BL puede amparar varias líneas del mismo archivo.
    """

    def __init__(self, cliente: ClienteShipsGo) -> None:
        self._cliente = cliente
        self._indice: dict[str, tuple[int, bool]] | None = None
        self._resueltos: dict[str, str | None] = {}
        #: Tras un fallo de ShipsGo no se insiste en el resto del lote.
        self._fuera_de_servicio = False
        #: Cuántos embarques se leyeron. Lo reporta el script de carga.
        self.lecturas = 0

    async def _indice_de_la_cuenta(self) -> dict[str, tuple[int, bool]]:
        if self._indice is None:
            self._indice = await indice_shipsgo(self._cliente)
        return self._indice

    async def __call__(self, tipo: str, numero: str) -> str | None:
        if tipo.upper() not in CAMPO_POR_TIPO or self._fuera_de_servicio:
            return None
        clave = clave_referencia(numero)
        if clave is None:
            return None
        if clave in self._resueltos:
            return self._resueltos[clave]

        try:
            registrado = (await self._indice_de_la_cuenta()).get(clave)
            if registrado is None:
                logger.info("ShipsGo: %s %s no está registrado; no se da de alta.", tipo, numero)
                self._resueltos[clave] = None
                return None
            id_embarque, aereo = registrado
            embarque = await self._cliente.leer(id_embarque, aereo=aereo)
            self.lecturas += 1
        except ErrorShipsGo as exc:
            logger.warning(
                "ShipsGo: no se pudo consultar el destino de %s (%s); la línea queda "
                "como estaba y no se insiste con el resto del lote.",
                numero,
                exc.motivo,
            )
            self._fuera_de_servicio = True
            return None

        if not shipsgo.esta_maduro(embarque):
            # No se recuerda: dentro de un rato puede tener ruta.
            logger.info("ShipsGo: %s sigue madurando; el destino todavía no se conoce.", numero)
            return None

        puerto = shipsgo.interpretar(embarque).puerto_destino
        destino = EQUIVALENCIAS.get(puerto or "", puerto)
        self._resueltos[clave] = destino
        if destino:
            logger.info("ShipsGo: %s %s descarga en %s.", tipo, numero, destino)
        return destino


__all__ = ["EQUIVALENCIAS", "ResolutorDestinoShipsGo"]
