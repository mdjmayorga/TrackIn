"""Una sola versión de TrackIn — `PROD-06`.

La versión vive en `app/__init__.py` y de ahí la toman `/health`, el arranque y
la documentación de la API. `pyproject.toml` y el `package.json` del panel la
repiten porque sus herramientas la piden: estas pruebas fallan si alguna queda
atrás, que es lo que pasó con la `0.1.0` desde el Sprint 0.
"""

from __future__ import annotations

import json
import re
import tomllib

from app import __version__
from app.core.config import BACKEND_DIR, REPO_ROOT, get_settings

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_la_version_es_semver() -> None:
    assert SEMVER.match(__version__), __version__


def test_la_configuracion_no_tiene_una_version_propia() -> None:
    version_configurada = get_settings().VERSION
    assert version_configurada == __version__


def test_pyproject_dice_la_misma_version() -> None:
    proyecto = tomllib.loads((BACKEND_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    assert proyecto["project"]["version"] == __version__


def test_el_panel_dice_la_misma_version() -> None:
    paquete = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    bloqueo = json.loads((REPO_ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    assert paquete["version"] == __version__
    assert bloqueo["version"] == __version__
    assert bloqueo["packages"][""]["version"] == __version__
