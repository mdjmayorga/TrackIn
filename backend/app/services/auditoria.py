"""La bitácora de intervenciones manuales — `US-15` / RF-14, RNF-06.

    «El sistema debe registrar, por cada intervención manual sobre un pedido, el
    usuario que la ejecutó, la fecha y hora, el valor anterior, el valor nuevo y
    el motivo declarado.» — RF-14

Este módulo es **la única puerta** para escribir en `auditoria_intervenciones`.
Antes de `US-15` cada intervención armaba su fila a mano; ahora todas pasan por
`registrar`, que exige lo que RF-14 exige y convierte los valores a texto de una
sola manera, para que la bitácora se lea igual venga de donde venga.

Qué no hace: corregir. Una fila escrita no se edita ni se borra —lo impide un
disparador en la base (migración `0017`)—. Si una intervención estuvo mal, se
corrige con **otra** intervención, y la bitácora conserva las dos.

El autor
--------

Sale de la sesión (`US-42`), no de un selector: quien llama pasa el
`id_usuario` que le da `usuario_actual`. Con la cuenta compartida de Compras la
bitácora dice «Compras» sin distinguir personas (decisión del 30/09/2026).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.enums import TIPOS_INTERVENCION
from app.models.usuario import Usuario

#: Menos que esto no explica nada: «ok», «x», «cambio».
LONGITUD_MINIMA_MOTIVO: Final = 5
LONGITUD_MAXIMA_MOTIVO: Final = 300


class IntervencionInvalida(ValueError):
    """Falta algo que RF-14 exige, o el tipo no existe."""


def _como_texto(valor: object) -> str | None:
    """Una sola forma de escribir cada tipo, para que la bitácora se compare."""
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        # En UTC siempre: el mismo instante llega con «-06:00» si viene de la
        # pantalla y con «+00:00» si viene de la base, y la bitácora tiene que
        # poder compararlos como texto (`US-14`).
        if valor.tzinfo is not None:
            valor = valor.astimezone(dt.UTC)
        return valor.isoformat()
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, Decimal):
        return format(valor.normalize(), "f")
    return str(valor)


def validar_motivo(motivo: str | None) -> str:
    texto = (motivo or "").strip()
    if len(texto) < LONGITUD_MINIMA_MOTIVO:
        raise IntervencionInvalida(
            f"El motivo es obligatorio (RF-14) y debe explicar la intervención: "
            f"al menos {LONGITUD_MINIMA_MOTIVO} caracteres."
        )
    if len(texto) > LONGITUD_MAXIMA_MOTIVO:
        raise IntervencionInvalida(
            f"El motivo no puede pasar de {LONGITUD_MAXIMA_MOTIVO} caracteres."
        )
    return texto


def registrar(
    sesion: AsyncSession,
    *,
    id_pedido: int,
    id_usuario: int,
    tipo: str,
    motivo: str,
    campo: str | None = None,
    anterior: object = None,
    nuevo: object = None,
    instante: dt.datetime | None = None,
) -> AuditoriaIntervencion:
    """Anota una intervención. **No hace `flush` ni commit**: va en la misma
    transacción que el cambio que audita, así que entran juntos o ninguno."""
    if tipo not in TIPOS_INTERVENCION:
        raise IntervencionInvalida(f"Tipo de intervención desconocido: {tipo!r}.")
    fila = AuditoriaIntervencion(
        id_pedido=id_pedido,
        id_usuario=id_usuario,
        tipo_intervencion=tipo,
        campo_afectado=campo,
        valor_anterior=_como_texto(anterior),
        valor_nuevo=_como_texto(nuevo),
        motivo=validar_motivo(motivo),
    )
    if instante is not None:
        fila.fecha_hora = instante
    sesion.add(fila)
    return fila


@dataclass(frozen=True, slots=True)
class Asiento:
    """Una línea de la bitácora, con el autor ya resuelto."""

    fila: AuditoriaIntervencion
    usuario: str
    nombre_usuario: str
    rol: str


async def bitacora(sesion: AsyncSession, id_pedido: int) -> list[Asiento]:
    """Las intervenciones de un pedido, de la más antigua a la más reciente.

    El desempate por `id` ordena dos intervenciones del mismo instante —una
    confirmación que dispara un recálculo, por ejemplo— en el orden en que se
    escribieron.
    """
    filas = await sesion.execute(
        select(AuditoriaIntervencion, Usuario.usuario, Usuario.nombre_completo, Usuario.rol)
        .join(Usuario, Usuario.id == AuditoriaIntervencion.id_usuario)
        .where(AuditoriaIntervencion.id_pedido == id_pedido)
        .order_by(AuditoriaIntervencion.fecha_hora, AuditoriaIntervencion.id)
    )
    return [Asiento(fila, usuario, nombre, rol) for fila, usuario, nombre, rol in filas]


__all__ = [
    "LONGITUD_MAXIMA_MOTIVO",
    "LONGITUD_MINIMA_MOTIVO",
    "Asiento",
    "IntervencionInvalida",
    "bitacora",
    "registrar",
    "validar_motivo",
]
