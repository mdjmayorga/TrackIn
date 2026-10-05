"""Lectura de pedidos para la API — `US-16`.

Solo lee. El estado que devuelve es el **ya calculado** por el worker
(`architecture.md` §3.1): la API no consulta fuentes externas ni recalcula
dentro de la petición, que es lo que hace cumplible RNF-03 y RNF-12 —el
dashboard responde aunque ShipsGo esté caído—.

La única excepción aparente es el detalle, que **proyecta sin persistir** con
los insumos actuales para saber si la fecha guardada sigue al día. Es lectura:
usa la misma regla que el recálculo y no escribe nada.

Por qué los pedidos cerrados no salen por omisión
--------------------------------------------------

`wireframes.md` §1.11: la grilla por defecto muestra los activos
(`motivo_cierre IS NULL`) y los terminales aparecen **al filtrar por su
estado**. Como `CERRADO` y `CANCELADO` solo existen en filas cerradas —lo
garantiza el `CHECK terminal` de RN-13—, basta con que el filtro de estado
reemplace a la condición por omisión.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import ColumnElement, Select, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from app.models.elemento_rastreado import ElementoRastreado
from app.models.enums import ESTADOS_TERMINALES
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.schemas.pedidos import (
    SIN_PROYECCION,
    Arribos,
    Calculo,
    Cierre,
    PaisRef,
    PedidoDetalle,
    PedidoResumen,
    Posicion,
    Rastreo,
    VentanaLiberacion,
)
from app.services import parametros, proyeccion, recalculo

#: Columna de la grilla → expresión por la que ordena. La OC ordena también
#: por posición: la fila es la línea, y 10 tiene que ir antes que 20.
_COLUMNAS_ORDEN: dict[str, tuple[Any, ...]] = {
    "oc": (PedidoTransito.oc_numero, PedidoTransito.posicion_oc),
    "material": (Material.codigo,),
    "proveedor": (Proveedor.nombre,),
    "via": (PedidoTransito.via_transporte,),
    "destino": (MaestroDestino.nombre,),
    "eta": (PedidoTransito.eta_utilizada,),
    "fecha_proyectada": (PedidoTransito.fecha_proyectada_disponible,),
    "fecha_comprometida": (PedidoTransito.fecha_entrega_pedido,),
    "etapa": (PedidoTransito.etapa_viaje,),
    "cumplimiento": (PedidoTransito.estado_cumplimiento,),
    "estado": (PedidoTransito.estado_calculado,),
}

#: Lo primero que le importa a Compras: qué está por quedar disponible.
ORDEN_POR_OMISION = "fecha_proyectada"

#: Lo que acepta el parámetro `orden`: una columna, con `-` delante si baja.
PATRON_ORDEN = rf"^-?({'|'.join(_COLUMNAS_ORDEN)})$"


@dataclass(frozen=True, slots=True)
class Filtros:
    """Los filtros de RF-19 y los del Figma del 30/09. Vacío es «sin filtrar».

    El Figma corregido con los usuarios clave filtra por posición, por etapa y
    por cumplimiento por separado, y busca el material por texto. Los seis de
    RF-19 se conservan: proveedor y destino no están en el Figma, pero el
    requisito los pide.
    """

    oc: str | None = None
    proveedores: Sequence[int] = ()
    materiales: Sequence[int] = ()
    vias: Sequence[str] = ()
    estados: Sequence[str] = ()
    destinos: Sequence[int] = ()
    posiciones: Sequence[int] = ()
    etapas: Sequence[str] = ()
    cumplimientos: Sequence[str] = ()
    material_texto: str | None = None


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _condiciones(filtros: Filtros) -> list[ColumnElement[bool]]:
    condiciones: list[ColumnElement[bool]] = []
    if filtros.oc:
        # Por prefijo (decisión A5): el btree de `oc_numero` sirve tal cual.
        condiciones.append(
            PedidoTransito.oc_numero.like(f"{_escapar_like(filtros.oc.strip())}%", escape="\\")
        )
    if filtros.proveedores:
        condiciones.append(PedidoTransito.id_proveedor.in_(filtros.proveedores))
    if filtros.materiales:
        condiciones.append(PedidoTransito.id_material.in_(filtros.materiales))
    if filtros.vias:
        condiciones.append(PedidoTransito.via_transporte.in_(filtros.vias))
    if filtros.destinos:
        condiciones.append(PedidoTransito.id_destino.in_(filtros.destinos))
    if filtros.posiciones:
        condiciones.append(PedidoTransito.posicion_oc.in_(filtros.posiciones))
    if filtros.material_texto and filtros.material_texto.strip():
        patron = f"%{_escapar_like(filtros.material_texto.strip())}%"
        condiciones.append(
            or_(
                Material.codigo.ilike(patron, escape="\\"),
                Material.descripcion.ilike(patron, escape="\\"),
            )
        )
    if filtros.cumplimientos:
        valores = [c for c in filtros.cumplimientos if c != SIN_PROYECCION]
        opciones: list[ColumnElement[bool]] = []
        if valores:
            opciones.append(PedidoTransito.estado_cumplimiento.in_(valores))
        if SIN_PROYECCION in filtros.cumplimientos:
            opciones.append(PedidoTransito.estado_cumplimiento.is_(None))
        condiciones.append(or_(*opciones))

    terminales = [e for e in filtros.etapas if e in ESTADOS_TERMINALES]
    if filtros.etapas:
        activas = [e for e in filtros.etapas if e not in ESTADOS_TERMINALES]
        opciones = []
        if activas:
            # Un cerrado conserva su última etapa real, congelada: sin esta
            # condición, filtrar «En tránsito» traería pedidos ya cerrados.
            opciones.append(
                and_(
                    PedidoTransito.etapa_viaje.in_(activas),
                    PedidoTransito.motivo_cierre.is_(None),
                )
            )
        if terminales:
            opciones.append(PedidoTransito.estado_calculado.in_(terminales))
        condiciones.append(or_(*opciones))

    if filtros.estados:
        condiciones.append(PedidoTransito.estado_calculado.in_(filtros.estados))
    elif not terminales:
        condiciones.append(PedidoTransito.motivo_cierre.is_(None))
    return condiciones


def _consulta_base(filtros: Filtros) -> Select[tuple[PedidoTransito]]:
    return (
        select(PedidoTransito)
        .join(PedidoTransito.proveedor)
        .join(PedidoTransito.material)
        .join(PedidoTransito.destino)
        .outerjoin(PedidoTransito.elemento_rastreado)
        .where(*_condiciones(filtros))
    )


def _orden(orden: str) -> list[Any]:
    descendente = orden.startswith("-")
    columnas = _COLUMNAS_ORDEN[orden.lstrip("-")]
    expresiones = [
        (columna.desc() if descendente else columna.asc()).nulls_last() for columna in columnas
    ]
    # Desempate estable: sin él, dos páginas seguidas pueden repetir o saltarse
    # filas con la misma fecha, y la grilla tiene muchas.
    expresiones.append(PedidoTransito.id.asc())
    return expresiones


def _resumen(pedido: PedidoTransito) -> dict[str, Any]:
    elemento = pedido.elemento_rastreado
    return {
        "id": pedido.id,
        "oc_numero": pedido.oc_numero,
        "posicion_oc": pedido.posicion_oc,
        "tracking_interno": pedido.tracking_interno,
        "material": pedido.material,
        "proveedor": pedido.proveedor,
        "via_transporte": pedido.via_transporte,
        "destino": pedido.destino,
        "eta_utilizada": pedido.eta_utilizada,
        "fecha_proyectada_disponible": pedido.fecha_proyectada_disponible,
        "fecha_entrega_pedido": pedido.fecha_entrega_pedido,
        "etapa_viaje": pedido.etapa_viaje,
        "estado_cumplimiento": pedido.estado_cumplimiento,
        "estado_calculado": pedido.estado_calculado,
        "rastreable": elemento is not None,
        "ultima_actualizacion_fuente": elemento.ultima_actualizacion_api if elemento else None,
        "ausente_desde": pedido.ausente_desde,
        "fecha_recepcion_planta": pedido.fecha_recepcion_planta,
        "cantidad_recibida": pedido.cantidad_recibida,
    }


async def listar(
    sesion: AsyncSession,
    filtros: Filtros,
    *,
    orden: str = ORDEN_POR_OMISION,
    limite: int = 50,
    desplazamiento: int = 0,
) -> tuple[int, list[PedidoResumen]]:
    """Una página de pedidos y el total sin paginar. Una consulta para cada cosa."""
    consulta = _consulta_base(filtros)
    total = await sesion.scalar(select(func.count()).select_from(consulta.subquery()))

    pedidos = await sesion.scalars(
        consulta.options(
            contains_eager(PedidoTransito.proveedor),
            contains_eager(PedidoTransito.material),
            contains_eager(PedidoTransito.destino),
            contains_eager(PedidoTransito.elemento_rastreado),
        )
        .order_by(*_orden(orden))
        .limit(limite)
        .offset(desplazamiento)
    )
    return total or 0, [PedidoResumen.model_validate(_resumen(p)) for p in pedidos]


async def _posicion(sesion: AsyncSession, elemento: ElementoRastreado) -> Posicion | None:
    """Latitud y longitud de la última posición. `GEOGRAPHY` no tiene `ST_X`."""
    if elemento.posicion_actual is None:
        return None
    punto = cast(ElementoRastreado.posicion_actual, Geometry)
    fila = (
        await sesion.execute(
            select(func.ST_Y(punto), func.ST_X(punto)).where(ElementoRastreado.id == elemento.id)
        )
    ).one()
    return Posicion(latitud=fila[0], longitud=fila[1])


async def _rastreo(sesion: AsyncSession, elemento: ElementoRastreado | None) -> Rastreo | None:
    if elemento is None:
        return None
    return Rastreo(
        tipo=elemento.tipo_tracking_externo,
        referencia=elemento.tracking_externo,
        via_transporte=elemento.via_transporte,
        nombre=elemento.nombre,
        imo=elemento.imo,
        eta_fuente=elemento.eta_api,
        ata_fuente=elemento.ata_api,
        posicion=await _posicion(sesion, elemento),
        velocidad_nudos=elemento.velocidad_actual,
        ultima_consulta_exitosa=elemento.ultima_actualizacion_api,
        guia_madre=elemento.guia_madre,
        manifiesto_aduana=elemento.manifiesto_aduana,
        activo=elemento.activo,
    )


def _desglose_guardado(pedido: PedidoTransito, origen: str | None) -> str:
    """La operación que produjo la fecha **guardada**, con sus instantáneas.

    Es lo que la grilla muestra, así que es lo que hay que explicar, aunque los
    insumos de hoy ya den otra cosa: eso lo dice `desglose_actual`.
    """
    fecha = pedido.fecha_proyectada_disponible
    if fecha is None or pedido.eta_utilizada is None:
        return "Sin fecha proyectada en el último recálculo."
    base = pedido.eta_utilizada.date().isoformat()
    if origen is not None:
        base += f" ({origen})"
    partes = f"{base} + {pedido.lead_time_destino_dias} d de lead time"
    partes += proyeccion.sumando_ajuste(pedido.ajuste_manual_dias)
    return f"{partes} = {fecha.isoformat()}"


async def _calculo(sesion: AsyncSession, pedido: PedidoTransito) -> Calculo:
    """RF-05: la operación que produjo la fecha, y si todavía cuadra.

    Se reproyecta con la **instantánea** del lead time, no con el maestro: la
    pregunta es si la fecha guardada sigue saliendo de los insumos de hoy. Si
    el maestro cambió, eso ya se ve comparando los dos lead time, y mezclarlo
    aquí haría imposible distinguir una causa de la otra.

    El origen no tiene columna (`data-model.md` §1.3): se recupera de la
    reproyección, y solo cuando coincide con lo guardado. Si no coincide, el
    origen de hoy no es el que produjo la fecha, y darlo sería mentir.
    """
    if pedido.motivo_cierre is not None:
        # RN-13: un terminal no se recalcula, así que tampoco puede estar atrasado.
        origen = None
        desglose = (
            f"{_desglose_guardado(pedido, None)} "
            f"Pedido cerrado ({pedido.motivo_cierre}): RN-13 no lo recalcula."
        )
        desglose_actual = None
        al_dia = True
    else:
        proyectada = await recalculo.proyectar(
            sesion, pedido, lead_time_dias=pedido.lead_time_destino_dias
        )
        al_dia = proyectada.fecha == pedido.fecha_proyectada_disponible
        origen = proyectada.origen if al_dia else None
        if al_dia and pedido.fecha_proyectada_disponible is None:
            # Sin fecha y al día: el porqué de hoy es el porqué de entonces.
            desglose = proyectada.desglose
        else:
            desglose = _desglose_guardado(pedido, origen)
        desglose_actual = None if al_dia else proyectada.desglose

    proyectada_fecha = pedido.fecha_proyectada_disponible
    margen = (
        (pedido.fecha_entrega_pedido - proyectada_fecha).days
        if proyectada_fecha is not None
        else None
    )
    return Calculo(
        origen=origen,
        eta_utilizada=pedido.eta_utilizada,
        lead_time_dias=pedido.lead_time_destino_dias,
        lead_time_maestro_dias=pedido.destino.lead_time_dias,
        ajuste_manual_dias=pedido.ajuste_manual_dias,
        fecha_proyectada=proyectada_fecha,
        fecha_comprometida=pedido.fecha_entrega_pedido,
        # Compras, 29/09: la diferencia entre la llegada a CR y la fecha de
        # entrega **es** el tiempo que su plan da al proceso aduanal (`US-53`).
        ventana_aduanal_dias=(
            (pedido.fecha_entrega_pedido - pedido.eta_utilizada.date()).days
            if pedido.eta_utilizada is not None
            else None
        ),
        margen_dias=margen,
        umbral_riesgo_dias=await parametros.obtener_entero(sesion, recalculo.CLAVE_UMBRAL),
        desglose=desglose,
        al_dia=al_dia,
        desglose_actual=desglose_actual,
        fecha_ultimo_recalculo=pedido.fecha_ultimo_recalculo,
    )


async def detalle(sesion: AsyncSession, id_pedido: int) -> PedidoDetalle | None:
    """El pedido completo, o `None` si no existe."""
    pedido = await sesion.scalar(
        select(PedidoTransito)
        .where(PedidoTransito.id == id_pedido)
        .options(
            selectinload(PedidoTransito.proveedor),
            selectinload(PedidoTransito.material),
            selectinload(PedidoTransito.destino),
            selectinload(PedidoTransito.pais_origen),
            selectinload(PedidoTransito.elemento_rastreado),
        )
    )
    if pedido is None:
        return None

    elemento = pedido.elemento_rastreado
    pais = pedido.pais_origen
    return PedidoDetalle.model_validate(
        {
            **_resumen(pedido),
            "cantidad_pedida": pedido.cantidad_pedida,
            "unidad_medida": pedido.unidad_medida,
            "incoterm": pedido.incoterm,
            "temperatura": pedido.temperatura,
            "tipo_proveedor": pedido.tipo_proveedor,
            "fabricante": pedido.fabricante,
            "pais_origen": PaisRef(codigo=pais.codigo, nombre=pais.nombre) if pais else None,
            "rastreo": await _rastreo(sesion, elemento),
            "arribos": Arribos(
                confirmado=pedido.ata_confirmada,
                fuente=elemento.ata_api if elemento else None,
                inferido=pedido.ata_inferida,
            ),
            "calculo": await _calculo(sesion, pedido),
            "cierre": Cierre(
                fecha_recepcion_planta=pedido.fecha_recepcion_planta,
                cantidad_recibida=pedido.cantidad_recibida,
                liberacion_estimada=(
                    VentanaLiberacion(
                        desde=pedido.fecha_liberacion_estimada_desde,
                        hasta=pedido.fecha_liberacion_estimada_hasta,
                    )
                    if pedido.fecha_liberacion_estimada_desde is not None
                    and pedido.fecha_liberacion_estimada_hasta is not None
                    else None
                ),
                cantidad_liberada=pedido.cantidad_liberada,
                fecha_liberacion_calidad=pedido.fecha_liberacion_calidad,
                motivo_cierre=pedido.motivo_cierre,
            ),
            "fecha_ultima_carga": pedido.fecha_ultima_carga,
        }
    )


__all__ = ["ORDEN_POR_OMISION", "PATRON_ORDEN", "Filtros", "detalle", "listar"]
