"""Verificación en vivo contra ShipsGo, gastando lo mínimo — `US-45` / `US-46`.

    python scripts/verificar_shipsgo.py                      # solo lo gratuito
    python scripts/verificar_shipsgo.py --leer 6734941       # lee un embarque ya registrado
    python scripts/verificar_shipsgo.py --alta BL:COSU6508789000   # ESTO CUESTA

**Por defecto no gasta un solo crédito.** Las tres comprobaciones de arranque
—token, catálogo de aerolíneas y listado de la cuenta— son consultas, y el
cobro de ShipsGo es por **embarque registrado**, no por consulta.

Dar de alta es lo único que cuesta, son 2 USD, y es irreversible: por eso va
detrás de un flag propio y pide confirmación escribiendo el número de
referencia. Con 50 créditos comprados, un `--alta` por equivocación es el 2 %
del presupuesto.

El listado de la cuenta importa más de lo que parece
-----------------------------------------------------

Dice **qué embarques ya están registrados**. Si la referencia que se quiere
probar ya figura, el alta devolvería `409 ALREADY_EXISTS` y **no cobraría**:
conviene mirar antes de asumir que hay que pagar.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.rastreo import shipsgo, shipsgo_aerolineas, transporte_http  # noqa: E402
from app.services.rastreo.shipsgo_cliente import ErrorShipsGo  # noqa: E402

SEP = "=" * 72


def _forzar_salida_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")


async def _gratis(cliente) -> None:
    """Las tres comprobaciones que no cuestan nada."""
    print(f"\n{SEP}\nCOMPROBACIONES GRATUITAS (no consumen crédito)\n{SEP}")

    print("\n1. Token y conectividad — GET /ocean/shipments?take=1")
    try:
        cuerpo = await cliente.consultar("/ocean/shipments?take=1")
    except ErrorShipsGo as exc:
        print(f"   FALLO: {exc.motivo} — {exc.detalle}")
        print("   Revise SHIPSGO_API_TOKEN en backend/.env")
        return
    total = (cuerpo.get("meta") or {}).get("total")
    print(f"   OK. La cuenta tiene {total} embarques registrados.")

    print("\n2. Catálogo de aerolíneas — GET /air/airlines")
    try:
        catalogo = await shipsgo_aerolineas.cargar(cliente)
        print(
            f"   OK. {len(catalogo.aerolineas)} aerolíneas, {len(catalogo.por_prefijo)} prefijos."
        )
    except ErrorShipsGo as exc:
        print(f"   FALLO: {exc.motivo} — {exc.detalle}")

    print("\n3. Embarques ya registrados en la cuenta")
    embarques = cuerpo.get("shipments") or []
    if not embarques:
        cuerpo_full = await cliente.consultar("/ocean/shipments?take=50")
        embarques = cuerpo_full.get("shipments") or []
    if not embarques:
        print("   Ninguno. Cualquier alta va a consumir un crédito.")
        return
    print(f"   {len(embarques)} encontrados:")
    for emb in embarques[:20]:
        ref = emb.get("booking_number") or emb.get("container_number") or emb.get("reference")
        print(f"     id={emb.get('id'):<10} {ref!s:22} {emb.get('status')}")
    print("\n   Si la referencia que quiere probar ya está aquí, el alta")
    print("   devolvería 409 y NO cobraría.")


async def _leer(cliente, id_embarque: int, aereo: bool) -> None:
    """Lee un embarque ya registrado y lo pasa por el intérprete. Gratis."""
    print(f"\n{SEP}\nLECTURA DEL EMBARQUE {id_embarque} (no consume crédito)\n{SEP}")
    shipment = await cliente.leer(id_embarque, aereo=aereo)

    if not shipsgo.esta_maduro(shipment):
        print("\n  El embarque está dado de alta pero todavía SIN DATOS.")
        print("  Es el tercer estado: se reintenta en ~2 minutos, no es un fallo.")
        return

    geojson = await cliente.leer_geojson(id_embarque, aereo=aereo)
    lectura = shipsgo.interpretar(shipment, geojson)

    print(f"\n  referencia    : {lectura.referencia}")
    print(f"  vía           : {lectura.via}")
    print(f"  estado fuente : {lectura.estado_fuente}")
    print(f"  transportista : {lectura.naviera}")
    print(f"  destino       : {lectura.puerto_destino} ({lectura.puerto_destino_nombre})")
    print(f"  ETA           : {lectura.eta}")
    print(f"  ETD           : {lectura.etd}")
    print(f"  etapa TrackIn : {lectura.etapa}")
    print(f"  arribado      : {lectura.arribado}")
    print(f"  posición      : {lectura.posicion or 'no disponible'}")
    print(f"  transbordo    : {lectura.hay_transbordo} {[v.nombre for v in lectura.vehiculos]}")
    if lectura.archivado_en:
        print(f"  ARCHIVADO     : {lectura.archivado_en} — puede dejar de ser consultable")

    print(f"\n  Hitos ({len(lectura.hitos)}):")
    for hito in lectura.hitos:
        marca = "ACT" if hito.ocurrido else "EST"
        print(
            f"    {hito.evento:5} {marca}  {hito.puerto!s:6} "
            f"{str(hito.instante)[:16]}  {hito.buque or ''}"
        )


async def _alta(cliente, tipo: str, numero: str) -> None:
    """Da de alta el embarque. **Esto cuesta un crédito.**"""
    print(f"\n{SEP}\n⚠  ALTA DE EMBARQUE — ESTO CONSUME UN CRÉDITO (~2 USD)\n{SEP}")
    print(f"\n  tipo   : {tipo}")
    print(f"  número : {numero}")
    print("\n  ShipsGo acepta y cobra cualquier referencia, incluso una inexistente.")
    print("  Escriba el número de referencia para confirmar, o cualquier otra cosa")
    print("  para cancelar:")
    confirmacion = input("  > ").strip()
    if confirmacion != numero:
        print("\n  Cancelado. No se gastó nada.")
        return

    try:
        resultado = await cliente.dar_de_alta(tipo, numero)
    except ErrorShipsGo as exc:
        print(f"\n  FALLO: {exc.motivo} — {exc.detalle}")
        return

    print(f"\n  id del embarque : {resultado.id_embarque}")
    if resultado.consumio_credito:
        print("  CONSUMIÓ UN CRÉDITO.")
    else:
        print("  Ya estaba registrado (409). NO se cobró.")
    print(f"\n  Para leerlo:  python scripts/verificar_shipsgo.py --leer {resultado.id_embarque}")
    print("  Espere ~2 minutos: recién dado de alta todavía no trae datos.")


async def principal(args: argparse.Namespace) -> int:
    if not settings.SHIPSGO_API_TOKEN:
        print(
            "No hay SHIPSGO_API_TOKEN configurado.\nDefínalo en backend/.env.",
            file=sys.stderr,
        )
        return 1

    async with transporte_http.crear_cliente_http() as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token=settings.SHIPSGO_API_TOKEN)

        if args.alta:
            if ":" not in args.alta:
                print(
                    "Formato: --alta TIPO:NUMERO (por ejemplo BL:COSU6508789000)", file=sys.stderr
                )
                return 1
            tipo, numero = args.alta.split(":", 1)
            await _alta(cliente, tipo.strip().upper(), numero.strip())
            return 0

        if args.leer:
            await _leer(cliente, args.leer, aereo=args.aereo)
            return 0

        await _gratis(cliente)
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(
        description="Verifica la integración con ShipsGo. Por defecto no gasta créditos.",
    )
    analizador.add_argument(
        "--alta",
        metavar="TIPO:NUMERO",
        help="Da de alta un embarque. CONSUME UN CRÉDITO (~2 USD). Pide confirmación.",
    )
    analizador.add_argument(
        "--leer", type=int, metavar="ID", help="Lee un embarque ya registrado. Gratis."
    )
    analizador.add_argument(
        "--aereo", action="store_true", help="Usa los endpoints aéreos en vez de los marítimos."
    )
    argumentos = analizador.parse_args()
    _forzar_salida_utf8()
    logging.basicConfig(level=logging.WARNING, format="  [%(levelname)s] %(message)s")

    return asyncio.run(principal(argumentos))


if __name__ == "__main__":
    raise SystemExit(main())
