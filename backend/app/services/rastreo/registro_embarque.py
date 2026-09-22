"""Alta de un embarque en ShipsGo, auditada — `US-45` / RF-14.

La pieza que falta entre el cliente y la base: el cliente sabe **hacer** el alta
y `asociacion` sabe vincular la referencia, pero nadie registraba que se gastó
un crédito y por orden de quién.

Por qué el alta se audita
--------------------------

Porque cuesta dinero. RF-14 exige auditar toda intervención manual, y el
catálogo `TIPOS_INTERVENCION` ya traía `ASOCIACION_TRACKING` desde el modelo:
es el tipo que corresponde, y la fase 2 de `TASK-28` lo anotó explícitamente al
descubrir que las fuentes comerciales son *create-then-poll*.

Un alta que nadie puede rastrear después es un cargo de 2 USD sin dueño. Con
374 créditos anuales estimados, eso son ~750 USD al año que hay que poder
explicar línea por línea.

Las dos guardas antes de gastar
--------------------------------

1. **La referencia se valida en local.** ShipsGo **acepta y cobra cualquier
   cosa**: un `POST` con `XXXX0000000` devolvió `200 SUCCESS` y creó el
   embarque. El dígito verificador de `services/referencia.py` es lo único que
   separa una errata de una factura, y aquí se exige antes de tocar la red.
2. **No se da de alta dos veces.** Si el elemento ya tiene un embarque
   registrado no se vuelve a pedir. Y si se pide igual, el `409` de ShipsGo
   devuelve el existente sin cobrar — la red de seguridad, no el plan.
3. **En la vía aérea, el prefijo se contrasta contra el catálogo** (`US-46`).
   `GET /air/airlines` es **gratis** y dice de antemano si la guía resuelve.
   Es una ventaja que la vía marítima no tiene: allí hay que pagar el alta
   para averiguar si la naviera está cubierta.

Un catálogo que no se pudo leer **no** bloquea el alta. Negar por «no pude
comprobarlo» dejaría de rastrear envíos válidos cuando falla una consulta
gratuita, que es el peor intercambio posible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.pedido_transito import PedidoTransito
from app.services import referencia as referencia_mod
from app.services.rastreo.shipsgo_aerolineas import CatalogoAerolineas
from app.services.rastreo.shipsgo_cliente import ClienteShipsGo, ErrorShipsGo

logger = logging.getLogger(__name__)

#: El tipo del catálogo que corresponde (`TIPOS_INTERVENCION`).
TIPO_INTERVENCION = "ASOCIACION_TRACKING"

#: Motivos por los que no se dio de alta.
RECHAZO_REFERENCIA_INVALIDA = "referencia_invalida"
RECHAZO_FUENTE_AJENA = "no_la_sigue_shipsgo"
#: `US-46`: el prefijo de la guía no corresponde a ninguna aerolínea del
#: catálogo. Darla de alta costaría un crédito y devolvería vacío.
RECHAZO_AEROLINEA_SIN_COBERTURA = "aerolinea_sin_cobertura"


@dataclass(frozen=True, slots=True)
class ResultadoRegistroEmbarque:
    """Qué pasó con el alta, y si costó."""

    registrado: bool
    motivo: str
    id_embarque: int | None = None
    consumio_credito: bool = False


async def registrar(
    sesion: AsyncSession,
    cliente: ClienteShipsGo,
    pedido: PedidoTransito,
    tipo: str,
    numero: str,
    id_usuario: int | None = None,
    catalogo: CatalogoAerolineas | None = None,
) -> ResultadoRegistroEmbarque:
    """Da de alta el embarque y deja constancia. **No hace commit.**

    Devuelve el resultado en vez de lanzar cuando la referencia no sirve: una
    referencia mala es una línea para revisión (RN-17), no una excepción que
    detenga un lote.
    """
    veredicto = referencia_mod.validar_referencia(tipo, numero)
    if not veredicto.valida:
        # Primera guarda: no se gasta un crédito en un número mal transcrito.
        logger.warning("ShipsGo: no se da de alta %s %r — %s", tipo, numero, veredicto.motivo)
        return ResultadoRegistroEmbarque(False, RECHAZO_REFERENCIA_INVALIDA)

    if referencia_mod.fuente_de(veredicto.tipo) != "shipsgo":
        # Un MMSI lo sigue AISStream gratis: pagar por él sería tirar dinero.
        return ResultadoRegistroEmbarque(False, RECHAZO_FUENTE_AJENA)

    assert veredicto.tipo is not None and veredicto.numero is not None

    if veredicto.tipo == "MAWB" and catalogo:
        # Tercera guarda, solo aérea: comprobación gratuita antes de pagar.
        aerolinea = catalogo.resolver(veredicto.numero)
        if aerolinea is None:
            logger.warning(
                "ShipsGo Air: el prefijo de %s no está en el catálogo (%d aerolíneas). "
                "No se da de alta: costaría un crédito y devolvería vacío.",
                veredicto.numero,
                len(catalogo.aerolineas),
            )
            return ResultadoRegistroEmbarque(False, RECHAZO_AEROLINEA_SIN_COBERTURA)
        logger.info(
            "ShipsGo Air: %s resuelve a %s (%s).",
            veredicto.numero,
            aerolinea.nombre,
            aerolinea.iata,
        )

    alta = await cliente.dar_de_alta(veredicto.tipo, veredicto.numero)

    # RF-14. Se registra **siempre**, haya costado o no: que un `409` saliera
    # gratis es justamente lo que alguien querrá poder comprobar después.
    if id_usuario is not None:
        sesion.add(
            AuditoriaIntervencion(
                id_pedido=pedido.id,
                id_usuario=id_usuario,
                tipo_intervencion=TIPO_INTERVENCION,
                campo_afectado="shipsgo_id_embarque",
                valor_anterior=None,
                valor_nuevo=str(alta.id_embarque),
                motivo=(
                    f"Alta en ShipsGo de {veredicto.tipo} {veredicto.numero}. "
                    + (
                        "Consumió un crédito (~2 USD)."
                        if alta.consumio_credito
                        else "Ya estaba registrado (409): sin costo."
                    )
                ),
            )
        )
    elif alta.consumio_credito:
        # Sin login todavía (`US-42`), pero el gasto no puede quedar mudo.
        logger.warning(
            "ShipsGo: alta de %s %s sin usuario identificado. Crédito consumido sin dueño.",
            veredicto.tipo,
            veredicto.numero,
        )

    return ResultadoRegistroEmbarque(
        registrado=True,
        motivo="registrado",
        id_embarque=alta.id_embarque,
        consumio_credito=alta.consumio_credito,
    )


__all__ = [
    "RECHAZO_AEROLINEA_SIN_COBERTURA",
    "RECHAZO_FUENTE_AJENA",
    "RECHAZO_REFERENCIA_INVALIDA",
    "TIPO_INTERVENCION",
    "ErrorShipsGo",
    "ResultadoRegistroEmbarque",
    "registrar",
]
