"""Planificación de las consultas a las fuentes — `US-07` / RF-08.

Decide **qué se consulta, cuándo y en qué orden**. No consulta: eso es del
cliente. No calcula: eso es de `recalculo` y `arribo`. Es el que los ordena.

Lo que `TASK-28` cambió de esta historia
-----------------------------------------

El criterio original vigilaba la **cuota diaria de consultas**, y descansaba
sobre un supuesto que el spike midió falso:

> *«Dada la cuota diaria, cuando el consumo proyectado la excedería, entonces
> el planificador lo advierte en el log»*

**El crédito no se gasta consultando: se gasta en el alta.** ShipsGo es
*create-then-poll* y cobra por embarque registrado, no por lectura. Sondear
seguido no quema créditos, solo roza el límite de tasa. Así que lo que este
módulo contabiliza y advierte es el **número de altas**, que es lo que cuesta
dinero — a 2 USD el crédito y ~374 estimados al año.

Los tres estados de una respuesta, no dos
------------------------------------------

Esta es la otra consecuencia, y la más fácil de implementar mal:

| Estado | Qué significa | Qué hace el planificador |
|---|---|---|
| Con datos | El embarque maduró | Lo procesa y reprograma al intervalo normal |
| **Dado de alta, sin datos** | ~90 s de maduración: `status: NEW` | **Reprograma a corto plazo**, no cuenta fallo |
| Fallo | La fuente no respondió | Aplica la política de espera de `US-03` |

Tratar el segundo como fallo degradaría la fuente por algo que no falló; como
respuesta vacía definitiva, daría el embarque por perdido a los 45 segundos de
haberlo pagado. `TASK-28` lo midió: a los 45 s devolvía `NEW`, a los ~90 s
estaba completo.

Qué sale del ciclo
-------------------

- El embarque **auto-archivado** por ShipsGo (`discarded_at`): ya no es
  consultable y seguir pidiéndolo es gastar peticiones en un 404.
- El elemento **sin pedidos activos** (decisión B7 del 01/09): la nave zarpó
  hacia otro puerto y su posición ya no representa la carga. Lo apaga `US-11`
  y aquí simplemente deja de aparecer.
- El elemento cuya fuente quedó **degradada** por `US-03`.

Lo que no se planifica
-----------------------

El rastreo marítimo **por AIS** (`US-02`, respaldo del mapa) es una suscripción
persistente por WebSocket, no un sondeo: no tiene intervalo que configurar y su
bucle vive en `colector_ais`. Aquí solo se planifican las fuentes REST.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services import parametros

logger = logging.getLogger(__name__)

CLAVE_FRECUENCIA_AEREA = "frecuencia_aerea_min"
CLAVE_FRECUENCIA_MARITIMA = "frecuencia_maritima_min"
CLAVE_VENTANA_INICIO = "ventana_aerea_inicio_h"
CLAVE_VENTANA_FIN = "ventana_aerea_fin_h"
CLAVE_MADURACION = "maduracion_reintento_s"
CLAVE_ALTAS_MAXIMAS = "altas_maximas_dia"

#: Por qué un elemento no toca consultarlo ahora.
OMITIDO_FUERA_DE_VENTANA = "fuera_de_la_ventana_aerea"
OMITIDO_SIN_VENCER = "intervalo_sin_vencer"
OMITIDO_INACTIVO = "elemento_inactivo"
OMITIDO_SIN_PEDIDOS = "sin_pedidos_activos"

#: Las vías que este planificador sondea. `AIS` no está: es suscripción.
VIAS_SONDEADAS: Final[frozenset[str]] = frozenset({"AEREO", "MARITIMO"})


@dataclass(frozen=True, slots=True)
class Politica:
    """Los parámetros vigentes, leídos de la base en cada tic.

    **Se releen en cada tic y no se capturan al arrancar**: es lo que hace
    cierto el primer criterio de `US-07`, que la frecuencia se cambie sin
    reiniciar el servicio.
    """

    frecuencia_aerea_min: int
    frecuencia_maritima_min: int
    ventana_inicio_h: int
    ventana_fin_h: int
    maduracion_reintento_s: int
    altas_maximas_dia: int

    def intervalo(self, via: str) -> dt.timedelta:
        minutos = self.frecuencia_aerea_min if via == "AEREO" else self.frecuencia_maritima_min
        return dt.timedelta(minutes=minutos)

    def en_ventana(self, instante: dt.datetime) -> bool:
        """Si la hora cae dentro de la ventana activa del sondeo aéreo.

        Soporta ventanas que cruzan la medianoche (22 a 6), porque nada impide
        que alguien las configure así y fallar ahí sería silencioso: se
        sondearía justo al revés de lo pedido.
        """
        hora = instante.hour
        if self.ventana_inicio_h <= self.ventana_fin_h:
            return self.ventana_inicio_h <= hora < self.ventana_fin_h
        return hora >= self.ventana_inicio_h or hora < self.ventana_fin_h


async def politica_vigente(sesion: AsyncSession) -> Politica:
    """Lee los seis parámetros. Un valor ilegible cae a su defecto (`US-17`)."""
    return Politica(
        frecuencia_aerea_min=await parametros.obtener_entero(sesion, CLAVE_FRECUENCIA_AEREA),
        frecuencia_maritima_min=await parametros.obtener_entero(sesion, CLAVE_FRECUENCIA_MARITIMA),
        ventana_inicio_h=await parametros.obtener_entero(sesion, CLAVE_VENTANA_INICIO),
        ventana_fin_h=await parametros.obtener_entero(sesion, CLAVE_VENTANA_FIN),
        maduracion_reintento_s=await parametros.obtener_entero(sesion, CLAVE_MADURACION),
        altas_maximas_dia=await parametros.obtener_entero(sesion, CLAVE_ALTAS_MAXIMAS),
    )


@dataclass(frozen=True, slots=True)
class Tarea:
    """Un elemento que toca consultar, y por qué le toca."""

    id_elemento: int
    tracking: str
    via: str
    #: Cuándo se consultó por última vez. `None` = nunca.
    ultima: dt.datetime | None
    #: `True` si se reprograma pronto por estar madurando, no por el intervalo.
    madurando: bool = False


@dataclass(frozen=True, slots=True)
class Omitido:
    """Un elemento que **no** toca, con el motivo. Se reporta, no se esconde."""

    id_elemento: int
    tracking: str
    motivo: str


@dataclass(slots=True)
class Plan:
    """Qué hacer en este tic."""

    instante: dt.datetime
    politica: Politica
    tareas: list[Tarea] = field(default_factory=list)
    omitidos: list[Omitido] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.tareas)

    def por_via(self) -> dict[str, int]:
        cuenta: dict[str, int] = {}
        for tarea in self.tareas:
            cuenta[tarea.via] = cuenta.get(tarea.via, 0) + 1
        return cuenta

    def motivos_omitidos(self) -> dict[str, int]:
        cuenta: dict[str, int] = {}
        for omitido in self.omitidos:
            cuenta[omitido.motivo] = cuenta.get(omitido.motivo, 0) + 1
        return cuenta

    def resumen(self) -> str:
        return (
            f"{self.total} a consultar ({self.por_via()}), "
            f"{len(self.omitidos)} omitidos {self.motivos_omitidos()}"
        )


def _toca(
    politica: Politica,
    ahora: dt.datetime,
    via: str,
    ultima: dt.datetime | None,
    madurando: bool,
) -> bool:
    """Si venció el intervalo de ese elemento.

    Un embarque **madurando** usa la espera corta y no la del intervalo: a los
    45 s del alta devolvía `NEW` y a los ~90 s estaba completo. Esperar seis
    horas por él sería tener pagado un embarque y no mirarlo.
    """
    if ultima is None:
        return True  # nunca consultado: va ya
    espera = (
        dt.timedelta(seconds=politica.maduracion_reintento_s)
        if madurando
        else politica.intervalo(via)
    )
    return ahora - ultima >= espera


async def _elementos_con_pedidos_activos(sesion: AsyncSession) -> set[int]:
    """Los elementos que todavía llevan carga nuestra.

    Decisión B7 del 01/09: los demás no se consultan. `US-11` ya los apaga al
    cerrar el arribo; esto cubre además el caso de que la única línea que los
    usaba se cerrara por otra vía (RN-13).
    """
    filas = await sesion.scalars(
        select(PedidoTransito.id_elemento_rastreado)
        .where(
            PedidoTransito.id_elemento_rastreado.is_not(None),
            PedidoTransito.motivo_cierre.is_(None),
        )
        .distinct()
    )
    return {fila for fila in filas if fila is not None}


async def planificar(
    sesion: AsyncSession,
    instante: dt.datetime | None = None,
    madurando: set[int] | None = None,
) -> Plan:
    """Arma el plan del tic. **No consulta nada y no hace commit.**

    `madurando` son los elementos cuyo embarque se dio de alta y todavía no
    trajo datos; quien llama los arrastra de un tic al siguiente, porque el
    estado es del embarque en ShipsGo y no hay columna que lo guarde.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    politica = await politica_vigente(sesion)
    plan = Plan(instante=ahora, politica=politica)
    en_maduracion = madurando or set()

    con_carga = await _elementos_con_pedidos_activos(sesion)
    elementos = await sesion.scalars(
        select(ElementoRastreado).where(ElementoRastreado.via_transporte.in_(VIAS_SONDEADAS))
    )

    for elemento in elementos:
        if not elemento.activo:
            plan.omitidos.append(Omitido(elemento.id, elemento.tracking_externo, OMITIDO_INACTIVO))
            continue
        if elemento.id not in con_carga:
            plan.omitidos.append(
                Omitido(elemento.id, elemento.tracking_externo, OMITIDO_SIN_PEDIDOS)
            )
            continue
        if elemento.via_transporte == "AEREO" and not politica.en_ventana(ahora):
            # Segundo criterio: fuera de la ventana se **suspende** el sondeo.
            plan.omitidos.append(
                Omitido(elemento.id, elemento.tracking_externo, OMITIDO_FUERA_DE_VENTANA)
            )
            continue

        esta_madurando = elemento.id in en_maduracion
        if not _toca(
            politica,
            ahora,
            elemento.via_transporte,
            elemento.ultima_actualizacion_api,
            esta_madurando,
        ):
            plan.omitidos.append(
                Omitido(elemento.id, elemento.tracking_externo, OMITIDO_SIN_VENCER)
            )
            continue

        plan.tareas.append(
            Tarea(
                id_elemento=elemento.id,
                tracking=elemento.tracking_externo,
                via=elemento.via_transporte,
                ultima=elemento.ultima_actualizacion_api,
                madurando=esta_madurando,
            )
        )

    logger.info("Planificador: %s", plan.resumen())
    return plan


# --- Lo que sí cuesta dinero: las altas ------------------------------------


async def altas_del_dia(sesion: AsyncSession, instante: dt.datetime | None = None) -> int:
    """Cuántos embarques se dieron de alta hoy, según la auditoría de RF-14.

    Se cuenta desde `auditoria_intervenciones` y no desde un contador en
    memoria: el gasto tiene que sobrevivir a un reinicio, porque es dinero.
    """
    from app.models.auditoria_intervencion import AuditoriaIntervencion
    from app.services.rastreo.registro_embarque import TIPO_INTERVENCION

    ahora = instante or dt.datetime.now(dt.UTC)
    desde = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    total = await sesion.scalar(
        select(func.count())
        .select_from(AuditoriaIntervencion)
        .where(
            AuditoriaIntervencion.tipo_intervencion == TIPO_INTERVENCION,
            AuditoriaIntervencion.fecha_hora >= desde,
        )
    )
    return int(total or 0)


async def revisar_consumo(
    sesion: AsyncSession, instante: dt.datetime | None = None
) -> tuple[int, bool]:
    """Devuelve las altas de hoy y si pasan del umbral, avisando en el log.

    **Esto reemplaza al criterio de cuota diaria de consultas**, que descansaba
    sobre un supuesto falso. Lo que hay que vigilar es el alta: a 2 USD el
    crédito, veinte en un día son señal de que algo se registra en bucle.
    """
    politica = await politica_vigente(sesion)
    altas = await altas_del_dia(sesion, instante)
    excedido = altas > politica.altas_maximas_dia
    if excedido:
        logger.warning(
            "Planificador: %d altas hoy, por encima del umbral de %d. "
            "Son ~%d USD y conviene revisar qué las dispara.",
            altas,
            politica.altas_maximas_dia,
            altas * 2,
        )
    return altas, excedido


__all__ = [
    "CLAVE_ALTAS_MAXIMAS",
    "CLAVE_FRECUENCIA_AEREA",
    "CLAVE_FRECUENCIA_MARITIMA",
    "CLAVE_MADURACION",
    "CLAVE_VENTANA_FIN",
    "CLAVE_VENTANA_INICIO",
    "OMITIDO_FUERA_DE_VENTANA",
    "OMITIDO_INACTIVO",
    "OMITIDO_SIN_PEDIDOS",
    "OMITIDO_SIN_VENCER",
    "VIAS_SONDEADAS",
    "Omitido",
    "Plan",
    "Politica",
    "Tarea",
    "altas_del_dia",
    "planificar",
    "politica_vigente",
    "revisar_consumo",
]
