"""
Helpers compartidos por los scripts de spike TG-10 (AISStream) y TG-11 (OpenSky).

POR QUE EXISTE
    Los ~12 scripts de spike necesitan lo mismo: leer backend/.env, enmascarar
    secretos, imprimir una cabecera legible y guardar evidencia JSON con el
    mismo esquema. Centralizarlo evita repetir plomeria y, sobre todo,
    garantiza que todas las evidencias tengan formato identico: eso es lo que
    hace comparables las corridas desde red personal y desde red Gutis.

ESTO NO ES CODIGO PRODUCTIVO. Vive en scripts/spikes/ y es descartable.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SPIKES_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SPIKES_DIR.parents[1]
ENV_PATH = BACKEND_DIR / ".env"

SEP = "=" * 72
SUB = "-" * 72


def utc_now() -> str:
    """Timestamp UTC ISO-8601 con segundos. Todas las evidencias lo usan."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mask(value: str) -> str:
    """Mascara segura de un secreto: 4 primeros + 4 ultimos. Nunca el valor."""
    if not value:
        return "-"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "..." + value[-4:]


def load_env() -> dict[str, str]:
    """
    Carga backend/.env sin contaminar os.environ.

    Falla ruidosamente si el archivo no existe: preferimos un error claro
    ahora a un None inexplicable tres capas mas abajo.
    """
    try:
        from dotenv import dotenv_values
    except ImportError:
        sys.exit(
            "[FATAL] Falta python-dotenv.\n"
            "        Activar backend/.venv antes de correr los spikes."
        )

    if not ENV_PATH.is_file():
        sys.exit("[FATAL] No existe " + str(ENV_PATH))

    values = dotenv_values(ENV_PATH)
    return {k: v for k, v in values.items() if v is not None}


def require(env: dict[str, str], name: str) -> str:
    """
    Devuelve una variable obligatoria del .env o aborta con un mensaje util.

    Aborta tambien si el valor quedo como placeholder <...>, porque ese caso
    produce un 401 confuso en vez de un error de configuracion evidente.
    """
    value = (env.get(name) or "").strip()
    if not value:
        sys.exit(
            "[FATAL] Falta " + name + " en backend/.env\n"
            "        Correr primero: python backend/scripts/spikes/check_env.py --network <red>"
        )
    if value.startswith("<") and value.endswith(">"):
        sys.exit(
            "[FATAL] " + name + " sigue siendo un placeholder sin reemplazar.\n"
            "        Poner el valor real en backend/.env antes de continuar."
        )
    return value


def network_arg(description: str) -> argparse.Namespace:
    """
    Parser comun. --network es obligatorio a proposito: sin ese dato la
    evidencia no sirve para el A/B personal-vs-Gutis, que es el nucleo
    del diagnostico de TG-10.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--network",
        choices=["personal", "gutis"],
        required=True,
        help="Red desde la que se ejecuta. Se estampa en la evidencia.",
    )
    return parser.parse_args()


def header(title: str, network: str, extra: dict[str, str] | None = None) -> str:
    """Imprime la cabecera estandar y devuelve el timestamp de la corrida."""
    timestamp = utc_now()
    print(SEP)
    print(" " + title)
    print(SEP)
    print("  Fecha (UTC) : " + timestamp)
    print("  Red         : " + network)
    for key, value in (extra or {}).items():
        print("  {:<12}: {}".format(key, value))
    return timestamp


def save_evidence(subdir: str, filename: str, data: dict[str, Any]) -> Path | None:
    """
    Guarda la evidencia en scripts/spikes/<subdir>/output/<filename>.

    El nombre incluye la red para no pisar la corrida anterior: necesitamos
    conservar las dos para compararlas.
    """
    out_dir = SPIKES_DIR / subdir / "output"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / filename
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print("  Evidencia: " + str(out_file))
        return out_file
    except OSError as exc:
        print("  [!] No se pudo escribir la evidencia: " + str(exc))
        return None


def describe_http_error(exc: Exception) -> tuple[str, str]:
    """
    Clasifica un fallo de httpx en (categoria, explicacion).

    El punto es no reportar "no funciono": para el spike importa distinguir
    un DNS bloqueado de un timeout de un rechazo TLS, porque cada uno apunta
    a una causa distinta en la red corporativa.
    """
    import httpx

    if isinstance(exc, httpx.ConnectTimeout):
        return "connect_timeout", "TCP no completo el handshake (posible firewall descartando SYN)"
    if isinstance(exc, httpx.ReadTimeout):
        return "read_timeout", "Conexion abierta pero el servidor no respondio a tiempo"
    if isinstance(exc, httpx.ConnectError):
        detail = str(exc).lower()
        if "name" in detail or "resolve" in detail or "getaddrinfo" in detail:
            return "dns_error", "No se pudo resolver el hostname (posible DNS corporativo bloqueando)"
        return "connect_error", "No se pudo establecer la conexion TCP/TLS"
    if isinstance(exc, httpx.ProxyError):
        return "proxy_error", "Fallo el proxy configurado en el sistema"
    if isinstance(exc, httpx.TooManyRedirects):
        return "redirect_loop", "Bucle de redirecciones (tipico de portal cautivo corporativo)"
    if isinstance(exc, httpx.HTTPError):
        return "http_error", "Error HTTP generico: " + type(exc).__name__
    return "unknown", type(exc).__name__ + ": " + str(exc)
