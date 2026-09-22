"""Política de resiliencia de las fuentes externas — RF-09 / RNF-12 (`US-03`).

Reespecificada el 08/09/2026 para que **no dependa del transporte**. La versión
anterior estaba escrita contra WebSocket —watchdog sobre el ping/pong del
protocolo, cierre inmediato como fallo de credencial— y eso solo aplica a
AISStream. Vizion y Portcast son REST de consulta: no hay ping/pong ni cierre que
interpretar.

Lo que sí vale para las dos formas son los principios, y son los que viven acá:

1. **El silencio no es una caída.** Una fuente que responde bien y no trae nada
   nuevo tuvo un contacto **exitoso**. Confundirlo con un fallo es el error que
   hizo que el spike TG-10 pareciera roto cuando lo que pasaba es que en el
   Caribe no había tráfico que reportar.
2. **Un fallo permanente no se reintenta.** Una credencial inválida no mejora
   por insistir; reintentar solo gasta cuota y llena el log.
3. **Un fallo transitorio se reintenta con espera creciente y tope.** Nunca un
   bucle cerrado.
4. **Nunca se pierde la última lectura buena.** Vive en `historial_tracking` y
   ningún fallo la borra.
5. **El dashboard responde siempre**, porque lee de la base y no de la fuente.

Lo específico de cada proveedor —qué código HTTP o qué motivo de cierre
corresponde a qué clase— es del adaptador. Este módulo solo sabe de clases.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

logger = logging.getLogger(__name__)


class ClaseFallo(str, Enum):
    """Qué clase de fallo tuvo la fuente. Determina si se reintenta.

    La distinción es la que separa «esperá y volvé a probar» de «esto no se
    arregla solo»: reintentar una credencial inválida es gastar cuota, y no
    reintentar un tiempo agotado es perder datos que sí estaban.
    """

    #: La fuente respondió. No es un fallo.
    NINGUNO = "ninguno"
    #: Se arregla solo o con el tiempo: red, tiempo agotado, error del servidor.
    TRANSITORIO = "transitorio"
    #: No mejora reintentando: credencial, permiso, referencia inexistente.
    PERMANENTE = "permanente"
    #: Permanente **para esa referencia**, pero accionable: no es «no reintentar
    #: nunca», es «hay que dar de alta el embarque primero». Lo descubrió
    #: `TASK-28` el 14/09: las fuentes comerciales son *create-then-poll* y
    #: ninguna responde «¿dónde está el contenedor X?» en frío. Tratarlo como
    #: permanente dejaría la referencia muerta; como transitorio, reintentando
    #: en vano contra un embarque que nadie registró.
    REQUIERE_ALTA = "requiere_alta"


@dataclass(frozen=True, slots=True)
class PoliticaReintento:
    """Espera creciente con tope y ruido.

    El **tope** es lo que impide que la espera crezca sin límite tras una caída
    larga. El **ruido** evita que todos los elementos rastreados reintenten en el
    mismo instante tras una caída general: sin él, la recuperación de la fuente
    coincide con una avalancha de peticiones nuestra.
    """

    espera_inicial_s: float = 5.0
    factor: float = 2.0
    espera_maxima_s: float = 300.0
    intentos_maximos: int = 5
    #: Fracción de la espera que se reparte al azar. 0 la vuelve determinista.
    ruido: float = 0.2

    def espera(self, intento: int, *, aleatorio: random.Random | None = None) -> float:
        """Segundos a esperar antes del intento número `intento` (1 es el primero)."""
        if intento < 1:
            raise ValueError("El número de intento empieza en 1.")
        bruta = self.espera_inicial_s * (self.factor ** (intento - 1))
        acotada = min(bruta, self.espera_maxima_s)
        if not self.ruido:
            return acotada
        rng = aleatorio or random
        return acotada * (1 + rng.uniform(-self.ruido, self.ruido))

    def agotada(self, fallos_consecutivos: int) -> bool:
        """Si ya no vale la pena seguir reintentando."""
        return fallos_consecutivos >= self.intentos_maximos


@dataclass(slots=True)
class EstadoFuente:
    """Salud de una fuente externa, para RNF-12.

    No guarda datos de rastreo: la última posición vive en `historial_tracking` y
    ningún fallo la toca. Acá solo se lleva **si se puede confiar en lo que hay**
    y de cuándo es.
    """

    nombre: str
    politica: PoliticaReintento = field(default_factory=PoliticaReintento)

    ultimo_contacto_ok: dt.datetime | None = None
    ultimo_fallo: dt.datetime | None = None
    motivo_ultimo_fallo: str | None = None
    clase_ultimo_fallo: ClaseFallo = ClaseFallo.NINGUNO
    fallos_consecutivos: int = 0
    #: Se apaga sola al primer contacto bueno; un fallo permanente la fija.
    degradada: bool = False

    def registrar_exito(self, *, instante: dt.datetime, con_datos: bool = True) -> None:
        """Contacto correcto con la fuente, **traiga datos o no**.

        `con_datos=False` es el caso del primer principio: la fuente respondió y
        no había nada que reportar. Cuenta como éxito y **reinicia** el conteo de
        fallos. Tratarlo como caída fue justo lo que confundió al spike TG-10.
        """
        self.ultimo_contacto_ok = instante
        self.fallos_consecutivos = 0
        self.clase_ultimo_fallo = ClaseFallo.NINGUNO
        self.motivo_ultimo_fallo = None
        self.degradada = False
        if not con_datos:
            logger.debug("Fuente %s: contacto correcto sin datos nuevos.", self.nombre)

    def registrar_fallo(self, *, instante: dt.datetime, clase: ClaseFallo, motivo: str) -> None:
        """Anota el fallo. Un permanente degrada la fuente de inmediato.

        `REQUIERE_ALTA` es la excepción: se anota pero **no degrada nada**, por
        la razón que explica el cuerpo.
        """
        if clase is ClaseFallo.NINGUNO:
            raise ValueError("Un fallo no puede ser de clase NINGUNO.")

        self.ultimo_fallo = instante
        self.clase_ultimo_fallo = clase
        self.motivo_ultimo_fallo = motivo

        if clase is ClaseFallo.REQUIERE_ALTA:
            # La fuente **contestó bien**: el problema es de esta referencia, no
            # del proveedor. No cuenta contra los fallos consecutivos ni degrada
            # la fuente, porque degradarla apagaría el rastreo de todos los
            # demás embarques por culpa de uno sin registrar.
            logger.info(
                "Fuente %s: la referencia exige alta previa — %s. No degrada la fuente.",
                self.nombre,
                motivo,
            )
            return

        self.fallos_consecutivos += 1

        if clase is ClaseFallo.PERMANENTE:
            self.degradada = True
            logger.error(
                "Fuente %s degradada por fallo permanente: %s. No se reintenta.",
                self.nombre,
                motivo,
            )
        elif self.politica.agotada(self.fallos_consecutivos):
            self.degradada = True
            logger.error(
                "Fuente %s degradada tras %d fallos transitorios seguidos: %s",
                self.nombre,
                self.fallos_consecutivos,
                motivo,
            )
        else:
            logger.warning(
                "Fuente %s: fallo transitorio %d/%d — %s",
                self.nombre,
                self.fallos_consecutivos,
                self.politica.intentos_maximos,
                motivo,
            )

    @property
    def debe_reintentar(self) -> bool:
        """Si tiene sentido volver a intentar.

        Un fallo permanente **nunca** se reintenta, por muchos intentos que
        queden: es el segundo principio.
        """
        if self.clase_ultimo_fallo is ClaseFallo.PERMANENTE:
            return False
        if self.clase_ultimo_fallo is ClaseFallo.REQUIERE_ALTA:
            # Repetir la **misma** consulta volvería a fallar: lo que desbloquea
            # es el alta, no la espera. Quien llama tiene que darla de alta y
            # volver por otro camino.
            return False
        if self.clase_ultimo_fallo is ClaseFallo.NINGUNO:
            return True
        return not self.politica.agotada(self.fallos_consecutivos)

    def espera_hasta_el_proximo_intento(
        self, *, aleatorio: random.Random | None = None
    ) -> float | None:
        """Segundos que conviene esperar, o `None` si no hay que reintentar."""
        if not self.debe_reintentar:
            return None
        if self.fallos_consecutivos == 0:
            return 0.0
        return self.politica.espera(self.fallos_consecutivos, aleatorio=aleatorio)

    def antiguedad_s(self, *, ahora: dt.datetime) -> float | None:
        """Segundos desde el último contacto correcto, o `None` si nunca hubo.

        Es lo que RNF-12 exige mostrar junto al dato: no basta con enseñar la
        última posición, hay que decir de cuándo es.
        """
        if self.ultimo_contacto_ok is None:
            return None
        return (ahora - self.ultimo_contacto_ok).total_seconds()

    def resumen(self, *, ahora: dt.datetime) -> dict[str, object]:
        """Vista para el healthcheck y el encabezado del dashboard (RF-20)."""
        return {
            "fuente": self.nombre,
            "degradada": self.degradada,
            "fallos_consecutivos": self.fallos_consecutivos,
            "clase_ultimo_fallo": self.clase_ultimo_fallo.value,
            "motivo_ultimo_fallo": self.motivo_ultimo_fallo,
            "ultimo_contacto_ok": (
                self.ultimo_contacto_ok.isoformat() if self.ultimo_contacto_ok else None
            ),
            "antiguedad_s": self.antiguedad_s(ahora=ahora),
        }


#: Motivos que **siempre** son permanentes, sea cual sea el transporte. El
#: adaptador traduce su error concreto a uno de estos.
MOTIVOS_PERMANENTES: Final[frozenset[str]] = frozenset(
    {
        "credencial_invalida",  # 401/403 en REST · cierre inmediato en WebSocket
        "permiso_denegado",
        "referencia_inexistente",  # 404 sobre un contenedor o un MAWB
        "referencia_mal_formada",
        "cuota_agotada",  # el plan no da para más; insistir no lo cambia
    }
)

#: Motivos que exigen **dar de alta el embarque** antes de poder consultarlo.
#: Es el tercer caso que `US-03` dejó pendiente al cerrarse el 08/09 —*«el mapeo
#: de los errores concretos de cada proveedor»*— y que la fase 2 de `TASK-28`
#: midió el 14/09.
MOTIVOS_REQUIERE_ALTA: Final[frozenset[str]] = frozenset(
    {
        "referencia_sin_alta",  # TrackingMore lo dice con su código 4102
        "embarque_no_registrado",  # ShipsGo: la cuenta no tiene ese embarque
    }
)


def clasificar(motivo: str) -> ClaseFallo:
    """Clase del fallo a partir de su motivo normalizado.

    Lo desconocido se trata como **transitorio** a propósito: equivocarse hacia
    el reintento pierde cuota, y equivocarse hacia lo permanente pierde datos y
    apaga una fuente que funcionaba. El primer error es más barato, y el tope de
    intentos lo acota igual.
    """
    normalizado = motivo.strip().lower()
    if normalizado in MOTIVOS_REQUIERE_ALTA:
        return ClaseFallo.REQUIERE_ALTA
    if normalizado in MOTIVOS_PERMANENTES:
        return ClaseFallo.PERMANENTE
    return ClaseFallo.TRANSITORIO


__all__ = [
    "MOTIVOS_PERMANENTES",
    "MOTIVOS_REQUIERE_ALTA",
    "ClaseFallo",
    "EstadoFuente",
    "PoliticaReintento",
    "clasificar",
]
