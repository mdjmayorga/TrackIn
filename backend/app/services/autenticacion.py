"""Login, sesiones y roles — `US-42` / RNF-05, RNF-24.

Mecanismo propio, sin SSO ni Active Directory (fuera del alcance). Las
decisiones abiertas del wireframe del login (§0.4) se tomaron con valores
razonables que viven en `parametros_sistema` y se ajustan sin desplegar:

- **Bloqueo:** `login_intentos_maximos` fallos seguidos bloquean la cuenta
  `login_bloqueo_min` minutos.
- **Inactividad:** una sesión se cierra tras `sesion_inactividad_min` sin uso.
  Cada petición cuenta: la pantalla de planta, que se refresca sola, sigue
  abierta mientras esté encendida.
- **«Recordar sesión»:** no cierra por inactividad; dura
  `sesion_recordada_dias` desde que se abrió.
- **«¿Olvidó su contraseña?»:** sin correo, la reinicia el Administrador.

El mensaje de error del login es **siempre el mismo**, falle el usuario, la
contraseña o esté bloqueada la cuenta: cualquier diferencia diría a un tercero
qué usuarios existen.

La cuenta compartida de Compras
--------------------------------

`compras@gutis.com` es **un solo usuario** que usan varias personas a la vez
(decisión del 30/09/2026). Por eso abrir una sesión nunca cierra otra, y la
auditoría registra «Compras» sin pedir nombres.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import parametros

logger = logging.getLogger(__name__)

#: argon2id con los parámetros por omisión de argon2-cffi (RFC 9106, perfil bajo
#: en memoria): suficiente para una intranet y rápido para las pruebas.
_HASHER = PasswordHasher()

#: Lo único que ve quien falla el login, sea cual sea la causa.
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos, o la cuenta está bloqueada."

LONGITUD_MINIMA_CONTRASENA = 10


class CredencialesInvalidas(Exception):
    """El login falló. Nunca dice por qué: ver `MENSAJE_CREDENCIALES`."""

    def __init__(self) -> None:
        super().__init__(MENSAJE_CREDENCIALES)


class SesionInvalida(Exception):
    """El token no existe, está cerrado o venció."""


class ContrasenaDebil(ValueError):
    """La contraseña no cumple el mínimo."""


@dataclass(frozen=True, slots=True)
class SesionAbierta:
    token: str
    """Solo existe aquí y en el cliente: la base guarda su hash."""
    sesion: Sesion
    usuario: Usuario


def hashear(contrasena: str) -> str:
    validar_contrasena(contrasena)
    return _HASHER.hash(contrasena)


def validar_contrasena(contrasena: str) -> None:
    if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        raise ContrasenaDebil(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
        )


def _verificar(hash_guardado: str, contrasena: str) -> bool:
    try:
        return _HASHER.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


#: Un hash real para comparar cuando el usuario no existe: así el login tarda
#: lo mismo exista o no, y el tiempo de respuesta no delata qué cuentas hay.
_HASH_SEÑUELO = _HASHER.hash(secrets.token_urlsafe(16))


async def iniciar_sesion(
    sesion_bd: AsyncSession,
    usuario: str,
    contrasena: str,
    *,
    recordar: bool = False,
    instante: dt.datetime | None = None,
) -> SesionAbierta:
    """Verifica la credencial y abre una sesión. **No hace commit.**

    Un fallo con usuario existente suma un intento; al llegar al máximo, la
    cuenta queda bloqueada. El contador vuelve a cero al entrar bien.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    cuenta = await sesion_bd.scalar(
        select(Usuario).where(func.lower(Usuario.usuario) == usuario.strip().lower())
    )
    if cuenta is None:
        _verificar(_HASH_SEÑUELO, contrasena)
        raise CredencialesInvalidas()

    bloqueada = cuenta.bloqueado_hasta is not None and cuenta.bloqueado_hasta > ahora
    if bloqueada or not cuenta.activo:
        _verificar(_HASH_SEÑUELO, contrasena)
        raise CredencialesInvalidas()

    if not _verificar(cuenta.hash_contrasena, contrasena):
        cuenta.intentos_fallidos += 1
        maximo = await parametros.obtener_entero(sesion_bd, "login_intentos_maximos")
        if cuenta.intentos_fallidos >= maximo:
            minutos = await parametros.obtener_entero(sesion_bd, "login_bloqueo_min")
            cuenta.bloqueado_hasta = ahora + dt.timedelta(minutes=minutos)
            cuenta.intentos_fallidos = 0
            logger.warning(
                "Login: %s bloqueado %d min tras %d intentos.", cuenta.usuario, minutos, maximo
            )
        await sesion_bd.flush()
        raise CredencialesInvalidas()

    if _HASHER.check_needs_rehash(cuenta.hash_contrasena):
        cuenta.hash_contrasena = _HASHER.hash(contrasena)
    cuenta.intentos_fallidos = 0
    cuenta.bloqueado_hasta = None
    cuenta.ultimo_acceso = ahora

    token = secrets.token_urlsafe(32)
    nueva = Sesion(
        id_usuario=cuenta.id,
        hash_token=_hash_token(token),
        recordada=recordar,
        creada_en=ahora,
        ultimo_uso=ahora,
    )
    sesion_bd.add(nueva)
    await sesion_bd.flush()
    logger.info("Login: %s (%s) abre la sesión %d.", cuenta.usuario, cuenta.rol, nueva.id)
    return SesionAbierta(token=token, sesion=nueva, usuario=cuenta)


async def _vencida(sesion_bd: AsyncSession, sesion: Sesion, ahora: dt.datetime) -> bool:
    if sesion.recordada:
        dias = await parametros.obtener_entero(sesion_bd, "sesion_recordada_dias")
        return ahora - sesion.creada_en > dt.timedelta(days=dias)
    minutos = await parametros.obtener_entero(sesion_bd, "sesion_inactividad_min")
    return ahora - sesion.ultimo_uso > dt.timedelta(minutes=minutos)


async def validar_token(
    sesion_bd: AsyncSession, token: str, *, instante: dt.datetime | None = None
) -> tuple[Sesion, Usuario]:
    """La sesión y el usuario del token, renovando su último uso. **No hace commit.**

    Una sesión vencida se marca cerrada al detectarlo: queda en la tabla con
    su cierre, que es lo que permite auditar después cuándo terminó.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    sesion = await sesion_bd.scalar(select(Sesion).where(Sesion.hash_token == _hash_token(token)))
    if sesion is None or sesion.cerrada_en is not None:
        raise SesionInvalida()
    usuario = await sesion_bd.get(Usuario, sesion.id_usuario)
    if usuario is None or not usuario.activo:
        sesion.cerrada_en = ahora
        await sesion_bd.flush()
        raise SesionInvalida()
    if await _vencida(sesion_bd, sesion, ahora):
        sesion.cerrada_en = ahora
        await sesion_bd.flush()
        raise SesionInvalida()
    sesion.ultimo_uso = ahora
    await sesion_bd.flush()
    return sesion, usuario


async def cerrar_sesion(
    sesion_bd: AsyncSession, sesion: Sesion, *, instante: dt.datetime | None = None
) -> None:
    """Cierra **solo esta** sesión: las demás del mismo usuario siguen abiertas."""
    sesion.cerrada_en = instante or dt.datetime.now(dt.UTC)
    await sesion_bd.flush()


async def cerrar_sesiones_de(
    sesion_bd: AsyncSession, id_usuario: int, *, instante: dt.datetime | None = None
) -> int:
    """Cierra todas las sesiones abiertas de un usuario. Devuelve cuántas."""
    resultado = await sesion_bd.execute(
        update(Sesion)
        .where(Sesion.id_usuario == id_usuario, Sesion.cerrada_en.is_(None))
        .values(cerrada_en=instante or dt.datetime.now(dt.UTC))
    )
    return resultado.rowcount or 0


__all__ = [
    "LONGITUD_MINIMA_CONTRASENA",
    "MENSAJE_CREDENCIALES",
    "ContrasenaDebil",
    "CredencialesInvalidas",
    "SesionAbierta",
    "SesionInvalida",
    "cerrar_sesion",
    "cerrar_sesiones_de",
    "hashear",
    "iniciar_sesion",
    "validar_contrasena",
    "validar_token",
]
