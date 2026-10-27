"""Cargar un lote de pedidos enviado por la API de SAP — `US-65`.

Reunión de entrega del Informe 2 (27/10/2026): la API de SAP todavía no existe,
pero TrackIn tiene que quedar escuchando —apagado— para el día que exista.

**La carga es la misma del Excel.** Este módulo solo convierte el lote al
`PedidoCrudo` de siempre y lo pasa por `carga.cargar`: normalización (RN-17),
carga idempotente por OC y posición, rechazo línea por línea, recálculo
(`US-12`) e informe. Comparte el candado con el Excel, así que nunca corren dos
cargas a la vez.

**Lo que cambia respecto del Excel:**

- **No marca ausentes.** Un lote puede traer solo lo que cambió; dar por ausente
  todo lo demás vaciaría el panel. Las ausencias siguen saliendo de la carga
  completa del Excel, hasta que se acuerde otra cosa con quien construya la API.
- **No tiene usuario.** Queda en el historial con origen `API_SAP` y el id del
  lote en el lugar del nombre del archivo.
- **Los campos reservados se aceptan y se ignoran.** Están en el contrato para
  que la API los traiga desde el principio (`US-64`); usarlos es una decisión de
  negocio que todavía no se tomó.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.carga_ztracking import API_SAP, CargaZTracking
from app.models.parametro_sistema import ParametroSistema
from app.models.usuario import Usuario
from app.schemas.integracion_sap import LoteSap, PedidoSap
from app.services import parametros
from app.services.ingesta.carga import ResolutorDestino, cargar
from app.services.ingesta.carga_archivo import (
    FuenteLeida,
    avisos,
    registro_de_carga,
    tomar_candado,
)
from app.services.ingesta.comentario import referencia_en_comentario
from app.services.ingesta.dto import PedidoCrudo
from app.services.ingesta.informe import construir_informe

logger = logging.getLogger(__name__)

CLAVE_ESCUCHA: Final = "sap_escucha_habilitada"
FUENTE: Final = "api_sap"


async def escucha_habilitada(sesion: AsyncSession) -> bool:
    return bool(await parametros.obtener(sesion, CLAVE_ESCUCHA))


@dataclass(frozen=True, slots=True)
class EstadoEscucha:
    """Lo que muestra la pantalla «Integración con SAP» (`US-66`)."""

    habilitada: bool
    #: Quién la cambió por última vez y cuándo. Nulo si nadie la tocó desde la
    #: migración que la creó apagada.
    cambiada_por: Usuario | None
    cambiada_en: dt.datetime | None
    ultima_recepcion: CargaZTracking | None


async def estado_escucha(sesion: AsyncSession) -> EstadoEscucha:
    fila = await sesion.get(ParametroSistema, CLAVE_ESCUCHA)
    quien = (
        await sesion.get(Usuario, fila.id_usuario_modificacion)
        if fila is not None and fila.id_usuario_modificacion is not None
        else None
    )
    ultima = await sesion.scalar(
        select(CargaZTracking)
        .options(selectinload(CargaZTracking.usuario))
        .where(CargaZTracking.origen == API_SAP)
        .order_by(CargaZTracking.realizada_en.desc(), CargaZTracking.id.desc())
        .limit(1)
    )
    return EstadoEscucha(
        habilitada=await escucha_habilitada(sesion),
        cambiada_por=quien,
        cambiada_en=fila.actualizado_en if quien is not None and fila is not None else None,
        ultima_recepcion=ultima,
    )


async def cambiar_escucha(
    sesion: AsyncSession,
    *,
    habilitada: bool,
    id_usuario: int,
    instante: dt.datetime | None = None,
) -> None:
    """Enciende o apaga la escucha y deja quién y cuándo. **No hace commit.**

    El parámetro guarda quién lo cambió (`id_usuario_modificacion`) y cuándo
    (`actualizado_en`): es el registro que pide `US-66`. La auditoría de RF-14
    es de intervenciones sobre pedidos y no aplica aquí.
    """
    fila = await sesion.get(ParametroSistema, CLAVE_ESCUCHA)
    definicion = parametros.CATALOGO[CLAVE_ESCUCHA]
    if fila is None:
        fila = ParametroSistema(
            clave=CLAVE_ESCUCHA,
            tipo_dato=definicion.tipo_dato,
            descripcion=definicion.descripcion[:200],
            valor="false",
        )
        sesion.add(fila)
    fila.valor = "true" if habilitada else "false"
    fila.id_usuario_modificacion = id_usuario
    fila.actualizado_en = instante or dt.datetime.now(dt.UTC)
    await sesion.flush()
    logger.warning(
        "Escucha de la API de SAP %s por el usuario %s.",
        "ENCENDIDA" if habilitada else "apagada",
        id_usuario,
    )


def _texto(valor: str | None) -> str | None:
    limpio = valor.strip() if valor is not None else None
    return limpio or None


def a_pedido_crudo(pedido: PedidoSap) -> PedidoCrudo:
    """El pedido de SAP con la forma del que lee el Excel.

    Va **sin normalizar**, como del Excel: la normalización es de la carga
    (RN-17), no de cada fuente.
    """
    tipo: str | None = pedido.tipo_referencia
    numero = _texto(pedido.numero_referencia)
    desde_comentario = False
    if not (tipo and numero):
        # Como en el Excel: el comentario solo se lee si la referencia falta.
        hallada = referencia_en_comentario(_texto(pedido.comentario))
        if hallada is not None:
            tipo, numero = hallada
            desde_comentario = True

    return PedidoCrudo(
        oc_numero=pedido.oc_numero,
        posicion_oc=pedido.posicion_oc,
        proveedor_codigo=pedido.proveedor_codigo.strip(),
        proveedor_nombre=pedido.proveedor_nombre.strip(),
        material_codigo=pedido.material_codigo.strip(),
        material_descripcion=pedido.material_descripcion.strip(),
        cantidad=pedido.cantidad,
        unidad_medida=pedido.unidad_medida.strip(),
        fecha_entrega_pedido=pedido.fecha_entrega_pedido,
        destino_codigo=pedido.destino_codigo,
        via_transporte=pedido.via_transporte,
        pais_origen=_texto(pedido.pais_origen),
        incoterm=_texto(pedido.incoterm),
        temperatura=_texto(pedido.temperatura),
        tipo_proveedor=pedido.tipo_proveedor,
        fabricante=_texto(pedido.fabricante),
        eta_declarada=pedido.eta_declarada,
        arribo_declarado=pedido.arribo_declarado,
        tipo_referencia=tipo if numero else None,
        numero_referencia=numero if tipo else None,
        referencia_desde_comentario=desde_comentario,
        transportista=_texto(pedido.transportista),
        fecha_referencia=pedido.fecha_referencia,
        solicitud_pedido=_texto(pedido.solicitud_pedido),
    )


async def cargar_lote(
    sesion: AsyncSession,
    lote: LoteSap,
    *,
    tamano: int,
    resolutor_destino: ResolutorDestino | None = None,
    instante: dt.datetime | None = None,
) -> CargaZTracking:
    """Carga el lote y deja su registro. **No hace commit.**

    No revisa la escucha ni la clave: eso es de quien recibe el envío. Lanza
    `CargaEnCurso` si otra carga tiene el candado.
    """
    pedidos = [a_pedido_crudo(p) for p in lote.pedidos]
    await tomar_candado(sesion)

    ahora = instante or dt.datetime.now(dt.UTC)
    resultado = await cargar(
        sesion,
        FuenteLeida(FUENTE, f"API de SAP (lote {lote.lote.id})", pedidos),
        señalar_ausentes=False,
        resolutor_destino=resolutor_destino,
    )
    informe = construir_informe(FUENTE, resultado)
    fila = registro_de_carga(
        id_usuario=None,
        archivo=f"Lote {lote.lote.id}"[:255],
        tamano=tamano,
        instante=ahora,
        informe=informe,
        avisos=avisos(resultado),
        origen=API_SAP,
    )
    if fila.informe is not None:
        fila.informe["lote"] = lote.lote.model_dump(mode="json")
    sesion.add(fila)
    await sesion.flush()
    logger.info(
        "Carga de SAP, lote %r (%s, %d pedidos): %s",
        lote.lote.id,
        lote.lote.tipo,
        len(pedidos),
        informe.como_texto(ejemplos=0).splitlines()[1].strip(),
    )
    return fila


__all__ = [
    "CLAVE_ESCUCHA",
    "FUENTE",
    "EstadoEscucha",
    "a_pedido_crudo",
    "cambiar_escucha",
    "cargar_lote",
    "escucha_habilitada",
    "estado_escucha",
]
