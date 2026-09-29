"""Arranque del worker de rastreo — `python -m app.workers`.

Arma los clientes con lo que haya configurado y corre el ciclo de
`app.workers.rastreo`:

- **TICA** siempre: es la consulta pública de Hacienda, sin credenciales.
- **ShipsGo** solo con `SHIPSGO_API_TOKEN`. Sin token, sus elementos se omiten
  con `fuente_sin_configurar` y el resto sigue.

El catálogo de aerolíneas de ShipsGo se lee una vez al arrancar (gratis): sirve
para señalar si la guía madre que resuelve TICA se podría seguir en ShipsGo.

    python -m app.workers                      # cada 60 s, hasta Ctrl+C
    python -m app.workers --una-vez            # un ciclo y termina
    python -m app.workers --intervalo 300      # cada 5 minutos
    python -m app.workers --sin-tica           # solo ShipsGo
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.core.config import settings
from app.db.session import AsyncSessionLocal, dispose_engine, engine
from app.services import parametros
from app.services.rastreo import shipsgo_aerolineas, transporte_http
from app.services.rastreo.shipsgo_cliente import ErrorShipsGo
from app.workers import rastreo

logger = logging.getLogger("app.workers")


async def _revisar_parametros() -> None:
    """Dice al arrancar qué filas de `parametros_sistema` no se pueden usar (`US-17`)."""
    try:
        async with AsyncSessionLocal() as sesion:
            problemas = await parametros.revisar(sesion)
    except Exception:
        # Sin base el ciclo fallará igual y lo dirá; esto es solo un aviso.
        logger.exception("Worker: no se pudo revisar parametros_sistema.")
        return
    for problema in problemas:
        logger.error("Worker: parámetro mal configurado — %s", problema)


async def principal(args: argparse.Namespace) -> int:
    await _revisar_parametros()
    async with (
        transporte_http.crear_cliente_http() as http,
        transporte_http.crear_cliente_http_tica() as http_tica,
    ):
        fuentes = rastreo.Fuentes()
        if settings.SHIPSGO_API_TOKEN:
            fuentes.shipsgo = transporte_http.crear_cliente_shipsgo(
                http, settings.SHIPSGO_API_TOKEN
            )
            try:
                fuentes.catalogo = await shipsgo_aerolineas.cargar(fuentes.shipsgo)
            except ErrorShipsGo as exc:
                # Sin catálogo no se bloquea nada: solo no se informa.
                logger.warning(
                    "Worker: no se pudo leer el catálogo de aerolíneas (%s).", exc.motivo
                )
        else:
            logger.warning("Worker: sin SHIPSGO_API_TOKEN; ShipsGo queda fuera.")
        if not args.sin_tica:
            fuentes.tica = transporte_http.crear_cliente_tica(http_tica)

        logger.info(
            "Worker: arranca con %s, cada %.0f s.",
            ", ".join(n for n, c in (("ShipsGo", fuentes.shipsgo), ("TICA", fuentes.tica)) if c)
            or "ninguna fuente",
            args.intervalo,
        )
        try:
            await rastreo.ejecutar(
                AsyncSessionLocal,
                fuentes,
                intervalo_s=args.intervalo,
                ciclos=1 if args.una_vez else None,
            )
        finally:
            await dispose_engine()
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(
        prog="python -m app.workers", description="Worker de rastreo de TrackIn."
    )
    analizador.add_argument("--una-vez", action="store_true", help="Corre un solo ciclo.")
    analizador.add_argument(
        "--intervalo",
        type=float,
        default=rastreo.INTERVALO_S,
        help="Segundos entre ciclos (defecto: 60).",
    )
    analizador.add_argument("--sin-tica", action="store_true", help="No consulta TICA.")
    argumentos = analizador.parse_args()

    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    # En desarrollo el engine va con `echo=True` (`DEBUG`), y el eco ignora el
    # nivel del logger: hay que apagarlo en el engine. Lo que el worker tiene
    # que dejar ver es el ciclo, no cada SELECT.
    engine.echo = False
    try:
        return asyncio.run(principal(argumentos))
    except KeyboardInterrupt:
        logger.info("Worker: detenido.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
