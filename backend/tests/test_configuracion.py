"""Pruebas de la configuración — `US-17` (RF-24, RNF-07, RNF-15).

Dos cosas distintas, las dos del arranque:

- que la configuración incompleta **impida arrancar** y diga qué falta, todo de
  una vez;
- que ninguna credencial viva en el repositorio.

Las pruebas de arranque se aíslan de **las dos** fuentes de configuración de la
máquina: el `.env` (`_env_file=None`) y las variables de entorno reales, que
borra `_sin_entorno`. CI define `SECRET_KEY` y `POSTGRES_PASSWORD` en
`ci.yml`, y sin borrarlas una prueba de «falta X» pasa o falla según dónde corra.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from app.core.config import (
    BACKEND_DIR,
    PASSWORD_DE_DESARROLLO,
    REPO_ROOT,
    SECRET_KEY_DE_DESARROLLO,
    Settings,
)


@pytest.fixture(autouse=True)
def _sin_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borra de este proceso cada variable que `Settings` leería."""
    for nombre in Settings.model_fields:
        monkeypatch.delenv(nombre, raising=False)


def _config(**valores) -> Settings:
    return Settings(_env_file=None, **valores)


def _mensaje(**valores) -> str:
    with pytest.raises(ValidationError) as error:
        _config(**valores)
    return str(error.value)


# --- La configuración incompleta no arranca ---------------------------------


def test_el_desarrollo_arranca_con_los_valores_del_codigo() -> None:
    assert _config().problemas() == []


def test_un_valor_de_la_plantilla_no_cuenta_como_configurado() -> None:
    """`cp .env.example .env` sin completar encendería ShipsGo con `<placeholder>`."""
    mensaje = _mensaje(SHIPSGO_API_TOKEN="<placeholder>")

    assert "SHIPSGO_API_TOKEN todavía tiene el valor de la plantilla" in mensaje


def test_una_credencial_a_medias_dice_cual_falta() -> None:
    assert "OPENSKY_CLIENT_SECRET falta" in _mensaje(OPENSKY_CLIENT_ID="cliente")
    assert "OPENSKY_CLIENT_ID falta" in _mensaje(OPENSKY_CLIENT_SECRET="secreto")


def test_produccion_no_acepta_los_secretos_de_desarrollo() -> None:
    """Y los informa **juntos**: nadie debería arrancar dos veces para enterarse."""
    mensaje = _mensaje(ENVIRONMENT="production")

    assert "SECRET_KEY falta" in mensaje
    assert "POSTGRES_PASSWORD falta" in mensaje


def test_en_produccion_una_database_url_exime_de_la_password_suelta() -> None:
    config = _config(
        ENVIRONMENT="production",
        SECRET_KEY="k" * 64,
        DATABASE_URL="postgresql+asyncpg://u:p@db/trackin",
    )

    assert config.problemas() == []


def test_produccion_completa_arranca() -> None:
    config = _config(ENVIRONMENT="production", SECRET_KEY="k" * 64, POSTGRES_PASSWORD="p" * 32)

    assert config.problemas() == []


def test_varios_problemas_salen_en_un_solo_mensaje() -> None:
    mensaje = _mensaje(
        ENVIRONMENT="production",
        INGESTA_ADAPTADOR="ztracking",
        AISSTREAM_API_KEY="<placeholder>",
    )

    for variable in ("AISSTREAM_API_KEY", "ZTRACKING_RUTA", "SECRET_KEY", "POSTGRES_PASSWORD"):
        assert variable in mensaje


# --- Ninguna credencial en el repositorio -----------------------------------


def _git(*argumentos: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *argumentos], cwd=REPO_ROOT, capture_output=True, check=False)


requiere_git = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(),
    reason="hace falta el repositorio de git",
)


@requiere_git
@pytest.mark.parametrize("ruta", [".env", "backend/.env", "frontend/.env"])
def test_los_env_reales_estan_ignorados(ruta: str) -> None:
    assert _git("check-ignore", "-q", ruta).returncode == 0, f"{ruta} no está en .gitignore"


@requiere_git
def test_ninguna_credencial_configurada_aparece_en_un_archivo_versionado() -> None:
    """Busca los valores de los `.env` de esta máquina en lo que git versiona.

    Se leen **los archivos** y no `settings`: `settings` también toma las
    variables de entorno, y en CI esas son los valores de prueba que `ci.yml`
    declara —versionados a propósito—. Las credenciales reales viven solo en los
    `.env`, que es donde se cuelan. Así se encontró el 29/09 el client ID de
    OpenSky en la salida de un spike. En CI no hay `.env` y la prueba se salta.
    """
    configurados: dict[str, str | None] = {}
    for archivo in (BACKEND_DIR / ".env", REPO_ROOT / ".env"):
        if archivo.is_file():
            configurados.update(dotenv_values(archivo))
    secretos = {
        nombre: valor.encode()
        for nombre, valor in configurados.items()
        if re.search(r"KEY|TOKEN|SECRET|PASSWORD|CLIENT_ID", nombre)
        and valor
        and valor not in (SECRET_KEY_DE_DESARROLLO, PASSWORD_DE_DESARROLLO)
        and not valor.startswith("<")
        # Un valor corto aparecería por casualidad en cualquier binario.
        and len(valor) >= 12
    }
    if not secretos:
        pytest.skip("esta máquina no tiene credenciales en sus .env")

    versionados = _git("ls-files", "-z").stdout.decode().split("\0")
    filtrados = []
    for ruta in filter(None, versionados):
        archivo = REPO_ROOT / ruta
        if not archivo.is_file():
            continue
        contenido = archivo.read_bytes()
        filtrados.extend(
            f"{nombre} en {ruta}" for nombre, valor in secretos.items() if valor in contenido
        )

    assert filtrados == []


def test_el_error_de_arranque_no_copia_las_credenciales() -> None:
    """El mensaje termina en un log: no puede llevar los valores configurados."""
    mensaje = _mensaje(SHIPSGO_API_TOKEN="<placeholder>", AISSTREAM_API_KEY="clave-secreta-123")

    assert "clave-secreta-123" not in mensaje
    assert "input_value" not in mensaje
