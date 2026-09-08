"""Pruebas de `app.services.asociacion` — RF-03 / `US-01`.

Todas son de integración: el valor de este módulo está en cómo se comporta
contra la base —reutilizar el elemento, respetar el `CHECK` de RN-02, dejar
rastro de auditoría—, y eso no se puede verificar con dobles.

Cada prueba corre dentro de la transacción de la *fixture* `sesion`, que hace
*rollback* al terminar: los datos semilla de `0002` quedan intactos.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.services.asociacion import (
    ETAPA_AL_ASOCIAR,
    asociar_referencia,
    obtener_o_crear_elemento,
)

pytestmark = pytest.mark.integration

#: Contador de sufijos para que los códigos únicos no choquen entre pruebas.
_contador = iter(range(1, 10_000))


async def _crear_pedido(sesion, *, via: str = "MARITIMO") -> PedidoTransito:
    """Pedido mínimo válido, en `SIN_TRACKING` como sale de la ingesta."""
    n = next(_contador)
    destino = await sesion.scalar(
        select(MaestroDestino).where(MaestroDestino.via_transporte == via).limit(1)
    )
    assert destino is not None, f"faltan destinos {via} en el maestro (migración 0002)"

    proveedor = Proveedor(codigo=f"PRV{n:05d}", nombre=f"Proveedor {n}")
    material = Material(codigo=f"MAT{n:05d}", descripcion=f"Material {n}")
    sesion.add_all([proveedor, material])
    await sesion.flush()

    pedido = PedidoTransito(
        oc_numero=f"45{n:08d}",
        posicion_oc=10,
        tracking_interno=f"TRK-{n:06d}",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte=via,
        cantidad_pedida=Decimal("100.000"),
        unidad_medida="UN",
        fecha_entrega_pedido=dt.date(2026, 12, 1),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        estado_calculado="SIN_TRACKING",
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def _crear_usuario(sesion) -> Usuario:
    n = next(_contador)
    usuario = Usuario(
        usuario=f"prueba{n}",
        nombre_completo=f"Usuario de prueba {n}",
        # No es una contraseña: es un marcador con el formato de un hash, para
        # satisfacer el NOT NULL sin sugerir que hay una credencial real.
        hash_contrasena="$argon2id$sin-credencial-de-prueba",
        rol="LOGISTICA",
    )
    sesion.add(usuario)
    await sesion.flush()
    return usuario


# --- obtener_o_crear_elemento ---------------------------------------------


async def test_crea_el_elemento_si_no_existe(sesion) -> None:
    elemento = await obtener_o_crear_elemento(sesion, "CONTENEDOR", "MSCU1000001", "MARITIMO")
    assert elemento.id is not None
    assert elemento.activo is True


async def test_reutiliza_el_elemento_activo_con_la_misma_referencia(sesion) -> None:
    """Cinco líneas de una OC viajan en el mismo contenedor.

    Duplicar el elemento multiplicaría las consultas a una fuente que se cobra
    por envío rastreado, sin aportar nada.
    """
    primero = await obtener_o_crear_elemento(sesion, "CONTENEDOR", "MSCU1000002", "MARITIMO")
    segundo = await obtener_o_crear_elemento(sesion, "CONTENEDOR", "MSCU1000002", "MARITIMO")
    assert primero.id == segundo.id


async def test_no_reutiliza_un_elemento_inactivo(sesion) -> None:
    """La unicidad es *mientras esté activo* (§4.3 del modelo).

    Un MMSI se reasigna años después: el elemento viejo no debe revivir.
    """
    viejo = await obtener_o_crear_elemento(sesion, "MMSI", "111000001", "MARITIMO")
    viejo.activo = False
    await sesion.flush()

    nuevo = await obtener_o_crear_elemento(sesion, "MMSI", "111000001", "MARITIMO")
    assert nuevo.id != viejo.id
    assert nuevo.activo is True


async def test_distinto_tipo_es_distinto_elemento(sesion) -> None:
    contenedor = await obtener_o_crear_elemento(sesion, "BL", "X1000003", "MARITIMO")
    booking = await obtener_o_crear_elemento(sesion, "BOOKING", "X1000003", "MARITIMO")
    assert contenedor.id != booking.id


# --- asociar_referencia: camino feliz -------------------------------------


async def test_asociar_vincula_y_mueve_la_etapa(sesion) -> None:
    """El `CHECK` de RN-02 exige que la etapa deje de ser `SIN_TRACKING`."""
    pedido = await _crear_pedido(sesion)
    resultado = await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU2000001")

    assert resultado.valida
    assert pedido.id_elemento_rastreado is not None
    assert pedido.etapa_viaje == ETAPA_AL_ASOCIAR == "EN_ORIGEN"
    assert pedido.estado_calculado == "EN_ORIGEN"
    await sesion.flush()  # si el CHECK se violara, reventaría aquí


async def test_asociar_persiste_la_referencia_normalizada(sesion) -> None:
    pedido = await _crear_pedido(sesion)
    await asociar_referencia(sesion, pedido, " contenedor ", " mscu 2000002 ")
    await sesion.flush()

    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    assert elemento is not None
    assert elemento.tipo_tracking_externo == "CONTENEDOR"
    assert elemento.tracking_externo == "MSCU2000002"


async def test_dos_pedidos_del_mismo_contenedor_comparten_elemento(sesion) -> None:
    uno = await _crear_pedido(sesion)
    otro = await _crear_pedido(sesion)
    await asociar_referencia(sesion, uno, "CONTENEDOR", "MSCU2000003")
    await asociar_referencia(sesion, otro, "CONTENEDOR", "MSCU2000003")
    await sesion.flush()

    assert uno.id_elemento_rastreado == otro.id_elemento_rastreado


async def test_una_referencia_valida_pero_no_rastreable_se_asocia_igual(sesion) -> None:
    """Tercer criterio de `US-01`: se guarda aunque hoy nadie la siga.

    Un contenedor depende de Vizion, que está aprobada pero no contratada. El
    dato vale igual: mañana hay fuente y hoy le sirve a quien consulta a mano.
    """
    pedido = await _crear_pedido(sesion)
    resultado = await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU2000004")

    assert resultado.valida and not resultado.rastreable
    assert pedido.id_elemento_rastreado is not None  # se asoció igual


# --- asociar_referencia: rechazo ------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [
        ("CONTENEDOR", "NO-ES-UN-CONTENEDOR"),
        ("MAWB", "ABC-12345678"),  # HAWB del agente de carga
        ("TIPO_INVENTADO", "123"),
        (None, "MSCU2000005"),
        ("CONTENEDOR", None),
    ],
)
async def test_referencia_invalida_no_toca_el_pedido(sesion, tipo, numero) -> None:
    pedido = await _crear_pedido(sesion)
    resultado = await asociar_referencia(sesion, pedido, tipo, numero)

    assert not resultado.valida
    assert pedido.id_elemento_rastreado is None
    assert pedido.etapa_viaje == "SIN_TRACKING"  # intacto


async def test_referencia_invalida_no_crea_elementos_huerfanos(sesion) -> None:
    antes = await sesion.scalar(select(func.count()).select_from(ElementoRastreado))
    pedido = await _crear_pedido(sesion)
    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MAL")
    await sesion.flush()
    despues = await sesion.scalar(select(func.count()).select_from(ElementoRastreado))
    assert antes == despues


# --- Auditoría (RF-14) -----------------------------------------------------


async def test_con_usuario_deja_rastro_de_auditoria(sesion) -> None:
    usuario = await _crear_usuario(sesion)
    pedido = await _crear_pedido(sesion)
    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000001", id_usuario=usuario.id)
    await sesion.flush()

    registro = await sesion.scalar(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert registro is not None
    assert registro.tipo_intervencion == "ASOCIACION_TRACKING"
    assert registro.campo_afectado == "id_elemento_rastreado"
    assert registro.valor_nuevo == "CONTENEDOR:MSCU3000001"
    assert registro.valor_anterior is None  # no tenía elemento previo


async def test_sin_usuario_no_audita(sesion) -> None:
    """Hasta que exista login (`US-42`) la autoría puede no estar disponible.

    `id_usuario` es `NOT NULL` en la tabla: sin usuario no se puede auditar, y
    forzarlo rompería la carga automática, que no tiene detrás a una persona.
    """
    pedido = await _crear_pedido(sesion)
    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000002")
    await sesion.flush()

    registro = await sesion.scalar(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert registro is None


async def test_reasociar_registra_el_valor_anterior(sesion) -> None:
    """Un transbordo cambia el elemento: la auditoría tiene que decir desde cuál."""
    usuario = await _crear_usuario(sesion)
    pedido = await _crear_pedido(sesion)

    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000003")
    await sesion.flush()
    primero = pedido.id_elemento_rastreado

    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000004", id_usuario=usuario.id)
    await sesion.flush()

    assert pedido.id_elemento_rastreado != primero
    registro = await sesion.scalar(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert registro is not None
    assert registro.valor_anterior == str(primero)


# --- Idempotencia ----------------------------------------------------------


async def test_asociar_dos_veces_la_misma_referencia_es_idempotente(sesion) -> None:
    pedido = await _crear_pedido(sesion)
    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000005")
    await sesion.flush()
    primero = pedido.id_elemento_rastreado

    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000005")
    await sesion.flush()

    assert pedido.id_elemento_rastreado == primero


async def test_no_degrada_una_etapa_ya_avanzada(sesion) -> None:
    """Si el pedido ya zarpó, asociar no debe devolverlo a `EN_ORIGEN`."""
    pedido = await _crear_pedido(sesion)
    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000006")
    pedido.etapa_viaje = "EN_TRANSITO"
    pedido.estado_calculado = "EN_TRANSITO"
    await sesion.flush()

    await asociar_referencia(sesion, pedido, "CONTENEDOR", "MSCU3000007")
    assert pedido.etapa_viaje == "EN_TRANSITO"
