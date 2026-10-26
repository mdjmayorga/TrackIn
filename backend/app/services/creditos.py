"""Saldo de créditos de ShipsGo y avisos antes de que se agoten — `US-57`.

Acuerdo del 06/10/2026: los créditos se compran por paquete anual. ShipsGo no
avisa cuando se acaban: el alta simplemente deja de funcionar. TrackIn lleva el
saldo para avisar antes.

**El saldo se calcula, no se guarda:** lo disponible del paquete vigente (lo
comprado más lo arrastrado) menos las altas que costaron crédito desde que se
registró. Las altas salen de la auditoría (RF-14), con el mismo criterio que el
tope diario (`planificador.altas_del_dia`): solo las que se pagaron.

| Nivel | Cuándo | Aviso |
|---|---|---|
| `SIN_PAQUETE` | Ningún paquete registrado | Registrar el vigente |
| `OK` | Lo normal | — |
| `POR_VENCER` | Faltan 60 días o menos y queda saldo | Cuánto se arrastraría y la recompra mínima |
| `BAJO` | Se consumió el 80 % o más | Comprar a tiempo |
| `AGOTADO` | Saldo cero o menos | Las altas van a fallar |
| `VENCIDO` | Pasó la fecha de vencimiento | Ídem |

**El arrastre** (condición de ShipsGo del 07/10/2026): lo que sobra pasa al paquete
siguiente si la compra nueva es de al menos el 50 % del anterior —550 con el de
1 100—, y siempre que el anterior no hubiera vencido al comprar.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from dataclasses import dataclass
from typing import Final, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.paquete_creditos import PaqueteCreditos
from app.models.parametro_sistema import ParametroSistema
from app.services.rastreo.registro_embarque import CAMPO_ALTA_CON_CREDITO, TIPO_INTERVENCION

logger = logging.getLogger(__name__)

#: Costa Rica no cambia de hora: UTC-6 todo el año.
ZONA_CR: Final = dt.timezone(dt.timedelta(hours=-6), "America/Costa_Rica")

#: Criterios de `US-57`.
PROPORCION_AVISO: Final = 0.8
DIAS_AVISO_VENCIMIENTO: Final = 60
#: Condición de ShipsGo del 07/10/2026 para arrastrar lo que sobra.
PROPORCION_RECOMPRA: Final = 0.5

Nivel = Literal["SIN_PAQUETE", "OK", "POR_VENCER", "BAJO", "AGOTADO", "VENCIDO"]

#: Los niveles que avisan en el panel y en el log.
NIVELES_CON_AVISO: Final[frozenset[str]] = frozenset(
    {"SIN_PAQUETE", "POR_VENCER", "BAJO", "AGOTADO", "VENCIDO"}
)


@dataclass(frozen=True, slots=True)
class EstadoCreditos:
    nivel: Nivel
    mensaje: str
    paquete: PaqueteCreditos | None = None
    disponible: int = 0
    consumidos: int = 0
    saldo: int = 0
    dias_para_vencer: int | None = None
    #: Lo mínimo que hay que comprar para arrastrar el saldo al paquete siguiente.
    recompra_minima: int | None = None

    @property
    def porcentaje_consumido(self) -> float | None:
        return self.consumidos / self.disponible if self.disponible else None


def recompra_minima(cantidad: int) -> int:
    return math.ceil(cantidad * PROPORCION_RECOMPRA)


async def paquete_vigente(sesion: AsyncSession) -> PaqueteCreditos | None:
    # Anotado: con el `selectinload`, mypy deduce `Any` para el resultado.
    vigente: PaqueteCreditos | None = await sesion.scalar(
        select(PaqueteCreditos)
        .options(selectinload(PaqueteCreditos.usuario))
        .order_by(PaqueteCreditos.registrado_en.desc(), PaqueteCreditos.id.desc())
        .limit(1)
    )
    return vigente


async def consumidos_desde(sesion: AsyncSession, desde: dt.datetime) -> int:
    """Altas que costaron crédito desde ese instante, según la auditoría."""
    total = await sesion.scalar(
        select(func.count())
        .select_from(AuditoriaIntervencion)
        .where(
            AuditoriaIntervencion.tipo_intervencion == TIPO_INTERVENCION,
            AuditoriaIntervencion.campo_afectado == CAMPO_ALTA_CON_CREDITO,
            AuditoriaIntervencion.fecha_hora >= desde,
        )
    )
    return int(total or 0)


def _hoy(instante: dt.datetime | None) -> dt.date:
    return (instante or dt.datetime.now(dt.UTC)).astimezone(ZONA_CR).date()


async def estado(sesion: AsyncSession, *, instante: dt.datetime | None = None) -> EstadoCreditos:
    """El saldo del paquete vigente y el aviso que corresponde."""
    paquete = await paquete_vigente(sesion)
    if paquete is None:
        return EstadoCreditos(
            nivel="SIN_PAQUETE",
            mensaje=(
                "No hay un paquete de créditos de ShipsGo registrado: TrackIn no puede llevar el "
                "saldo ni avisar antes de que se agote."
            ),
        )

    hoy = _hoy(instante)
    consumidos = await consumidos_desde(sesion, paquete.registrado_en)
    disponible = paquete.disponible
    saldo = disponible - consumidos
    dias = (paquete.vence_en - hoy).days if paquete.vence_en else None
    minima = recompra_minima(paquete.cantidad)

    nivel: Nivel
    if paquete.vence_en is not None and paquete.vence_en < hoy:
        nivel = "VENCIDO"
        mensaje = (
            f"El paquete de créditos de ShipsGo venció el {paquete.vence_en:%d/%m/%Y}. "
            "Las altas nuevas van a fallar hasta registrar uno nuevo."
        )
    elif saldo <= 0:
        nivel = "AGOTADO"
        mensaje = (
            f"Se agotaron los créditos de ShipsGo ({consumidos} de {disponible} usados). "
            "Las altas nuevas van a fallar hasta comprar más."
        )
    elif consumidos >= PROPORCION_AVISO * disponible:
        nivel = "BAJO"
        mensaje = (
            f"Quedan {saldo} de {disponible} créditos de ShipsGo: se usó el "
            f"{round(100 * consumidos / disponible)} %. Conviene comprar a tiempo."
        )
    elif dias is not None and dias <= DIAS_AVISO_VENCIMIENTO:
        nivel = "POR_VENCER"
        mensaje = (
            f"El paquete de créditos de ShipsGo vence en {dias} días con {saldo} sin usar. "
            f"Se arrastran al siguiente si la recompra es de al menos {minima} créditos."
        )
    else:
        nivel = "OK"
        mensaje = f"Quedan {saldo} de {disponible} créditos de ShipsGo."

    return EstadoCreditos(
        nivel=nivel,
        mensaje=mensaje,
        paquete=paquete,
        disponible=disponible,
        consumidos=consumidos,
        saldo=saldo,
        dias_para_vencer=dias,
        recompra_minima=minima,
    )


def arrastre(previo: EstadoCreditos, cantidad: int, comprado_en: dt.date) -> int:
    """Lo que pasa del paquete vigente al nuevo, con la regla de ShipsGo."""
    paquete = previo.paquete
    if paquete is None or previo.saldo <= 0:
        return 0
    if paquete.vence_en is not None and paquete.vence_en < comprado_en:
        return 0
    if cantidad < recompra_minima(paquete.cantidad):
        return 0
    return previo.saldo


async def registrar_paquete(
    sesion: AsyncSession,
    *,
    cantidad: int,
    comprado_en: dt.date,
    vence_en: dt.date | None,
    id_usuario: int,
    nota: str | None = None,
    altas_maximas_dia: int | None = None,
    instante: dt.datetime | None = None,
) -> PaqueteCreditos:
    """Registra una compra y la deja como vigente. **No hace commit.**

    Con `altas_maximas_dia`, sube el tope diario en la misma transacción: con el
    paquete anual entran 70 a 110 embarques al mes, y el tope de 5 se fijó para
    los 50 créditos de prueba (`US-57`, quinto criterio).
    """
    previo = await estado(sesion, instante=instante)
    sumado = arrastre(previo, cantidad, comprado_en)
    paquete = PaqueteCreditos(
        cantidad=cantidad,
        saldo_arrastrado=sumado,
        comprado_en=comprado_en,
        vence_en=vence_en,
        id_usuario=id_usuario,
        nota=nota,
        registrado_en=instante or dt.datetime.now(dt.UTC),
    )
    sesion.add(paquete)
    if altas_maximas_dia is not None:
        fila = await sesion.get(ParametroSistema, "altas_maximas_dia")
        if fila is None:
            sesion.add(
                ParametroSistema(
                    clave="altas_maximas_dia",
                    valor=str(altas_maximas_dia),
                    tipo_dato="ENTERO",
                    descripcion="Altas diarias por encima de las cuales se avisa (US-57).",
                )
            )
        else:
            fila.valor = str(altas_maximas_dia)
    await sesion.flush()
    logger.info(
        "Créditos: paquete de %d registrado (%d arrastrados, vence %s).",
        cantidad,
        sumado,
        vence_en or "sin fecha",
    )
    return paquete


async def avisar_en_log(sesion: AsyncSession) -> EstadoCreditos:
    """Escribe en el log si el saldo pide atención (`US-57`: `/health` y el log)."""
    actual = await estado(sesion)
    if actual.nivel in {"BAJO", "AGOTADO", "VENCIDO"}:
        logger.warning("Créditos de ShipsGo: %s", actual.mensaje)
    return actual


__all__ = [
    "DIAS_AVISO_VENCIMIENTO",
    "NIVELES_CON_AVISO",
    "PROPORCION_AVISO",
    "PROPORCION_RECOMPRA",
    "EstadoCreditos",
    "Nivel",
    "arrastre",
    "avisar_en_log",
    "consumidos_desde",
    "estado",
    "paquete_vigente",
    "recompra_minima",
    "registrar_paquete",
]
