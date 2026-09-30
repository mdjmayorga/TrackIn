"""Pruebas del login, las sesiones y los roles — `US-42`.

A diferencia del resto de pruebas de la API, aquí **no** se sustituye
`usuario_actual`: todo pasa por el login de verdad, contra la base. Solo se
convierte el `commit` en `flush`, para que la transacción de la prueba se
revierta al final y la base de desarrollo quede intacta.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import get_db
from app.main import app
from app.models.parametro_sistema import ParametroSistema
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import autenticacion
from app.services.autenticacion import (
    MENSAJE_CREDENCIALES,
    CredencialesInvalidas,
    SesionInvalida,
    iniciar_sesion,
    validar_token,
)

pytestmark = pytest.mark.integration

CLAVE = "una-clave-larga"
AHORA = dt.datetime(2026, 9, 30, 15, 0, tzinfo=dt.UTC)


class _SinCommit:
    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()


@pytest.fixture
async def api(sesion) -> AsyncGenerator[AsyncClient, None]:
    async def _misma_sesion():
        yield _SinCommit(sesion)

    app.dependency_overrides[get_db] = _misma_sesion
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _usuario(sesion, usuario: str = "logistica.prueba", rol: str = "LOGISTICA") -> Usuario:
    cuenta = Usuario(
        usuario=usuario,
        nombre_completo=f"Usuario {usuario}",
        rol=rol,
        hash_contrasena=autenticacion.hashear(CLAVE),
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


async def _parametro(sesion, clave: str, valor: int) -> None:
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    sesion.add(ParametroSistema(clave=clave, valor=str(valor), tipo_dato="ENTERO", descripcion="t"))
    await sesion.flush()


async def _login(api, usuario: str = "logistica.prueba", clave: str = CLAVE, **extra) -> Any:
    return await api.post(
        "/api/v1/auth/login", json={"usuario": usuario, "contrasena": clave, **extra}
    )


def _con(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Login ----------------------------------------------------------------------


async def test_la_contrasena_se_guarda_como_hash_argon2id(sesion) -> None:
    cuenta = await _usuario(sesion)

    assert cuenta.hash_contrasena.startswith("$argon2id$")
    assert CLAVE not in cuenta.hash_contrasena


async def test_con_credenciales_validas_se_entra_y_se_sabe_quien_es(api, sesion) -> None:
    await _usuario(sesion)

    respuesta = await _login(api, usuario="LOGISTICA.PRUEBA")  # sin distinguir mayúsculas

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "bearer" and cuerpo["usuario"]["rol"] == "LOGISTICA"
    yo = await api.get("/api/v1/auth/yo", headers=_con(cuerpo["token"]))
    assert yo.json()["usuario"] == "logistica.prueba"
    # La base guarda el hash del token, no el token.
    guardada = await sesion.scalar(select(Sesion).where(Sesion.id_usuario == yo.json()["id"]))
    assert guardada.hash_token != cuerpo["token"] and len(guardada.hash_token) == 64


async def test_el_error_es_el_mismo_falle_lo_que_falle(api, sesion) -> None:
    """No puede decirle a un tercero qué usuarios existen."""
    await _usuario(sesion)

    clave_mala = await _login(api, clave="otra-clave-larga")
    usuario_malo = await _login(api, usuario="no.existe")

    assert clave_mala.status_code == usuario_malo.status_code == 401
    assert clave_mala.json() == usuario_malo.json() == {"detail": MENSAJE_CREDENCIALES}


async def test_cada_fallo_se_cuenta_y_entrar_bien_lo_reinicia(api, sesion) -> None:
    cuenta = await _usuario(sesion)

    await _login(api, clave="otra-clave-larga")
    await _login(api, clave="otra-clave-larga")
    await sesion.refresh(cuenta)
    assert cuenta.intentos_fallidos == 2

    await _login(api)
    await sesion.refresh(cuenta)
    assert cuenta.intentos_fallidos == 0
    assert cuenta.ultimo_acceso is not None


async def test_superar_los_intentos_bloquea_aunque_la_clave_sea_buena(sesion) -> None:
    await _usuario(sesion)
    await _parametro(sesion, "login_intentos_maximos", 3)
    await _parametro(sesion, "login_bloqueo_min", 15)
    for _ in range(3):
        with pytest.raises(CredencialesInvalidas):
            await iniciar_sesion(sesion, "logistica.prueba", "mala-clave-x", instante=AHORA)

    with pytest.raises(CredencialesInvalidas):
        await iniciar_sesion(sesion, "logistica.prueba", CLAVE, instante=AHORA)
    # Pasado el bloqueo, entra.
    despues = AHORA + dt.timedelta(minutes=16)
    abierta = await iniciar_sesion(sesion, "logistica.prueba", CLAVE, instante=despues)
    assert abierta.usuario.bloqueado_hasta is None


async def test_un_usuario_inactivo_no_entra(sesion) -> None:
    cuenta = await _usuario(sesion)
    cuenta.activo = False
    await sesion.flush()

    with pytest.raises(CredencialesInvalidas):
        await iniciar_sesion(sesion, "logistica.prueba", CLAVE)


# --- Sesiones -------------------------------------------------------------------


async def test_sin_token_o_con_uno_falso_la_api_responde_401(api) -> None:
    sin_token = await api.get("/api/v1/pedidos")
    falso = await api.get("/api/v1/pedidos", headers=_con("no-es-un-token"))

    assert sin_token.status_code == falso.status_code == 401
    assert sin_token.headers["www-authenticate"] == "Bearer"


async def test_la_inactividad_cierra_la_sesion_y_el_uso_la_renueva(sesion) -> None:
    """Cuarto criterio: la pantalla que se refresca sigue; la abandonada se cierra."""
    await _usuario(sesion)
    await _parametro(sesion, "sesion_inactividad_min", 30)
    abierta = await iniciar_sesion(sesion, "logistica.prueba", CLAVE, instante=AHORA)

    await validar_token(sesion, abierta.token, instante=AHORA + dt.timedelta(minutes=25))
    await validar_token(sesion, abierta.token, instante=AHORA + dt.timedelta(minutes=50))
    with pytest.raises(SesionInvalida):
        await validar_token(sesion, abierta.token, instante=AHORA + dt.timedelta(minutes=81))

    assert abierta.sesion.cerrada_en is not None  # queda registrada como cerrada


async def test_recordar_sesion_no_cierra_por_inactividad_sino_por_duracion(sesion) -> None:
    await _usuario(sesion)
    await _parametro(sesion, "sesion_recordada_dias", 30)
    abierta = await iniciar_sesion(sesion, "logistica.prueba", CLAVE, recordar=True, instante=AHORA)

    await validar_token(sesion, abierta.token, instante=AHORA + dt.timedelta(days=5))
    with pytest.raises(SesionInvalida):
        await validar_token(sesion, abierta.token, instante=AHORA + dt.timedelta(days=31))


async def test_la_cuenta_compartida_admite_sesiones_simultaneas(api, sesion) -> None:
    """`compras@gutis.com`: varias personas, un usuario (decisión del 30/09)."""
    await _usuario(sesion, usuario="compras@gutis.com", rol="COMPRAS")
    una = (await _login(api, usuario="compras@gutis.com")).json()["token"]
    otra = (await _login(api, usuario="compras@gutis.com")).json()["token"]

    assert una != otra
    assert (await api.post("/api/v1/auth/logout", headers=_con(una))).status_code == 204
    assert (await api.get("/api/v1/auth/yo", headers=_con(una))).status_code == 401
    assert (await api.get("/api/v1/auth/yo", headers=_con(otra))).status_code == 200


# --- Cuentas, solo el Administrador --------------------------------------------


async def _admin(api, sesion) -> str:
    await _usuario(sesion, usuario="admin.prueba", rol="ADMINISTRADOR")
    return (await _login(api, usuario="admin.prueba")).json()["token"]


async def test_solo_el_administrador_mantiene_cuentas(api, sesion) -> None:
    await _usuario(sesion)
    token = (await _login(api)).json()["token"]

    respuesta = await api.get("/api/v1/usuarios", headers=_con(token))

    assert respuesta.status_code == 403


async def test_el_administrador_crea_una_cuenta_que_puede_entrar(api, sesion) -> None:
    token = await _admin(api, sesion)
    nuevo = {
        "usuario": "Planif.Nueva",
        "nombre_completo": "Planificación",
        "rol": "PLANIFICACION",
        "contrasena": "otra-clave-larga",
    }

    creado = await api.post("/api/v1/usuarios", json=nuevo, headers=_con(token))
    duplicado = await api.post("/api/v1/usuarios", json=nuevo, headers=_con(token))
    corta = await api.post(
        "/api/v1/usuarios",
        json={**nuevo, "usuario": "otra", "contrasena": "corta"},
        headers=_con(token),
    )

    assert creado.status_code == 201 and creado.json()["usuario"] == "planif.nueva"
    assert duplicado.status_code == 409
    assert corta.status_code == 422 and "al menos 10" in corta.text
    assert (await _login(api, usuario="planif.nueva", clave="otra-clave-larga")).status_code == 200


async def test_desactivar_un_usuario_corta_sus_sesiones_abiertas(api, sesion) -> None:
    token_admin = await _admin(api, sesion)
    cuenta = await _usuario(sesion)
    token = (await _login(api)).json()["token"]

    await api.patch(
        f"/api/v1/usuarios/{cuenta.id}", json={"activo": False}, headers=_con(token_admin)
    )

    assert (await api.get("/api/v1/auth/yo", headers=_con(token))).status_code == 401


async def test_reiniciar_la_contrasena_desbloquea_y_saca_a_quien_estaba(api, sesion) -> None:
    """El flujo de «¿Olvidó su contraseña?», sin correo."""
    token_admin = await _admin(api, sesion)
    cuenta = await _usuario(sesion)
    token_viejo = (await _login(api)).json()["token"]
    cuenta.bloqueado_hasta = dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)
    await sesion.flush()

    respuesta = await api.post(
        f"/api/v1/usuarios/{cuenta.id}/contrasena",
        json={"contrasena": "clave-nueva-larga"},
        headers=_con(token_admin),
    )

    assert respuesta.status_code == 204
    assert (await api.get("/api/v1/auth/yo", headers=_con(token_viejo))).status_code == 401
    assert (await _login(api, clave="clave-nueva-larga")).status_code == 200


async def test_un_administrador_no_puede_desactivarse_a_si_mismo(api, sesion) -> None:
    token = await _admin(api, sesion)
    yo = (await api.get("/api/v1/auth/yo", headers=_con(token))).json()

    respuesta = await api.patch(
        f"/api/v1/usuarios/{yo['id']}", json={"activo": False}, headers=_con(token)
    )

    assert respuesta.status_code == 409
