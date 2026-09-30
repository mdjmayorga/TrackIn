r"""Crea un usuario desde la consola — `US-42`.

    .venv\Scripts\python scripts\crear_usuario.py admin "Mariano Mayorga" ADMINISTRADOR
    .venv\Scripts\python scripts\crear_usuario.py compras@gutis.com "Compras" COMPRAS --correo compras@gutis.com

Se corre con el Python de `backend\.venv`, desde `backend`: el Python global de
la máquina no tiene las dependencias del proyecto.

Existe para el **primer Administrador**: las cuentas se mantienen desde la API,
pero solo un Administrador puede crearlas, y sin este script nadie podría
entrar la primera vez.

La contraseña se pide por teclado sin mostrarla. **No se acepta como argumento**:
quedaría en el historial de la consola. Para automatizar, se lee de la variable
de entorno `TRACKIN_CONTRASENA_INICIAL` si existe.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select  # noqa: E402

from app.db.session import AsyncSessionLocal, dispose_engine, engine  # noqa: E402
from app.models.enums import ROLES  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import autenticacion  # noqa: E402


def _contrasena() -> str:
    desde_entorno = os.environ.get("TRACKIN_CONTRASENA_INICIAL")
    if desde_entorno:
        return desde_entorno
    primera = getpass.getpass("Contraseña: ")
    if primera != getpass.getpass("Repítala: "):
        sys.exit("Las contraseñas no coinciden.")
    return primera


async def principal(args: argparse.Namespace) -> int:
    try:
        hash_contrasena = autenticacion.hashear(_contrasena())
    except autenticacion.ContrasenaDebil as exc:
        print(exc, file=sys.stderr)
        return 1

    nombre = args.usuario.strip().lower()
    async with AsyncSessionLocal() as sesion:
        if await sesion.scalar(select(Usuario).where(func.lower(Usuario.usuario) == nombre)):
            print(f"Ya existe el usuario {nombre}.", file=sys.stderr)
            return 1
        sesion.add(
            Usuario(
                usuario=nombre,
                nombre_completo=args.nombre,
                correo=args.correo.lower() if args.correo else None,
                rol=args.rol,
                hash_contrasena=hash_contrasena,
            )
        )
        await sesion.commit()
    print(f"Usuario {nombre} creado con el rol {args.rol}.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description="Crea un usuario de TrackIn.")
    analizador.add_argument("usuario", help="Nombre de inicio de sesión.")
    analizador.add_argument("nombre", help="Nombre completo.")
    analizador.add_argument("rol", choices=ROLES)
    analizador.add_argument("--correo")
    args = analizador.parse_args()

    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    async def _correr() -> int:
        try:
            return await principal(args)
        finally:
            await dispose_engine()

    return asyncio.run(_correr())


if __name__ == "__main__":
    raise SystemExit(main())
