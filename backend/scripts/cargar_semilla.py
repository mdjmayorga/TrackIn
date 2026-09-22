"""Carga en la base los pedidos que entrega la fuente configurada.

    python scripts/cargar_semilla.py            # carga
    python scripts/cargar_semilla.py --resumen  # solo muestra qué hay, sin escribir
    python scripts/cargar_semilla.py --limpiar  # borra los pedidos antes de cargar

`TASK-03`. La fuente sale de `INGESTA_ADAPTADOR` del `.env`, así que este mismo
script carga el Z-tracking real desde que `US-31` registró su adaptador
(`INGESTA_ADAPTADOR=ztracking` más `ZTRACKING_RUTA`): no menciona la semilla en
ninguna parte salvo en su nombre, que conviene cambiar cuando toque.

**Es idempotente.** La clave natural es `(oc_numero, posicion_oc)` y una línea
ya presente se **actualiza** con lo que traiga el archivo, sin tocar el estado
calculado ni lo confirmado a mano. Correrlo dos veces seguidas no duplica nada
y la segunda vez no cambia nada.

Lo que estaba en la base y no vino en el archivo se marca para revisión y **no
se borra** (`US-31`). `--sin-ausentes` desactiva esa marca para cargas
parciales, donde el archivo no es el universo completo de pedidos vivos.

`--limpiar` existe para dejar la base en un estado conocido antes de una
demostración. Borra `pedidos_transito` y `elementos_rastreados`; **no toca los
maestros** —destinos, países, parámetros— que vienen de las migraciones, ni
`historial_tracking`, que es *append-only* por disparador (RNF-13) y cuyo borrado
tiene que ser un acto deliberado, no un efecto secundario de recargar.
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

from sqlalchemy import delete, func, select  # noqa: E402

from app.db.session import AsyncSessionLocal, dispose_engine, engine  # noqa: E402
from app.models.elemento_rastreado import ElementoRastreado  # noqa: E402
from app.models.maestro_destino import MaestroDestino  # noqa: E402
from app.models.pedido_transito import PedidoTransito  # noqa: E402
from app.services.ingesta import obtener_fuente  # noqa: E402
from app.services.ingesta.carga import cargar  # noqa: E402

SEP = "=" * 72


def _forzar_salida_utf8() -> None:
    """Escribe en UTF-8 pase lo que pase con la consola.

    La consola de Windows usa cp1252 salvo que alguien exporte
    `PYTHONIOENCODING`, y sin eso «Moín» y «Vía» salen rotos. Este informe se
    proyecta en reuniones: no puede depender de que quien lo corra se acuerde
    de una variable de entorno.
    """
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")


def _silenciar_eco_sql() -> None:
    """Apaga el volcado de SQL mientras corre el script.

    `backend/.env` trae `DEBUG=true`, que pone `echo=True` en el engine: útil
    depurando, ilegible acá. La salida de este script es un informe que alguien
    lee —a veces proyectado—, y el volcado del SQL la vuelve inservible.

    Se apaga en el **motor** y no bajando el nivel del logger, que no funciona:
    con `echo=True` SQLAlchemy emite a través de un `InstanceLogger` que
    consulta el `echo` del engine y **pasa por encima** del nivel configurado.
    Tampoco se toca el `.env`, que es una preferencia de desarrollo.
    """
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _resumir_rechazos(rechazadas, tope: int = 15) -> list[str]:
    """Agrupa por motivo y lista un puñado de ejemplos de cada uno.

    Contra el archivo real los rechazos se cuentan por centenares —la mayoría
    de las líneas no traen vía de transporte—, y volcarlos uno por uno tapa el
    resto del informe. El motivo con su cuenta es lo accionable; los ejemplos
    solo sirven para ir a buscar la línea.
    """
    por_motivo: dict[str, list[str]] = {}
    for linea in rechazadas:
        por_motivo.setdefault(linea.motivo, []).append(str(linea))

    salida: list[str] = []
    for motivo, lineas in sorted(por_motivo.items(), key=lambda par: -len(par[1])):
        salida.append(f"{motivo}: {len(lineas)} líneas")
        salida.extend(f"    {linea}" for linea in lineas[:tope])
        if len(lineas) > tope:
            salida.append(f"    … y {len(lineas) - tope} más")
    return salida


async def _mostrar_estado(sesion) -> None:
    """Qué hay hoy en la base, por vía y por etapa."""
    total = await sesion.scalar(select(func.count()).select_from(PedidoTransito))
    print(f"\nPedidos en la base: {total}")
    if not total:
        return

    filas = (
        await sesion.execute(
            select(
                PedidoTransito.via_transporte,
                PedidoTransito.etapa_viaje,
                func.count().label("n"),
            )
            .group_by(PedidoTransito.via_transporte, PedidoTransito.etapa_viaje)
            .order_by(PedidoTransito.via_transporte, PedidoTransito.etapa_viaje)
        )
    ).all()
    print(f"\n  {'Vía':<12} {'Etapa':<16} {'Pedidos':>8}")
    print(f"  {'-' * 12} {'-' * 16} {'-' * 8}")
    for via, etapa, n in filas:
        print(f"  {via:<12} {etapa:<16} {n:>8}")


async def _mostrar_pedidos(sesion) -> None:
    """El detalle que se enseña en una demostración."""
    filas = (
        await sesion.execute(
            select(PedidoTransito, MaestroDestino)
            .join(MaestroDestino, PedidoTransito.id_destino == MaestroDestino.id)
            .order_by(PedidoTransito.oc_numero, PedidoTransito.posicion_oc)
        )
    ).all()
    if not filas:
        return

    print(f"\n  {'Tracking':<20} {'Vía':<10} {'Destino':<26} {'Inco':<6} {'Etapa':<14} Referencia")
    print(f"  {'-' * 20} {'-' * 10} {'-' * 26} {'-' * 6} {'-' * 14} {'-' * 22}")
    for pedido, destino in filas:
        elemento = None
        if pedido.id_elemento_rastreado is not None:
            elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
        referencia = (
            f"{elemento.tipo_tracking_externo}:{elemento.tracking_externo}" if elemento else "—"
        )
        print(
            f"  {pedido.tracking_interno:<20} {pedido.via_transporte:<10} "
            f"{destino.nombre:<26} {pedido.incoterm or '—':<6} "
            f"{pedido.etapa_viaje:<14} {referencia}"
        )


async def principal(*, limpiar: bool, solo_resumen: bool, senalar_ausentes: bool) -> int:
    """Todo el trabajo, y el cierre del pool, dentro del **mismo** event loop.

    Una conexión de asyncpg queda atada al loop donde se abrió. Cerrar el pool
    desde un `asyncio.run` distinto revienta con
    `'NoneType' object has no attribute 'send'`, que es exactamente la trampa
    que `tests/conftest.py` ya documenta para las fixtures.
    """
    try:
        return await _ejecutar(
            limpiar=limpiar, solo_resumen=solo_resumen, senalar_ausentes=senalar_ausentes
        )
    finally:
        await dispose_engine()


async def _ejecutar(*, limpiar: bool, solo_resumen: bool, senalar_ausentes: bool) -> int:
    fuente = obtener_fuente()
    if fuente is None:
        print(
            "No hay fuente de ingesta configurada.\n"
            "Definí INGESTA_ADAPTADOR en backend/.env (por ejemplo, 'semilla').",
            file=sys.stderr,
        )
        return 1

    print(SEP)
    print(f"Fuente: {fuente.nombre} — {fuente.descripcion}")
    print(SEP)

    async with AsyncSessionLocal() as sesion:
        await sesion.begin()

        if solo_resumen:
            await _mostrar_estado(sesion)
            await _mostrar_pedidos(sesion)
            await sesion.rollback()
            return 0

        if limpiar:
            # El orden importa: el pedido apunta al elemento rastreado.
            borrados = await sesion.execute(delete(PedidoTransito))
            await sesion.execute(delete(ElementoRastreado))
            print(f"\n--limpiar: {borrados.rowcount} pedidos eliminados.")

        resultado = await cargar(sesion, fuente, señalar_ausentes=senalar_ausentes)
        await sesion.commit()

        # Los cuatro números del tercer criterio de US-31, más lo que el propio
        # archivo no dejó ni llegar a línea.
        print(
            f"\n  Recibidas    : {resultado.leidas}"
            f"\n  Insertadas   : {resultado.cargados}"
            f"\n  Actualizadas : {resultado.actualizados}"
            f"\n  Sin cambios  : {resultado.sin_cambios}"
            f"\n  Rechazadas   : {len(resultado.rechazadas)}"
        )
        if resultado.reaparecidos:
            print(f"  Reaparecidas : {resultado.reaparecidos} (estaban marcadas ausentes)")
        if resultado.cerrados_omitidos:
            print(
                f"  Cerradas     : {resultado.cerrados_omitidos} "
                "(volvieron al archivo; se dejan intactas, revisar a mano)"
            )

        if resultado.cargados:
            print(
                f"\n  Con rastreo automático posible hoy : {resultado.rastreables}"
                f"\n  Con referencia, sin API que la siga: {resultado.sin_rastreo_hoy}"
                f"\n  Sin referencia (SIN_TRACKING)      : {resultado.sin_tracking}"
            )

        # Filas que la fuente no pudo ni convertir en línea. No todas las
        # fuentes las exponen: la semilla no tiene archivo que leer.
        ilegibles = getattr(fuente, "ilegibles", [])
        if ilegibles:
            print(f"\nFilas ilegibles del archivo ({len(ilegibles)}) — no llegaron a línea:")
            for fila in ilegibles:
                print(f"  · {fila}")

        if resultado.rechazadas:
            # Se listan siempre: una línea que no entró y nadie ve es peor que
            # una carga que falla (RN-17).
            print("\nLíneas rechazadas — RN-17: la carga sigue, pero quedan a la vista:")
            for linea in _resumir_rechazos(resultado.rechazadas):
                print(f"  · {linea}")

        if resultado.ausentes:
            print(
                f"\nDejaron de figurar en el archivo ({len(resultado.ausentes)}) — "
                "marcadas para revisión manual, NO borradas:"
            )
            for oc, posicion in resultado.ausentes[:20]:
                print(f"  · {oc}-{posicion}")
            if len(resultado.ausentes) > 20:
                print(f"  … y {len(resultado.ausentes) - 20} más")

        await _mostrar_estado(sesion)
        await _mostrar_pedidos(sesion)

    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(
        description="Carga los pedidos de la fuente configurada en la base de TrackIn.",
    )
    analizador.add_argument(
        "--limpiar",
        action="store_true",
        help="Borra pedidos y elementos rastreados antes de cargar. No toca los maestros.",
    )
    analizador.add_argument(
        "--resumen",
        action="store_true",
        help="Solo muestra lo que hay en la base, sin escribir nada.",
    )
    analizador.add_argument(
        "--sin-ausentes",
        action="store_true",
        help=(
            "No marca como ausentes los pedidos que no vengan en el archivo. "
            "Para cargas parciales, donde el archivo no es el universo completo."
        ),
    )
    argumentos = analizador.parse_args()
    _forzar_salida_utf8()
    _silenciar_eco_sql()

    return asyncio.run(
        principal(
            limpiar=argumentos.limpiar,
            solo_resumen=argumentos.resumen,
            senalar_ausentes=not argumentos.sin_ausentes,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
