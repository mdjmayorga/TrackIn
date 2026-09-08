"""Suscripción a AISStream y persistencia de lo que llega — RF-06 (`US-02`).

**No tiene política de reintento propia.** La toma de `US-03`: clasifica su
fallo, se lo cuenta a su `EstadoFuente` y pregunta cuánto esperar. Este módulo
es el primer adaptador sobre ese puerto, y lo único que aporta de suyo es la
traducción de un cierre de WebSocket a un motivo del vocabulario común.

Tres decisiones del spike TG-10 que el bucle implementa y conviene no deshacer:

- **No hay watchdog por ausencia de datos.** Es deliberado y es la diferencia
  entre funcionar y entrar en bucle infinito: la zona que le interesa a TrackIn
  **no tiene cobertura AIS**, así que reconectar tras N segundos de silencio
  reconectaría para siempre. Lo único que dispara una reconexión acá es que la
  conexión termine o falle; el socket muerto lo detecta el ping/pong del
  protocolo, que es independiente del tráfico de datos.
- **El cierre se clasifica por el momento, no por el código**, porque el
  servidor cierra sin *close frame*: una credencial inválida y una suscripción
  malformada dan exactamente el mismo cierre. Como `aisstream.suscripcion`
  valida antes de mandar, un cierre inmediato solo puede ser la credencial.
- **Se cierra abortando el transporte**, nunca esperando el `close()`
  negociado, que se cuelga con volumen alto (hallazgo de la Fase 0).

El transporte se inyecta. Sirve para probar el bucle entero sin red, que no es
una comodidad: el riesgo **R1** deja la cuenta sin entregar datos desde el
19/08/2026, así que una prueba que dependiera del socket real no correría.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.services import historial
from app.services.rastreo import aisstream
from app.services.rastreo.aisstream import EstaticoAIS, MensajeIlegible, PosicionAIS
from app.services.resiliencia import ClaseFallo, EstadoFuente, clasificar
from app.services.salud_fuentes import registro as registro_salud

logger = logging.getLogger(__name__)

#: Nombre con el que la fuente aparece en el healthcheck.
NOMBRE_FUENTE = "aisstream"

#: Los buques se siguen por MMSI. El IMO es más estable pero no viaja en los
#: mensajes de posición, que son los que alimentan el mapa.
TIPO_TRACKING = "MMSI"

#: La lectura no corresponde a nada que estemos siguiendo. **No es un error**:
#: el bounding box trae todo el tráfico de la zona y lo normal es que la enorme
#: mayoría de los buques no sea nuestra.
DESCARTE_SIN_ELEMENTO = "sin_elemento_activo"
#: Un estático que no declaró ETA no tiene nada que aportar hoy: el modelo no
#: guarda nombre, IMO ni destino. Ver el aviso al final del módulo.
DESCARTE_SIN_DATO_UTIL = "sin_dato_persistible"


@dataclass(frozen=True, slots=True)
class ResultadoProceso:
    """Qué se hizo con la lectura."""

    aplicado: bool
    motivo: str

    def __bool__(self) -> bool:
        return self.aplicado


class ConexionAIS(Protocol):
    """Lo mínimo que el bucle necesita de un transporte.

    Deliberadamente más chico que un WebSocket: así el doble de las pruebas es
    tres métodos y no una librería entera.
    """

    async def enviar(self, texto: str) -> None: ...

    def __aiter__(self) -> AsyncIterator[str]: ...

    async def abortar(self) -> None: ...


async def buscar_elemento(sesion: AsyncSession, mmsi: str) -> ElementoRastreado | None:
    """El elemento **activo** que corresponde a ese MMSI, si lo hay.

    El índice único es parcial sobre `activo` (§4.3 del diccionario), así que un
    MMSI reutilizado años después no colisiona con su vida anterior. Filtrar por
    `activo` acá es lo que hace que eso funcione.
    """
    return await sesion.scalar(
        select(ElementoRastreado).where(
            ElementoRastreado.tipo_tracking_externo == TIPO_TRACKING,
            ElementoRastreado.tracking_externo == mmsi,
            ElementoRastreado.activo.is_(True),
        )
    )


async def _aplicar_posicion(
    sesion: AsyncSession, elemento: ElementoRastreado, lectura: PosicionAIS
) -> ResultadoProceso:
    """Guarda la lectura en el historial y refresca la copia desnormalizada."""
    resultado = await historial.registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        fecha_registro=lectura.instante,
        latitud=lectura.latitud,
        longitud=lectura.longitud,
        velocidad=lectura.velocidad_nudos,
        rumbo=lectura.rumbo_grados,
        estado_api=lectura.estado_navegacion,
        payload=lectura.payload,
    )
    if not resultado.guardada:
        # Submuestreo o duplicada. La copia desnormalizada tampoco se toca: si
        # la lectura no mereció una fila, tampoco merece mover el mapa.
        return ResultadoProceso(False, resultado.motivo)

    # `posicion_actual` existe para que el dashboard no consulte una tabla de 25
    # millones de filas (§4.1 del diccionario). Se actualiza solo hacia adelante:
    # un mensaje que llega fuera de orden no puede retroceder el mapa.
    if (
        elemento.ultima_actualizacion_api is None
        or lectura.instante >= elemento.ultima_actualizacion_api
    ):
        elemento.posicion_actual = historial.punto_wkt(lectura.longitud, lectura.latitud)
        elemento.velocidad_actual = (
            Decimal(str(lectura.velocidad_nudos)) if lectura.velocidad_nudos is not None else None
        )
        elemento.ultima_actualizacion_api = lectura.instante

    return ResultadoProceso(True, "guardada")


def _aplicar_estatico(elemento: ElementoRastreado, lectura: EstaticoAIS) -> ResultadoProceso:
    """Actualiza la ETA declarada. **No toca la posición**, que es el criterio.

    Es lo único del mensaje estático que el modelo sabe guardar: no hay columna
    para el nombre del buque, ni para el IMO, ni para el destino. `eta_api` sí
    existe, y el diccionario la creó citando justamente esta fuente.
    """
    if lectura.eta is None:
        return ResultadoProceso(False, DESCARTE_SIN_DATO_UTIL)

    elemento.eta_api = lectura.eta
    return ResultadoProceso(True, "eta_actualizada")


async def procesar_mensaje(
    sesion: AsyncSession, lectura: PosicionAIS | EstaticoAIS
) -> ResultadoProceso:
    """Aplica una lectura ya parseada, si corresponde a algo que seguimos.

    No hace *commit*: el bucle procesa un flujo continuo y quien lo consume
    decide cada cuánto confirmar.
    """
    elemento = await buscar_elemento(sesion, lectura.mmsi)
    if elemento is None:
        return ResultadoProceso(False, DESCARTE_SIN_ELEMENTO)

    if isinstance(lectura, PosicionAIS):
        return await _aplicar_posicion(sesion, elemento, lectura)
    # No necesita la sesión: basta mutar el objeto, que ya está en la unidad
    # de trabajo. Quien llama decide cuándo confirmar.
    return _aplicar_estatico(elemento, lectura)


class ColectorAIS:
    """Mantiene la suscripción y reconecta según la política de `US-03`."""

    def __init__(
        self,
        *,
        api_key: str,
        cajas: list[list[list[float]]],
        abrir: Callable[[], Awaitable[ConexionAIS]],
        estado: EstadoFuente | None = None,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        # Se valida acá y no al conectar: si la suscripción fuera inválida, el
        # servidor cerraría igual que con una credencial mala y el diagnóstico
        # sería imposible. Mejor fallar antes de gastar una conexión.
        self._peticion = aisstream.suscripcion(api_key, cajas=cajas)
        self._abrir = abrir
        self._estado = estado or registro_salud.estado(NOMBRE_FUENTE)
        self._dormir = dormir
        self._reloj = reloj
        self._ultimo_tramo_s: float | None = None

    def _motivo_del_corte(self) -> str:
        """Motivo normalizado del corte, distinguiendo si llegó a conectarse.

        Sin esta distinción, una red caída —que ni siquiera abre el socket— se
        clasificaría como credencial inválida por haber durado cero segundos, y
        un fallo permanente apagaría la fuente para siempre. Es el error caro
        que `US-03` advierte: equivocarse hacia lo permanente pierde datos.
        """
        if self._ultimo_tramo_s is None:
            return "conexion_rechazada"
        return aisstream.clasificar_cierre(segundos_conectado=self._ultimo_tramo_s)

    @property
    def estado(self) -> EstadoFuente:
        """Salud de la fuente, la misma que reporta `/health`."""
        return self._estado

    async def _un_ciclo(self, procesar: Callable[[Any], Awaitable[None]]) -> None:
        """Una conexión completa: abre, se suscribe, consume hasta que termina."""
        conexion = await self._abrir()
        inicio = self._reloj()
        # Desde acá sí hubo conexión, así que su duración es clasificable.
        self._ultimo_tramo_s = 0.0
        try:
            await conexion.enviar(json.dumps(self._peticion))
            async for crudo in conexion:
                try:
                    lectura = aisstream.parsear(json.loads(crudo))
                except (json.JSONDecodeError, MensajeIlegible) as exc:
                    # Un frame corrupto es un problema de la fuente, no nuestro,
                    # y no puede tumbar la suscripción entera.
                    logger.warning("AIS: mensaje descartado por ilegible: %s", exc)
                    continue

                # El contacto fue correcto **aunque el mensaje no interese**:
                # es el primer principio de US-03, y es lo que impide que el
                # tráfico ajeno cuente como caída.
                self._estado.registrar_exito(
                    instante=dt.datetime.now(dt.UTC), con_datos=lectura is not None
                )
                if lectura is not None:
                    await procesar(lectura)
        finally:
            # Abortar, nunca el close() negociado: se cuelga con volumen alto.
            with contextlib.suppress(Exception):
                await conexion.abortar()
            self._ultimo_tramo_s = self._reloj() - inicio

    async def ejecutar(
        self, procesar: Callable[[Any], Awaitable[None]], *, ciclos: int | None = None
    ) -> None:
        """Consume la suscripción, reconectando mientras la política lo permita.

        `ciclos` acota cuántas conexiones se intentan; sin él corre indefinido,
        que es como lo usará el worker de `US-07`.
        """
        intento = 0
        while ciclos is None or intento < ciclos:
            intento += 1

            if not self._estado.debe_reintentar:
                logger.error(
                    "AIS: no se reintenta (%s). Se detiene el colector.",
                    self._estado.motivo_ultimo_fallo,
                )
                return

            espera = self._estado.espera_hasta_el_proximo_intento()
            if espera:
                logger.info("AIS: esperando %.1f s antes de reconectar.", espera)
                await self._dormir(espera)

            # `None` distingue «no llegó a conectar» de «conectó y duró 0 s»,
            # que es la diferencia entre un corte de red y una credencial mala.
            self._ultimo_tramo_s = None
            try:
                await self._un_ciclo(procesar)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                motivo = self._motivo_del_corte()
                self._estado.registrar_fallo(
                    instante=dt.datetime.now(dt.UTC), clase=clasificar(motivo), motivo=motivo
                )
                logger.warning("AIS: conexión terminada (%s): %s", motivo, exc)
                continue

            # La iteración terminó sin excepción: el servidor cerró de su lado.
            # Es transitorio salvo que haya durado lo que dura un rechazo de
            # credencial, que es el único caso en que AISStream cierra sin dar
            # ningún motivo.
            motivo = self._motivo_del_corte()
            clase = clasificar(motivo)
            if clase is ClaseFallo.PERMANENTE:
                self._estado.registrar_fallo(
                    instante=dt.datetime.now(dt.UTC), clase=clase, motivo=motivo
                )
            else:
                logger.info("AIS: el servidor cerró la suscripción; se reconecta.")
                self._estado.registrar_fallo(
                    instante=dt.datetime.now(dt.UTC),
                    clase=ClaseFallo.TRANSITORIO,
                    motivo="conexion_perdida",
                )


class _ConexionWebSocket:  # pragma: no cover - glue de E/S, sin lógica propia
    """Adapta `websockets` al protocolo mínimo que usa el colector."""

    def __init__(self, socket: Any) -> None:
        self._socket = socket

    async def enviar(self, texto: str) -> None:
        await self._socket.send(texto)

    def __aiter__(self) -> AsyncIterator[str]:
        return self._socket.__aiter__()

    async def abortar(self) -> None:
        # `close()` negociado se cuelga con volumen alto (Fase 0 del spike).
        transporte = getattr(self._socket, "transport", None)
        if transporte is not None:
            transporte.abort()
        else:
            await self._socket.close()


def abrir_websocket(url: str = aisstream.URL_STREAM) -> Callable[[], Awaitable[ConexionAIS]]:
    """Fábrica de conexiones reales, para inyectar en `ColectorAIS`."""

    async def _abrir() -> ConexionAIS:  # pragma: no cover - requiere red
        import websockets

        return _ConexionWebSocket(await websockets.connect(url))

    return _abrir


__all__ = [
    "DESCARTE_SIN_DATO_UTIL",
    "DESCARTE_SIN_ELEMENTO",
    "NOMBRE_FUENTE",
    "TIPO_TRACKING",
    "ColectorAIS",
    "ConexionAIS",
    "ResultadoProceso",
    "abrir_websocket",
    "buscar_elemento",
    "procesar_mensaje",
]
