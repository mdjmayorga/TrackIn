"""Consulta una guía en TICA, sin tocar la base — `US-49`.

    python scripts/consultar_tica.py ZIVHYD017
    python scripts/consultar_tica.py ZIVHYD017 --dias 90

**Gratis y sin créditos**: TICA es la consulta pública de Hacienda. Son dos
peticiones si la guía todavía no aparece y tres si aparece y es hija (la
tercera resuelve la guía madre). Con el token de ShipsGo configurado, además
revisa si la aerolínea de la madre está en su catálogo —otra consulta gratuita—
para saber de antemano si un alta resolvería.

Para asociar la guía a un pedido y correr el ciclo completo, use
`asociar_referencia.py PEDIDO HAWB:NUMERO`.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.rastreo import shipsgo_aerolineas, transporte_http  # noqa: E402
from app.services.rastreo.colector_tica import ZONA_CR  # noqa: E402
from app.services.rastreo.shipsgo_cliente import ErrorShipsGo  # noqa: E402
from app.services.rastreo.tica_cliente import ErrorTICA  # noqa: E402

SEP = "=" * 72


def _forzar_salida_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")


async def _catalogo(prefijo: str | None) -> str:
    if prefijo is None:
        return "la guía madre no tiene forma de MAWB"
    if not settings.SHIPSGO_API_TOKEN:
        return "sin SHIPSGO_API_TOKEN: no se revisó el catálogo"
    async with transporte_http.crear_cliente_http() as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, settings.SHIPSGO_API_TOKEN)
        try:
            catalogo = await shipsgo_aerolineas.cargar(cliente)
        except ErrorShipsGo as exc:
            return f"no se pudo leer el catálogo ({exc.motivo})"
    aerolinea = catalogo.por_prefijo.get(prefijo)
    if aerolinea is None:
        return f"prefijo {prefijo} fuera del catálogo: un alta cobraría y devolvería vacío"
    estado = "ACTIVA — un alta resolvería" if aerolinea.activa else "INACTIVA — no dar de alta"
    return f"{prefijo} = {aerolinea.nombre}: {estado}"


async def principal(args: argparse.Namespace) -> int:
    hoy = dt.datetime.now(ZONA_CR).date()
    desde = hoy - dt.timedelta(days=args.dias)
    print(f"\n{SEP}\nTICA — guía {args.guia}, arribos del {desde} al {hoy}\n{SEP}")

    async with transporte_http.crear_cliente_http_tica() as http:
        cliente = transporte_http.crear_cliente_tica(http)
        try:
            rastreo = await cliente.rastrear(args.guia, desde, hoy)
        except ErrorTICA as exc:
            print(f"  FALLO: {exc.motivo} — {exc.detalle}")
            if exc.motivo == "acceso_bloqueado":
                print("  TICA rechazó la consulta. No se reintenta: ver tica_cliente.py.")
            return 1
        peticiones = cliente.peticiones

    if not rastreo.encontrado:
        print("  No aparece en ningún manifiesto del periodo.")
        print("  Es lo normal antes del arribo: la guía entra al transmitirse el manifiesto.")
        print(f"\n  Peticiones a TICA: {peticiones}")
        return 0

    for c in sorted(rastreo.conocimientos, key=lambda c: c.fecha_arribo):
        print(
            f"\n  Arribo        : {c.fecha_arribo}  (manifiesto {c.manifiesto}, depósito {c.deposito})"
        )
        print(f"  Tipo          : {c.tipo_documento}{' (guía hija)' if c.es_hija else ''}")
        print(f"  Aduana        : {c.aduana_codigo} {c.aduana_nombre}")
        print(f"  Agente        : {c.agente_nombre} ({c.agente_ruc})")
        print(f"  Embarque      : {c.embarque_codigo} {c.embarque_nombre}")
        print(f"  Estado        : {c.estado}")

    if rastreo.madre is not None:
        m = rastreo.madre
        print(f"\n  GUÍA MADRE    : {m.numero} ({m.tipo_documento})")
        print(f"  Transportista : {m.transportista_nombre}")
        print(f"  ShipsGo       : {await _catalogo(m.prefijo)}")

    print(f"\n  Peticiones a TICA: {peticiones}")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description="Consulta una guía en TICA. Gratis.")
    analizador.add_argument("guia", help="Número de la guía, hija o madre (p. ej. ZIVHYD017).")
    analizador.add_argument(
        "--dias", type=int, default=60, help="Días hacia atrás en que se busca el arribo."
    )
    argumentos = analizador.parse_args()
    _forzar_salida_utf8()
    logging.basicConfig(level=logging.WARNING, format="  [%(levelname)s] %(message)s")
    return asyncio.run(principal(argumentos))


if __name__ == "__main__":
    raise SystemExit(main())
