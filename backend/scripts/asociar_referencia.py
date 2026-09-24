"""Asocia una referencia de embarque a un pedido y corre el ciclo — RF-03.

    python scripts/asociar_referencia.py --resumen
    python scripts/asociar_referencia.py TRK-4500016171-090 CONTENEDOR:MRSU8132490
    python scripts/asociar_referencia.py TRK-... BL:COSU123456789 --leer 6734887

`asociar_referencia` existe como servicio desde `US-01`, pero hasta `US-16`
(Sprint 5) no tiene endpoint. Este script es esa entrada mientras tanto, y de
paso permite lo que ninguna prueba unitaria puede: **ver el ciclo completo
sobre datos reales**, de la referencia a la fecha proyectada.

**No gasta créditos, y no puede gastarlos.** Aquí no se da de alta nada: dar de
alta es lo que cobra ShipsGo (~2 USD) y vive en `registro_embarque`, detrás del
flag `--alta` de `verificar_shipsgo.py`, que pide confirmación escrita. Este
script solo asocia —que es local— y con `--leer` **consulta** un embarque que
ya está registrado en la cuenta, que es gratis.

Qué ejercita `--leer`
---------------------

La cadena entera, en el orden en que corre en producción:

1. `asociacion` vincula la referencia y mueve la etapa fuera de `SIN_TRACKING`.
2. `colector_shipsgo.procesar` interpreta la respuesta: hitos, ETA, posición.
3. `recalculo.recalcular` aplica RN-01 y el semáforo.
4. `arribo.evaluar` decide si llegó, por hito o por geocerca (RN-05).

Es la única forma de comprobar que las piezas encajan. Cada una está probada
por separado; que el conjunto funcione es otra afirmación.
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

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402
from app.models.elemento_rastreado import ElementoRastreado  # noqa: E402
from app.models.pedido_transito import PedidoTransito  # noqa: E402
from app.services import arribo, asociacion, recalculo  # noqa: E402
from app.services.rastreo import colector_shipsgo, transporte_http  # noqa: E402
from app.services.rastreo.shipsgo_cliente import ErrorShipsGo  # noqa: E402

SEP = "=" * 72


def _forzar_salida_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")


async def _resumen(sesion) -> None:
    """Qué pedidos hay para asociar y cuáles ya lo están."""
    pedidos = list(
        await sesion.scalars(
            select(PedidoTransito)
            .options(selectinload(PedidoTransito.destino))
            .where(PedidoTransito.ausente_desde.is_(None))
            .order_by(PedidoTransito.via_transporte, PedidoTransito.tracking_interno)
        )
    )
    libres = [p for p in pedidos if p.id_elemento_rastreado is None]
    asociados = [p for p in pedidos if p.id_elemento_rastreado is not None]

    print(f"\n{SEP}\nPEDIDOS PRESENTES: {len(pedidos)}\n{SEP}")
    print(f"\n  Sin referencia : {len(libres)}")
    print(f"  Con referencia : {len(asociados)}")

    if asociados:
        print("\n  Ya asociados:")
        for p in asociados:
            elemento = await sesion.get(ElementoRastreado, p.id_elemento_rastreado)
            ref = (
                f"{elemento.tipo_tracking_externo}:{elemento.tracking_externo}" if elemento else "?"
            )
            print(f"    {p.tracking_interno:22} {ref:28} {p.etapa_viaje}")

    print("\n  Candidatos (primeros 15 de cada vía):")
    for via in ("MARITIMO", "AEREO", "TERRESTRE"):
        de_la_via = [p for p in libres if p.via_transporte == via]
        if not de_la_via:
            continue
        print(f"\n    --- {via} ({len(de_la_via)}) ---")
        for p in de_la_via[:15]:
            destino = p.destino.codigo if p.destino else "—"
            print(f"    {p.tracking_interno:22} {destino:8} {p.incoterm or '—':10} {p.etapa_viaje}")


async def _buscar_pedido(sesion, clave: str) -> PedidoTransito | None:
    """Por tracking interno, o por `OC-POSICION` si es más cómodo escribirlo."""
    consulta = select(PedidoTransito).options(selectinload(PedidoTransito.destino))
    pedido = await sesion.scalar(consulta.where(PedidoTransito.tracking_interno == clave))
    if pedido is not None:
        return pedido
    if "-" in clave:
        oc, _, posicion = clave.rpartition("-")
        if posicion.isdigit():
            return await sesion.scalar(
                consulta.where(
                    PedidoTransito.oc_numero == oc,
                    PedidoTransito.posicion_oc == int(posicion),
                )
            )
    return None


def _mostrar(titulo: str, pedido: PedidoTransito) -> None:
    print(f"\n  --- {titulo} ---")
    print(f"    etapa              : {pedido.etapa_viaje}")
    print(f"    estado calculado   : {pedido.estado_calculado}")
    print(f"    cumplimiento       : {pedido.estado_cumplimiento or '—'}")
    print(f"    fecha comprometida : {pedido.fecha_entrega_pedido}")
    print(f"    fecha proyectada   : {pedido.fecha_proyectada_disponible or '—'}")
    print(f"    ETA utilizada      : {pedido.eta_utilizada or '—'}")
    print(f"    ATA confirmada     : {pedido.ata_confirmada or '—'}")
    print(f"    ATA inferida       : {pedido.ata_inferida or '—'}")


async def _leer_y_procesar(sesion, pedido: PedidoTransito, id_embarque: int, aereo: bool) -> None:
    """Consulta el embarque ya registrado y corre la cadena. Gratis."""
    if not settings.SHIPSGO_API_TOKEN:
        print("\n  Sin SHIPSGO_API_TOKEN: no se puede leer. Se queda en la asociación.")
        return

    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    if elemento is None:
        print("\n  El pedido no quedó con elemento rastreado; nada que leer.")
        return

    print(f"\n{SEP}\n2. LECTURA DE SHIPSGO (embarque {id_embarque}, no consume crédito)\n{SEP}")
    async with transporte_http.crear_cliente_http() as http:
        cliente = transporte_http.crear_cliente_shipsgo(http, token=settings.SHIPSGO_API_TOKEN)
        try:
            shipment = await cliente.leer(id_embarque, aereo=aereo)
            geojson = await cliente.leer_geojson(id_embarque, aereo=aereo)
        except ErrorShipsGo as exc:
            print(f"  FALLO: {exc.motivo} — {exc.detalle}")
            return

    lectura = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson)
    print(f"  aplicado      : {lectura.aplicada}")
    print(f"  motivo        : {lectura.motivo or '—'}")
    if lectura.lectura is not None:
        print(f"  transportista : {lectura.lectura.naviera or '—'}")
        print(f"  puerto destino: {lectura.lectura.puerto_destino or '—'}")
        print(f"  etapa fuente  : {lectura.lectura.etapa or '—'}")
        print(f"  hitos         : {len(lectura.lectura.hitos)}")
    await sesion.flush()


async def principal(args: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as sesion:
        if args.resumen:
            await _resumen(sesion)
            return 0

        pedido = await _buscar_pedido(sesion, args.pedido)
        if pedido is None:
            print(f"No existe el pedido {args.pedido!r}.", file=sys.stderr)
            print("Use --resumen para ver los disponibles.", file=sys.stderr)
            return 1

        if ":" not in args.referencia:
            print("Formato: TIPO:NUMERO (por ejemplo CONTENEDOR:MRSU8132490)", file=sys.stderr)
            return 1
        tipo, numero = args.referencia.split(":", 1)

        print(f"\n{SEP}\nPEDIDO {pedido.tracking_interno}\n{SEP}")
        _mostrar("ANTES", pedido)

        print(f"\n{SEP}\n1. ASOCIACIÓN (local, no consume crédito)\n{SEP}")
        resultado = await asociacion.asociar_referencia(
            sesion, pedido, tipo.strip().upper(), numero.strip(), motivo=args.motivo
        )
        print(f"  válida     : {resultado.valida}")
        print(f"  rastreable : {resultado.rastreable}")
        print(f"  motivo     : {resultado.motivo or '—'}")
        if not resultado.valida:
            print("\n  No se tocó el pedido. Nada que revertir.")
            return 1
        await sesion.flush()

        if args.leer:
            await _leer_y_procesar(sesion, pedido, args.leer, args.aereo)

        print(f"\n{SEP}\n3. RECÁLCULO — RN-01 y semáforo\n{SEP}")
        recalculado = await recalculo.recalcular(sesion, pedido)
        print(f"  cambió        : {recalculado.cambio}")
        print(f"  origen fecha  : {recalculado.proyeccion.origen or '—'}")
        print(f"  motivo        : {recalculado.proyeccion.motivo or '—'}")

        print(f"\n{SEP}\n4. ARRIBO — RN-05\n{SEP}")
        llegada = await arribo.evaluar(sesion, pedido)
        print(f"  arribado : {llegada.arribado}")
        print(f"  origen   : {llegada.origen or '—'}")
        print(f"  motivo   : {llegada.motivo or '—'}")
        if llegada.distancia_m is not None:
            print(f"  distancia: {llegada.distancia_m:.0f} m del destino")

        _mostrar("DESPUÉS", pedido)

        if args.ensayo:
            await sesion.rollback()
            print("\n  --ensayo: se revirtió todo. La base quedó como estaba.")
        else:
            await sesion.commit()
            print("\n  Cambios guardados.")
    await dispose_engine()
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(
        description=(
            "Asocia una referencia a un pedido y corre el ciclo completo. "
            "No da de alta embarques: eso cuesta y vive en verificar_shipsgo.py."
        ),
    )
    analizador.add_argument("pedido", nargs="?", help="Tracking interno, o OC-POSICION.")
    analizador.add_argument("referencia", nargs="?", help="TIPO:NUMERO, p. ej. BL:COSU6508789000.")
    analizador.add_argument(
        "--leer",
        type=int,
        metavar="ID",
        help="Lee de ShipsGo un embarque YA registrado y corre el colector. Gratis.",
    )
    analizador.add_argument(
        "--aereo", action="store_true", help="Usa los endpoints aéreos en vez de los marítimos."
    )
    analizador.add_argument(
        "--resumen", action="store_true", help="Muestra qué pedidos hay, sin escribir."
    )
    analizador.add_argument(
        "--ensayo",
        action="store_true",
        help="Corre todo y revierte al final: sirve para ver el efecto sin dejarlo.",
    )
    analizador.add_argument(
        "--motivo",
        default="Asociación manual de verificación (RF-03)",
        help="Queda en la auditoría de la intervención (RF-14).",
    )
    argumentos = analizador.parse_args()

    if not argumentos.resumen and not (argumentos.pedido and argumentos.referencia):
        analizador.error("hacen falta PEDIDO y REFERENCIA, o --resumen")

    _forzar_salida_utf8()
    logging.basicConfig(level=logging.WARNING, format="  [%(levelname)s] %(message)s")
    # En desarrollo el engine va con `echo=True` y cada SELECT tapa el informe.
    # Lo que este script tiene que dejar ver es el ciclo, no el SQL.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    return asyncio.run(principal(argumentos))


if __name__ == "__main__":
    raise SystemExit(main())
