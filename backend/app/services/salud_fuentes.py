"""Dónde vive la salud de las fuentes externas, y de dónde salen sus umbrales.

`US-03` (RF-09 / RNF-12), criterios quinto y sexto.

`app.services.resiliencia` es **política pura**: sabe clasificar un fallo y
calcular una espera, y no toca ni la red ni la base. Este módulo es lo que le
falta para que la historia se cumpla de punta a punta, y son dos cosas:

1. **Un lugar donde el estado sobreviva** entre una lectura y la siguiente. Sin
   esto, `fallos_consecutivos` se reinicia en cada llamada y la espera creciente
   nunca crece.
2. **Los umbrales leídos de `parametros_sistema`**, para que se ajusten sin
   desplegar código (RF-24), igual que el intervalo de `US-04`.

**El registro empieza vacío, y eso es correcto.** Una fuente aparece cuando
alguien la consulta por primera vez; hoy nadie lo hace porque los adaptadores de
Vizion, Portcast y AISStream esperan a `TASK-28`. El healthcheck reporta la
lista vacía, que es la misma decisión que ya se tomó con `ingesta: null`: un
despliegue sin fuentes conectadas es un estado válido y visible, no un error.

**El estado vive en memoria a propósito.** Es salud de conexión, no dato de
negocio: la última posición buena está en `historial_tracking` y ningún reinicio
la toca (cuarto principio). Perder el conteo de fallos al reiniciar el proceso
solo significa que la primera consulta después del reinicio se hace de una vez,
que es lo que uno querría de todos modos. Cuando haya más de un proceso —no es
el caso del despliegue nativo de un solo servidor que aprobó `TASK-21`— habría
que moverlo a la base.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import parametros
from app.services.resiliencia import EstadoFuente, PoliticaReintento

logger = logging.getLogger(__name__)


async def politica_vigente(sesion: AsyncSession) -> PoliticaReintento:
    """Arma la política con los umbrales que hay en `parametros_sistema`.

    Cada valor cae a su defecto del catálogo si la fila no existe o está mal
    escrita, así que esto nunca falla por configuración: en el peor caso se
    reintenta con los valores de siempre, que es mejor que no reintentar.
    """
    return PoliticaReintento(
        espera_inicial_s=float(
            await parametros.obtener_decimal(sesion, "resiliencia_espera_inicial_s")
        ),
        factor=float(await parametros.obtener_decimal(sesion, "resiliencia_factor_espera")),
        espera_maxima_s=float(
            await parametros.obtener_decimal(sesion, "resiliencia_espera_maxima_s")
        ),
        intentos_maximos=await parametros.obtener_entero(sesion, "resiliencia_intentos_maximos"),
        ruido=float(await parametros.obtener_decimal(sesion, "resiliencia_ruido_espera")),
    )


class RegistroSalud:
    """Un `EstadoFuente` por fuente externa, creado al primer uso.

    Que cada fuente lleve su propio estado es lo que impide que la caída de
    Vizion apague a Portcast: son contratos distintos, con credenciales y
    límites de tasa distintos, y no hay razón para que una arrastre a la otra.
    """

    def __init__(self, politica: PoliticaReintento | None = None) -> None:
        self._politica = politica or PoliticaReintento()
        self._fuentes: dict[str, EstadoFuente] = {}

    def estado(self, nombre: str) -> EstadoFuente:
        """Estado de la fuente, creándolo sano si es la primera vez que se ve."""
        clave = nombre.strip().lower()
        if clave not in self._fuentes:
            self._fuentes[clave] = EstadoFuente(nombre=clave, politica=self._politica)
            logger.info("Salud de fuentes: se empieza a seguir %r.", clave)
        return self._fuentes[clave]

    def usar_politica(self, politica: PoliticaReintento) -> None:
        """Aplica umbrales nuevos, también a las fuentes que ya se seguían.

        Es lo que hace que RF-24 se note de verdad: cambiar la fila y recargar
        surte efecto sobre las fuentes vivas, sin reiniciar ni desplegar. No se
        toca el conteo de fallos, porque el historial de la fuente no cambia
        porque cambien sus umbrales.
        """
        self._politica = politica
        for fuente in self._fuentes.values():
            fuente.politica = politica

    def resumen(self, *, ahora: dt.datetime | None = None) -> list[dict[str, object]]:
        """Lo que el healthcheck y el encabezado del dashboard necesitan (RF-20).

        Ordenado por nombre para que la respuesta sea estable entre llamadas:
        una lista que cambia de orden sola es ruido en un diff y en una prueba.
        """
        instante = ahora or dt.datetime.now(dt.UTC)
        return [self._fuentes[nombre].resumen(ahora=instante) for nombre in sorted(self._fuentes)]

    @property
    def hay_degradadas(self) -> bool:
        """Si alguna fuente está degradada.

        **No degrada el servicio**, y por eso es una consulta aparte y no algo
        que el healthcheck mezcle con su `status`: el quinto principio dice que
        el dashboard responde siempre, porque lee de la base y no de la fuente.
        Que Vizion esté caída se informa, no se propaga.
        """
        return any(fuente.degradada for fuente in self._fuentes.values())

    def olvidar_todo(self) -> None:
        """Vacía el registro. Existe para las pruebas y para un reinicio manual."""
        self._fuentes.clear()


#: Registro único del proceso. Los adaptadores de `TASK-28` piden acá el estado
#: de su fuente en vez de llevar el suyo, que es lo que permite que un solo
#: healthcheck las vea todas.
registro = RegistroSalud()


__all__ = ["RegistroSalud", "politica_vigente", "registro"]
