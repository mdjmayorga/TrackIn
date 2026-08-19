"""
Spike TG-10 / TG-11 - Fase 0: verificacion de entorno.

QUE PRUEBA
    Que el entorno local esta en condiciones de ejecutar los spikes de
    AISStream (TG-10) y OpenSky Network (TG-11), ANTES de hacer una sola
    llamada de red. La motivacion es concreta: en el intento previo con
    AISStream se perdio tiempo depurando la API cuando el problema podia
    estar en el .env. Este script separa esa capa del resto.

QUE **NO** HACE
    No abre sockets, no resuelve DNS, no llama a ninguna API y no escribe
    ni modifica el .env. Eso es responsabilidad de las fases 1 en adelante.
    Mezclar capas es exactamente lo que impide saber que fallo.

VERIFICA
    1. Que backend/.env exista y sea legible.
    2. Presencia de AISSTREAM_API_KEY.
    3. Credenciales OpenSky, aceptando LOS DOS esquemas de nombres:
         - OAuth2 (actual):   OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET
         - Basic  (retirado): OPENSKY_USERNAME  / OPENSKY_PASSWORD
       y reporta cual esta en uso sin asumir nada.
    4. Fallas silenciosas tipicas: espacios sobrantes, comillas envolventes
       accidentales, caracteres de control, valores placeholder sin llenar.
    5. Que httpx, websockets y python-dotenv importen, con su version.

SEGURIDAD
    Nunca imprime un secreto completo. Solo primeros 4 + ultimos 4
    caracteres. El JSON de evidencia guarda unicamente booleanos,
    longitudes y la mascara, jamas el valor.

USO
    python backend/scripts/spikes/check_env.py --network personal
    python backend/scripts/spikes/check_env.py --network gutis

SALIDA
    Codigo 0 si el entorno sirve para arrancar; 1 si hay algo bloqueante.
    Evidencia en backend/scripts/spikes/output/check_env_<red>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SPIKES_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SPIKES_DIR.parents[1]
ENV_PATH = BACKEND_DIR / ".env"
OUTPUT_DIR = SPIKES_DIR / "output"

SEP = "=" * 72
SUB = "-" * 72

PLACEHOLDERS = {
    "changeme", "change_me", "your_key_here", "your_api_key", "tu_api_key",
    "xxx", "xxxx", "todo", "tbd", "replace_me", "<your_key>", "none", "null",
}

REQUIRED_PACKAGES = ["httpx", "websockets", "dotenv"]


def mask(value: str) -> str:
    """Devuelve una mascara segura del secreto: 4 primeros + 4 ultimos."""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "..." + value[-4:]


def read_raw_env(path: Path) -> tuple[dict[str, str], list[str]]:
    """
    Parsea el .env crudo, SIN normalizar, para poder detectar problemas de
    formato que python-dotenv corrige en silencio (comillas, espacios).

    Devuelve (variables, errores_de_lectura).
    """
    raw: dict[str, str] = {}
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append("El archivo no es UTF-8 valido: " + str(exc))
        return raw, errors
    except OSError as exc:
        errors.append("No se pudo leer el archivo: " + str(exc))
        return raw, errors

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            errors.append("Linea " + str(lineno) + ": sin '=' , se ignora")
            continue
        key, _, value = stripped.partition("=")
        raw[key.strip()] = value
    return raw, errors


def diagnose(name: str, raw_value: str | None) -> dict:
    """
    Diagnostica una sola variable. Devuelve un dict con el estado y la lista
    de problemas detectados. 'present' es False si falta o esta vacia.
    """
    result: dict = {
        "name": name,
        "present": False,
        "length": 0,
        "masked": None,
        "issues": [],
    }
    if raw_value is None:
        return result

    value = raw_value
    issues: list[str] = []

    if value != value.strip():
        issues.append("tiene espacios al inicio o al final")
    value = value.strip()

    for quote in ('"', "'"):
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            issues.append("esta envuelto en comillas " + quote + " (dotenv las quita, pero revisalo)")
            value = value[1:-1]

    if not value:
        result["issues"] = ["esta vacia"]
        return result

    if value.lower() in PLACEHOLDERS:
        issues.append("es un valor placeholder sin llenar")
    elif value.startswith("<") and value.endswith(">"):
        issues.append("tiene forma de placeholder <...> sin reemplazar")

    if any(ord(c) < 32 for c in value):
        issues.append("contiene caracteres de control (posible salto de linea pegado)")

    if any(c.isspace() for c in value):
        issues.append("contiene espacios internos")

    if not value.isascii():
        issues.append("contiene caracteres no-ASCII")

    result.update(
        present=True,
        length=len(value),
        masked=mask(value),
        issues=issues,
    )
    return result


def print_var(diag: dict, expected_len: int | None = None) -> None:
    if not diag["present"]:
        status = "[FALTA]"
    elif diag["issues"]:
        status = "[REVISAR]"
    else:
        status = "[OK]"
    masked = diag["masked"] or "-"
    length = str(diag["length"]) + " chars" if diag["present"] else ""
    print("  {:<26} {:<10} {:<16} {}".format(diag["name"], status, masked, length))
    pad = " " * 26 + " " * 11
    if expected_len and diag["present"] and diag["length"] != expected_len:
        print("  " + pad + "-> longitud esperada ~" + str(expected_len) + ", hay " + str(diag["length"]))
    for issue in diag["issues"]:
        print("  " + pad + "-> " + issue)


def check_packages() -> tuple[list[dict], bool]:
    """Verifica que las librerias necesarias importen. No instala nada."""
    from importlib import import_module
    from importlib.metadata import PackageNotFoundError, version

    dist_names = {"dotenv": "python-dotenv"}
    results: list[dict] = []
    all_ok = True
    for mod in REQUIRED_PACKAGES:
        entry: dict = {"module": mod, "importable": False, "version": None, "error": None}
        try:
            import_module(mod)
            entry["importable"] = True
        except ImportError as exc:
            entry["error"] = str(exc)
            all_ok = False
        if entry["importable"]:
            try:
                entry["version"] = version(dist_names.get(mod, mod))
            except PackageNotFoundError:
                entry["version"] = "desconocida"
        results.append(entry)
    return results, all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike Fase 0: verificacion de entorno TrackIn")
    parser.add_argument(
        "--network",
        choices=["personal", "gutis"],
        required=True,
        help="Red desde la que se ejecuta. Se estampa en la evidencia para el A/B.",
    )
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    blocking: list[str] = []
    warnings: list[str] = []

    print(SEP)
    print(" TrackIn - Spikes TG-10 / TG-11 - Fase 0: verificacion de entorno")
    print(SEP)
    print("  Fecha (UTC) : " + timestamp)
    print("  Red         : " + args.network)
    print("  Python      : " + sys.version.split()[0])
    print("  .env        : " + str(ENV_PATH))

    if not ENV_PATH.is_file():
        print("  Estado      : [FALTA] el archivo no existe")
        print(SEP)
        print()
        print("  BLOQUEANTE: sin backend/.env no se puede continuar.")
        print("  Copiar backend/.env.example a backend/.env y llenar las credenciales.")
        return 1

    raw, read_errors = read_raw_env(ENV_PATH)
    print("  Estado      : [OK] existe, " + str(len(raw)) + " variables parseadas")

    for err in read_errors:
        warnings.append(".env: " + err)

    print(SUB)
    print("  CREDENCIALES - AISStream (TG-10)")
    print(SUB)
    ais = diagnose("AISSTREAM_API_KEY", raw.get("AISSTREAM_API_KEY"))
    print_var(ais, expected_len=40)
    if not ais["present"]:
        blocking.append("Falta AISSTREAM_API_KEY: TG-10 no puede arrancar.")
    elif any("placeholder" in i for i in ais["issues"]):
        blocking.append("AISSTREAM_API_KEY es un placeholder sin reemplazar: TG-10 no puede arrancar.")
    elif ais["issues"]:
        warnings.append("AISSTREAM_API_KEY tiene problemas de formato (ver detalle arriba).")

    print(SUB)
    print("  CREDENCIALES - OpenSky Network (TG-11)")
    print(SUB)
    oauth = {k: diagnose(k, raw.get(k)) for k in ("OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET")}
    basic = {k: diagnose(k, raw.get(k)) for k in ("OPENSKY_USERNAME", "OPENSKY_PASSWORD")}

    for diag in oauth.values():
        print_var(diag)
    for diag in basic.values():
        print_var(diag)

    has_oauth = all(d["present"] for d in oauth.values())
    has_basic = all(d["present"] for d in basic.values())

    print()
    if has_oauth:
        scheme = "oauth2"
        print("  Esquema detectado: OAuth2 client_credentials  [correcto]")
        if has_basic:
            print("  Ademas hay claves Basic residuales: conviene limpiarlas del .env.")
            warnings.append("Conviven claves OAuth2 y Basic en el .env; las Basic estan obsoletas.")
    elif has_basic:
        scheme = "basic_legacy"
        print("  Esquema detectado: Basic auth (OPENSKY_USERNAME / OPENSKY_PASSWORD)")
        print("  ATENCION: OpenSky retiro la autenticacion Basic. Si el client_id y el")
        print("            client_secret que generaste estan guardados bajo estos nombres,")
        print("            hay que renombrar las claves antes de la Fase 1.")
        blocking.append(
            "OpenSky: no hay OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET. "
            "Renombrar las claves del .env (requiere tu OK) antes de TG-11 Fase 1."
        )
    else:
        scheme = "ninguno"
        print("  Esquema detectado: NINGUNO completo")
        blocking.append("Faltan credenciales de OpenSky: TG-11 no puede arrancar.")

    print(SUB)
    print("  DEPENDENCIAS")
    print(SUB)
    packages, packages_ok = check_packages()
    for entry in packages:
        status = "[OK]" if entry["importable"] else "[FALTA]"
        ver = entry["version"] or "-"
        print("  {:<26} {:<10} {}".format(entry["module"], status, ver))
        if entry["error"]:
            print("  " + " " * 37 + "-> " + entry["error"])
    if not packages_ok:
        blocking.append("Faltan librerias. NO instalar nada sin confirmarlo primero.")

    print(SEP)
    print("  RESULTADO")
    print(SEP)
    if warnings:
        print("  Advertencias (no bloquean):")
        for item in warnings:
            print("    - " + item)
    if blocking:
        print("  BLOQUEANTES:")
        for item in blocking:
            print("    - " + item)
        print()
        print("  Fase 0 NO superada. Resolver lo anterior antes de la Fase 1.")
    else:
        print("  Fase 0 superada. Entorno listo para la Fase 1.")
    print(SEP)

    def strip_name(d: dict) -> dict:
        return {k: v for k, v in d.items() if k != "name"}

    evidence = {
        "spike_phase": "0-check-env",
        "timestamp_utc": timestamp,
        "network_profile": args.network,
        "python_version": sys.version.split()[0],
        "env_file": str(ENV_PATH),
        "env_vars_parsed": len(raw),
        "aisstream": strip_name(ais),
        "opensky_scheme": scheme,
        "opensky_oauth": {k: strip_name(d) for k, d in oauth.items()},
        "opensky_basic": {k: strip_name(d) for k, d in basic.items()},
        "packages": packages,
        "warnings": warnings,
        "blocking": blocking,
        "passed": not blocking,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / ("check_env_" + args.network + ".json")
    try:
        out_file.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        print("  Evidencia: " + str(out_file))
    except OSError as exc:
        print("  [!] No se pudo escribir la evidencia: " + str(exc))

    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
