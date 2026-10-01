"""El ciclo periódico de rastreo — `US-50` / RF-08, RF-09, RF-12, RNF-14.

Hasta el 28/09/2026 cada pieza existía y estaba probada —el planificador, los
clientes de ShipsGo y TICA, los colectores, el arribo, el recálculo—, pero nadie
llamaba al planificador: el rastreo corría solo cuando alguien lanzaba un
script. Este módulo es el que los encadena, en el worker que `TASK-20` decidió
separar de la API (`docs/architecture.md` §1.4).

Qué hace un ciclo
------------------

1. **Planifica** (`planificador.planificar`): qué elementos toca consultar ya.
2. **Despacha** cada tarea a su fuente según el tipo de referencia:

   | Tipo | Fuente | Qué trae |
   |---|---|---|
   | `CONTENEDOR`, `BL`, `BOOKING`, `MAWB` | ShipsGo | Hitos, ETA, posición, arribo |
   | `HAWB` | TICA | Llegada real y guía madre (`US-49`) |
   | Los demás (`MMSI`, `VUELO`...) | — | Se omiten con su motivo: AIS es suscripción, no sondeo, y OpenSky es respaldo del mapa |

3. **Aplica** la lectura con su colector.
4. **Evalúa el arribo y recalcula** los pedidos activos del elemento, en ese
   orden: el arribo mueve la etapa y el estado calculado se deriva de ella.
5. **Confirma elemento por elemento.** Un fallo en uno no deshace ni bloquea a
   los demás (RNF-14).

Lo que el ciclo **no** hace: gastar dinero
-------------------------------------------

Consultar ShipsGo no cuesta; **dar de alta sí** (~2 USD). El ciclo solo lee
embarques que ya están registrados en la cuenta. Un elemento sin alta se omite
con el motivo `sin_alta_en_shipsgo` y queda a la vista: darlo de alta lo decide
una persona (`scripts/verificar_shipsgo.py --alta`), con la auditoría de RF-14.

ShipsGo no guarda qué id le dio a cada referencia de nuestro lado, así que al
principio del ciclo se lista la cuenta —gratis, de 25 en 25— y se arma el
índice referencia → id. Es una consulta por página y por ciclo, no por elemento.

La salud de cada fuente
------------------------

Cada fuente lleva su `EstadoFuente` (`US-03`). Si una falla, **se deja de
consultar en ese ciclo** —insistir contra un sitio caído o que nos bloqueó es lo
que no hay que hacer— y no se vuelve a intentar hasta que pase la espera que la
política indique. Un fallo permanente (`acceso_bloqueado` de TICA, credencial
inválida de ShipsGo) la apaga hasta reiniciar el worker. Las demás fuentes
siguen: la caída de TICA no detiene a ShipsGo.

Al final de cada ciclo el estado se **publica** en `salud_fuentes` (`US-51`):
`/health` lo sirve la API, que es otro proceso y no ve esta memoria. Publicarlo
es informativo, así que si falla se registra y el ciclo sigue: perder una foto
de la salud no justifica perder las lecturas ya confirmadas.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.services import arribo, planificador, recalculo, salud_fuentes
from app.services import estado as estado_mod
from app.services.rastreo import colector_shipsgo, colector_tica
from app.services.rastreo.indice_shipsgo import clave_referencia, indice_shipsgo
from app.services.rastreo.shipsgo_aerolineas import CatalogoAerolineas
from app.services.rastreo.shipsgo_cliente import ClienteShipsGo, ErrorShipsGo
from app.services.rastreo.tica_cliente import ClienteTICA, ErrorTICA
from app.services.referencia import fuente_de
from app.services.resiliencia import ClaseFallo, EstadoFuente

logger = logging.getLogger(__name__)

FUENTE_SHIPSGO: Final = "shipsgo"
FUENTE_TICA: Final = "tica"

#: Segundos entre ciclos. Es la resolución del planificador, no la frecuencia
#: de consulta: esa la decide cada elemento con `frecuencia_*_min`.
INTERVALO_S: Final = 60.0

#: Motivos de omisión propios del ciclo, además de los del planificador.
OMITIDO_SIN_FUENTE = "fuente_no_sondeada"
OMITIDO_SIN_CLIENTE = "fuente_sin_configurar"
OMITIDO_FUENTE_EN_ESPERA = "fuente_en_espera"
OMITIDO_FUENTE_DEGRADADA = "fuente_degradada"
OMITIDO_SIN_ALTA = "sin_alta_en_shipsgo"

FabricaSesion = Callable[[], Any]


@dataclass(slots=True)
class Fuentes:
    """Los clientes con que el ciclo habla con el mundo. `None` = no configurada.

    Se inyectan para poder probar el ciclo entero sin red.
    """

    shipsgo: ClienteShipsGo | None = None
    tica: ClienteTICA | None = None
    catalogo: CatalogoAerolineas | None = None


@dataclass(slots=True)
class EstadoWorker:
    """Lo que el worker arrastra de un ciclo al siguiente, en memoria.

    Nada de esto es dato de negocio: perderlo al reiniciar solo adelanta la
    próxima consulta, que es lo que uno querría de todos modos.
    """

    #: Elementos cuyo embarque se dio de alta y todavía no trae datos (~90 s).
    madurando: set[int] = field(default_factory=set)
    #: Hasta cuándo no se consulta cada fuente tras un fallo transitorio.
    en_espera_hasta: dict[str, dt.datetime] = field(default_factory=dict)
    #: Parámetros y lead times con que se recalculó todo por última vez.
    #: `None` al arrancar: el primer ciclo siempre barre (`US-17`).
    firma_calculo: recalculo.FirmaCalculo | None = None


@dataclass(slots=True)
class ResumenCiclo:
    """Qué pasó en un ciclo. Se loguea en una línea y lo usan las pruebas."""

    instante: dt.datetime
    consultados: dict[str, int] = field(default_factory=dict)
    aplicados: int = 0
    arribos: int = 0
    recalculados: int = 0
    #: Si hubo barrido global, por qué y qué movió.
    recalculo_global: str | None = None
    omitidos: dict[str, int] = field(default_factory=dict)
    errores: dict[str, str] = field(default_factory=dict)

    def omitir(self, motivo: str) -> None:
        self.omitidos[motivo] = self.omitidos.get(motivo, 0) + 1

    def contar(self, fuente: str) -> None:
        self.consultados[fuente] = self.consultados.get(fuente, 0) + 1

    def texto(self) -> str:
        partes = [
            f"consultados {self.consultados or 0}",
            f"aplicados {self.aplicados}",
            f"arribos {self.arribos}",
            f"recalculados {self.recalculados}",
        ]
        if self.recalculo_global:
            partes.append(f"recálculo global ({self.recalculo_global})")
        if self.omitidos:
            partes.append(f"omitidos {self.omitidos}")
        if self.errores:
            partes.append(f"errores {self.errores}")
        return ", ".join(partes)


# --- La salud de cada fuente ------------------------------------------------


def _salud(fuente: str) -> EstadoFuente:
    return salud_fuentes.registro.estado(fuente)


def _disponible(fuente: str, estado: EstadoWorker, ahora: dt.datetime) -> str | None:
    """`None` si se puede consultar la fuente; si no, el motivo de omitirla."""
    if not _salud(fuente).debe_reintentar:
        return OMITIDO_FUENTE_DEGRADADA
    hasta = estado.en_espera_hasta.get(fuente)
    if hasta is not None and ahora < hasta:
        return OMITIDO_FUENTE_EN_ESPERA
    return None


def _registrar_fallo(
    fuente: str, error: ErrorShipsGo | ErrorTICA, estado: EstadoWorker, ahora: dt.datetime
) -> None:
    salud = _salud(fuente)
    salud.registrar_fallo(instante=ahora, clase=error.clase, motivo=error.motivo)
    espera = salud.espera_hasta_el_proximo_intento()
    if espera:
        estado.en_espera_hasta[fuente] = ahora + dt.timedelta(seconds=espera)
    if error.clase is ClaseFallo.PERMANENTE:
        logger.error(
            "Worker: %s queda degradada (%s: %s). No se reintenta hasta reiniciar.",
            fuente,
            error.motivo,
            error.detalle,
        )
    else:
        logger.warning(
            "Worker: %s falló (%s); se reintenta en %.0f s.", fuente, error.motivo, espera or 0
        )


def _registrar_exito(
    fuente: str, estado: EstadoWorker, ahora: dt.datetime, con_datos: bool
) -> None:
    _salud(fuente).registrar_exito(instante=ahora, con_datos=con_datos)
    estado.en_espera_hasta.pop(fuente, None)


# --- Una tarea --------------------------------------------------------------


async def _pedidos_activos(
    sesion: AsyncSession, elemento: ElementoRastreado
) -> list[PedidoTransito]:
    filas = await sesion.scalars(
        select(PedidoTransito).where(
            PedidoTransito.id_elemento_rastreado == elemento.id,
            PedidoTransito.motivo_cierre.is_(None),
        )
    )
    return list(filas)


#: Hasta dónde mueve la etapa la lectura de la fuente. «En destino» lo decide
#: `arribo` —con el hito en el puerto de destino— y de ahí en adelante son
#: actos humanos (`US-14`, `US-18`).
ETAPAS_DE_LA_FUENTE: Final = frozenset({"EN_ORIGEN", "EN_TRANSITO"})


async def _arribo_y_recalculo(
    sesion: AsyncSession,
    elemento: ElementoRastreado,
    resumen: ResumenCiclo,
    ahora: dt.datetime,
    etapa_fuente: str | None = None,
) -> None:
    """El orden importa: el arribo mueve la etapa y el estado se deriva de ella.

    Antes del arribo se aplica la etapa que leyó la fuente, **solo hacia
    adelante** (`US-14`). Era el hallazgo del Sprint 4: el BL de COSCO
    navegaba (`SAILING`) y el pedido seguía «En origen», porque nadie copiaba
    la etapa de la lectura al pedido.

    Cada pedido va en su *savepoint* (`US-12`, RNF-14): si uno falla, se
    deshace solo ese. Sin esto, el error revertía el elemento entero —la
    lectura de la fuente y los demás pedidos del mismo contenedor—.
    """
    for pedido in await _pedidos_activos(sesion, elemento):
        nombre = pedido.tracking_interno
        etapa_antes = pedido.etapa_viaje
        try:
            async with sesion.begin_nested():
                if etapa_fuente in ETAPAS_DE_LA_FUENTE and estado_mod.avanza(
                    pedido.etapa_viaje, etapa_fuente
                ):
                    pedido.etapa_viaje = etapa_fuente
                llegada = await arribo.evaluar(sesion, pedido, ahora)
                await recalculo.recalcular(sesion, pedido, instante=ahora)
                await sesion.flush()
        except Exception:
            logger.exception("Worker: falló el recálculo de %s; se sigue.", nombre)
            resumen.errores[f"pedido:{nombre}"] = "error_de_recalculo"
            continue
        if llegada.arribado and etapa_antes != pedido.etapa_viaje:
            resumen.arribos += 1
        resumen.recalculados += 1


async def _consultar_shipsgo(
    sesion: AsyncSession,
    elemento: ElementoRastreado,
    cliente: ClienteShipsGo,
    id_embarque: int,
    aereo: bool,
    estado: EstadoWorker,
    ahora: dt.datetime,
) -> tuple[bool, str | None]:
    """Si la lectura se aplicó, y la etapa que dicen sus hitos."""
    shipment = await cliente.leer(id_embarque, aereo=aereo)
    geojson = await cliente.leer_geojson(id_embarque, aereo=aereo)
    lectura = await colector_shipsgo.procesar(sesion, elemento, shipment, geojson, instante=ahora)
    if lectura.motivo == colector_shipsgo.DESCARTE_SIN_MADURAR:
        estado.madurando.add(elemento.id)
    else:
        estado.madurando.discard(elemento.id)
    etapa = lectura.lectura.etapa if lectura.lectura is not None else None
    return lectura.aplicada, etapa


async def _consultar_tica(
    sesion: AsyncSession, elemento: ElementoRastreado, fuentes: Fuentes, ahora: dt.datetime
) -> bool:
    assert fuentes.tica is not None
    resultado = await colector_tica.procesar(
        sesion, elemento, fuentes.tica, catalogo=fuentes.catalogo, instante=ahora
    )
    return resultado.aplicada


# --- El recálculo global ----------------------------------------------------


async def _recalculo_global(
    fabrica_sesion: FabricaSesion, estado: EstadoWorker, resumen: ResumenCiclo, ahora: dt.datetime
) -> None:
    """Recalcula todo si cambió un insumo global (`US-17`, segundo criterio).

    El umbral de riesgo o un lead time editados en la base no llegan por
    ninguna lectura: sin esto, un pedido sin rastreo —la mayoría, hoy— no
    tendría nunca «el próximo recálculo» que los aplique. Al arrancar la firma
    es `None` y el primer ciclo barre, lo que además pone al día lo que haya
    cambiado con el worker apagado: una migración, un despliegue.

    Si falla se registra y el ciclo sigue: la firma no se actualiza, así que
    el próximo ciclo lo reintenta.
    """
    try:
        async with fabrica_sesion() as sesion:
            firma = await recalculo.firma_del_calculo(sesion)
            if firma == estado.firma_calculo:
                return
            motivo = (
                "arranque" if estado.firma_calculo is None else "cambió un parámetro o lead time"
            )
            barrido = await recalculo.recalcular_todos(sesion, instante=ahora)
            await sesion.commit()
    except Exception:
        logger.exception("Worker: falló el recálculo global; se reintenta el próximo ciclo.")
        resumen.errores["recalculo_global"] = "error_inesperado"
        return
    estado.firma_calculo = firma
    resumen.recalculo_global = f"{motivo}: {barrido.texto()}"
    for nombre in barrido.fallidos:
        resumen.errores[f"pedido:{nombre}"] = "error_de_recalculo"


# --- El ciclo ---------------------------------------------------------------


async def ejecutar_ciclo(
    fabrica_sesion: FabricaSesion,
    fuentes: Fuentes,
    estado: EstadoWorker | None = None,
    instante: dt.datetime | None = None,
) -> ResumenCiclo:
    """Un ciclo completo: planificar, consultar, aplicar, arribo y recálculo.

    Cada elemento va en su propia transacción. Lo único que detiene el ciclo
    entero es no poder planificarlo.
    """
    ahora = instante or dt.datetime.now(dt.UTC)
    estado = estado if estado is not None else EstadoWorker()
    resumen = ResumenCiclo(instante=ahora)

    async with fabrica_sesion() as sesion:
        salud_fuentes.registro.usar_politica(await salud_fuentes.politica_vigente(sesion))
        plan = await planificador.planificar(sesion, ahora, madurando=estado.madurando)
        await planificador.revisar_consumo(sesion, ahora)
    for omitido in plan.omitidos:
        resumen.omitir(omitido.motivo)

    # Antes de las lecturas: así lo que recalculen ya usa los valores nuevos.
    await _recalculo_global(fabrica_sesion, estado, resumen, ahora)

    tareas = [(tarea, fuente_de(tarea.tipo)) for tarea in plan.tareas]

    # El índice de ShipsGo se arma una vez por ciclo, y solo si hace falta.
    indice: dict[str, tuple[int, bool]] = {}
    hay_shipsgo = any(f == FUENTE_SHIPSGO for _, f in tareas)
    if (
        fuentes.shipsgo is not None
        and hay_shipsgo
        and _disponible(FUENTE_SHIPSGO, estado, ahora) is None
    ):
        try:
            indice = await indice_shipsgo(fuentes.shipsgo)
        except ErrorShipsGo as exc:
            _registrar_fallo(FUENTE_SHIPSGO, exc, estado, ahora)
            resumen.errores[FUENTE_SHIPSGO] = exc.motivo

    for tarea, fuente in tareas:
        if fuente not in (FUENTE_SHIPSGO, FUENTE_TICA):
            resumen.omitir(OMITIDO_SIN_FUENTE)
            continue
        cliente = fuentes.shipsgo if fuente == FUENTE_SHIPSGO else fuentes.tica
        if cliente is None:
            resumen.omitir(OMITIDO_SIN_CLIENTE)
            continue
        motivo = _disponible(fuente, estado, ahora)
        if motivo is not None:
            resumen.omitir(motivo)
            continue

        registrado: tuple[int, bool] | None = None
        if fuente == FUENTE_SHIPSGO:
            registrado = indice.get(clave_referencia(tarea.tracking) or "")
            if registrado is None:
                # Leer es gratis, dar de alta no: eso lo decide una persona.
                resumen.omitir(OMITIDO_SIN_ALTA)
                continue

        async with fabrica_sesion() as sesion:
            elemento = await sesion.get(ElementoRastreado, tarea.id_elemento)
            if elemento is None:
                continue
            try:
                etapa_fuente: str | None = None
                if registrado is not None:
                    assert fuentes.shipsgo is not None
                    aplicada, etapa_fuente = await _consultar_shipsgo(
                        sesion, elemento, fuentes.shipsgo, *registrado, estado, ahora
                    )
                else:
                    aplicada = await _consultar_tica(sesion, elemento, fuentes, ahora)
                resumen.contar(fuente)
                _registrar_exito(fuente, estado, ahora, con_datos=aplicada)
                if aplicada:
                    resumen.aplicados += 1
                    await _arribo_y_recalculo(sesion, elemento, resumen, ahora, etapa_fuente)
                await sesion.commit()
            except (ErrorShipsGo, ErrorTICA) as exc:
                await sesion.rollback()
                if exc.clase is ClaseFallo.REQUIERE_ALTA:
                    # Un 404 sobre **un** embarque (se archivó, o lo borraron de
                    # la cuenta) es un problema de ese elemento, no de la fuente:
                    # contarlo como fallo de ShipsGo la apagaría para todos.
                    resumen.omitir(OMITIDO_SIN_ALTA)
                    continue
                resumen.contar(fuente)
                resumen.errores[fuente] = exc.motivo
                _registrar_fallo(fuente, exc, estado, ahora)
            except Exception:
                # RNF-14: un elemento con un dato raro no puede tumbar el ciclo.
                await sesion.rollback()
                logger.exception("Worker: falló el elemento %s; se sigue.", tarea.tracking)
                resumen.errores[f"elemento:{tarea.tracking}"] = "error_inesperado"

    await _publicar_salud(fabrica_sesion, ahora)
    logger.info("Worker: ciclo %s — %s", ahora.isoformat(timespec="seconds"), resumen.texto())
    return resumen


async def _publicar_salud(fabrica_sesion: FabricaSesion, ahora: dt.datetime) -> None:
    """Vuelca la salud de las fuentes para que la vea `/health` (`US-51`)."""
    try:
        async with fabrica_sesion() as sesion:
            if await salud_fuentes.guardar(sesion, instante=ahora):
                await sesion.commit()
    except Exception:
        logger.exception("Worker: no se pudo publicar la salud de las fuentes; se sigue.")


async def ejecutar(
    fabrica_sesion: FabricaSesion,
    fuentes: Fuentes,
    *,
    intervalo_s: float = INTERVALO_S,
    ciclos: int | None = None,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[ResumenCiclo]:
    """Corre ciclos cada `intervalo_s` segundos. Sin `ciclos`, indefinidamente.

    Un ciclo que revienta entero —la base caída, típicamente— se registra y se
    espera al siguiente: el worker no muere por un corte de la base (RNF-14).
    """
    estado = EstadoWorker()
    resumenes: list[ResumenCiclo] = []
    hechos = 0
    while ciclos is None or hechos < ciclos:
        hechos += 1
        try:
            resumen = await ejecutar_ciclo(fabrica_sesion, fuentes, estado)
            if ciclos is not None:
                resumenes.append(resumen)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker: el ciclo falló entero; se reintenta en %.0f s.", intervalo_s)
        if ciclos is None or hechos < ciclos:
            await dormir(intervalo_s)
    return resumenes


__all__ = [
    "FUENTE_SHIPSGO",
    "FUENTE_TICA",
    "INTERVALO_S",
    "OMITIDO_FUENTE_DEGRADADA",
    "OMITIDO_FUENTE_EN_ESPERA",
    "OMITIDO_SIN_ALTA",
    "OMITIDO_SIN_CLIENTE",
    "OMITIDO_SIN_FUENTE",
    "EstadoWorker",
    "Fuentes",
    "ResumenCiclo",
    "ejecutar",
    "ejecutar_ciclo",
    "indice_shipsgo",
]
