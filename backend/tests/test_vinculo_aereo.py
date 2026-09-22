"""Pruebas de `app.services.rastreo.vinculo_aereo` — `US-06` / RF-07.

Contra la base, porque lo que hay que verificar es el **índice parcial** que
impide dos tramos abiertos a la vez: probarlo con un doble solo confirmaría que
se asigna una fecha.

El caso que da sentido a la historia lo midió TG-11: la aeronave `0ac9e1` voló
cinco vuelos con cinco callsigns en 48 horas. Guardar el `icao24` como atributo
fijo del pedido haría seguir un avión que ya lleva otra carga a otro destino.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, func, select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services.rastreo import vinculo_aereo
from app.services.rastreo.opensky import parsear_estados

pytestmark = pytest.mark.integration

AHORA = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
HORA_SERVIDOR = 1787066777


def _vector(icao24: str, callsign: str | None) -> list[Any]:
    vector: list[Any] = [None] * 17
    vector[0] = icao24
    vector[1] = f"{callsign}  " if callsign else None
    vector[4] = HORA_SERVIDOR - 1
    vector[5] = -85.333
    vector[6] = 10.9489
    return vector


def _posiciones(*pares: tuple[str, str | None]):
    return parsear_estados({"time": HORA_SERVIDOR, "states": [_vector(i, c) for i, c in pares]})


async def _pedido(sesion, oc: str = "4577000001") -> PedidoTransito:
    destino = await sesion.scalar(
        select(MaestroDestino).where(MaestroDestino.via_transporte == "AEREO")
    )
    assert destino is not None
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-VIN-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-VIN-1", nombre="Proveedor")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-VIN-1"))
    if material is None:
        material = Material(codigo="M-VIN-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()

    pedido = PedidoTransito(
        oc_numero=oc,
        posicion_oc=10,
        tracking_interno=f"TRK-{oc}-010",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte="AEREO",
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        fecha_entrega_pedido=dt.date(2026, 10, 10),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        estado_calculado="SIN_TRACKING",
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido


@pytest.fixture
async def limpio(sesion):
    await sesion.execute(delete(PedidoElementoRastreado))
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    await sesion.flush()
    return sesion


# --- Abrir el vínculo ------------------------------------------------------


async def test_resuelve_el_icao24_desde_el_callsign(sesion, limpio) -> None:
    """La cadena que hay que cerrar: vuelo → callsign → `icao24` → posición."""
    pedido = await _pedido(sesion)

    resultado = await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await sesion.flush()

    assert resultado.resuelto is True
    assert resultado.icao24 == "0ac9e1"
    assert resultado.tramo == 1
    assert resultado.abierto is True


async def test_el_vinculo_vive_en_la_asociativa_y_no_como_atributo_fijo(sesion, limpio) -> None:
    """El punto entero de `US-06`.

    El FK del pedido apunta a la aeronave **vigente**; el vínculo con su
    vigencia vive en `pedido_elemento_rastreado`, con `fecha_desde`.
    """
    pedido = await _pedido(sesion)

    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await sesion.flush()

    tramo = await vinculo_aereo.tramo_vigente(sesion, pedido)
    assert tramo is not None
    assert tramo.fecha_desde == AHORA
    assert tramo.fecha_hasta is None
    assert pedido.id_elemento_rastreado == tramo.id_elemento_rastreado


async def test_al_vincular_el_pedido_sale_de_sin_tracking(sesion, limpio) -> None:
    """RN-02 lo exige: el `CHECK` prohíbe tener elemento y seguir sin tracking."""
    pedido = await _pedido(sesion)

    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await sesion.flush()  # si el CHECK se violara, reventaría aquí

    assert pedido.etapa_viaje == "EN_ORIGEN"


async def test_la_aeronave_se_reutiliza_entre_pedidos(sesion, limpio) -> None:
    """Varias líneas pueden viajar en el mismo vuelo: duplicar el elemento
    duplicaría las consultas."""
    uno = await _pedido(sesion, "4577000001")
    otro = await _pedido(sesion, "4577000002")
    posiciones = _posiciones(("0ac9e1", "AVA072"))

    await vinculo_aereo.resolver(sesion, uno, "AVA072", posiciones, instante=AHORA)
    await vinculo_aereo.resolver(sesion, otro, "AVA072", posiciones, instante=AHORA)
    await sesion.flush()

    total = await sesion.scalar(select(func.count()).select_from(ElementoRastreado))
    assert total == 1
    assert uno.id_elemento_rastreado == otro.id_elemento_rastreado


async def test_una_aeronave_no_lleva_imo(sesion, limpio) -> None:
    """El IMO es de la OMI y solo aplica a naves."""
    pedido = await _pedido(sesion)

    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await sesion.flush()

    aeronave = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    assert aeronave is not None
    assert aeronave.imo is None
    assert aeronave.nombre == "AVA072"


# --- El callsign llega tarde -----------------------------------------------


async def test_sin_callsign_no_hay_nada_que_resolver(sesion, limpio) -> None:
    pedido = await _pedido(sesion)

    resultado = await vinculo_aereo.resolver(sesion, pedido, None, _posiciones(), instante=AHORA)

    assert resultado.resuelto is False
    assert resultado.motivo == vinculo_aereo.SIN_CALLSIGN


async def test_si_el_vuelo_no_aparece_no_se_inventa_nada(sesion, limpio) -> None:
    """Puede que no haya despegado, que ya aterrizara o que el callsign aún no
    se reporte: la API no los distingue."""
    pedido = await _pedido(sesion)

    resultado = await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("aaaaaa", "CMP884")), instante=AHORA
    )

    assert resultado.resuelto is False
    assert resultado.motivo == vinculo_aereo.NO_ESTA_VOLANDO
    assert pedido.id_elemento_rastreado is None


async def test_resolver_funciona_al_segundo_intento(sesion, limpio) -> None:
    """`0ae105` reportó `callsign: null` y `TIAGO` **tres minutos después**."""
    pedido = await _pedido(sesion)

    primero = await vinculo_aereo.resolver(
        sesion, pedido, "TIAGO", _posiciones(("0ae105", None)), instante=AHORA
    )
    segundo = await vinculo_aereo.resolver(
        sesion,
        pedido,
        "TIAGO",
        _posiciones(("0ae105", "TIAGO")),
        instante=AHORA + dt.timedelta(minutes=3),
    )
    await sesion.flush()

    assert primero.resuelto is False
    assert segundo.resuelto is True
    assert segundo.icao24 == "0ae105"


# --- El cambio de aeronave: cinco vuelos, una aeronave ---------------------


async def test_el_mismo_avion_no_abre_un_tramo_nuevo(sesion, limpio) -> None:
    pedido = await _pedido(sesion)
    posiciones = _posiciones(("0ac9e1", "AVA072"))

    await vinculo_aereo.resolver(sesion, pedido, "AVA072", posiciones, instante=AHORA)
    segundo = await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", posiciones, instante=AHORA + dt.timedelta(hours=1)
    )
    await sesion.flush()

    assert segundo.abierto is False
    assert segundo.tramo == 1
    total = await sesion.scalar(select(func.count()).select_from(PedidoElementoRastreado))
    assert total == 1


async def test_cambiar_de_aeronave_cierra_el_tramo_y_abre_el_siguiente(sesion, limpio) -> None:
    """Y el orden importa: el índice parcial de la tabla **no admite** dos
    tramos abiertos para el mismo pedido."""
    pedido = await _pedido(sesion)
    luego = AHORA + dt.timedelta(hours=4)

    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    segundo = await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("abc123", "AVA072")), instante=luego
    )
    await sesion.flush()  # si hubiera dos abiertos, el índice reventaría aquí

    assert segundo.abierto is True
    assert segundo.cerrado_anterior is True
    assert segundo.tramo == 2
    assert segundo.icao24 == "abc123"


async def test_el_tramo_anterior_conserva_su_vigencia(sesion, limpio) -> None:
    """RF-26: el historial de la aeronave anterior queda asociado a su tramo."""
    pedido = await _pedido(sesion)
    luego = AHORA + dt.timedelta(hours=4)

    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("abc123", "AVA072")), instante=luego
    )
    await sesion.flush()

    tramos = list(
        await sesion.scalars(
            select(PedidoElementoRastreado)
            .where(PedidoElementoRastreado.id_pedido == pedido.id)
            .order_by(PedidoElementoRastreado.tramo)
        )
    )

    assert len(tramos) == 2
    assert tramos[0].fecha_hasta == luego
    assert tramos[1].fecha_hasta is None


async def test_el_fk_del_pedido_apunta_a_la_aeronave_vigente(sesion, limpio) -> None:
    pedido = await _pedido(sesion)

    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await vinculo_aereo.resolver(
        sesion,
        pedido,
        "AVA072",
        _posiciones(("abc123", "AVA072")),
        instante=AHORA + dt.timedelta(hours=4),
    )
    await sesion.flush()

    vigente = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
    assert vigente is not None
    assert vigente.tracking_externo == "abc123"


# --- Cerrar el tramo: el segundo criterio ----------------------------------


async def test_cerrar_el_tramo_termina_el_vinculo(sesion, limpio) -> None:
    """*«Cuando finaliza el tramo, el vínculo queda cerrado y no se sigue
    consultando»*."""
    pedido = await _pedido(sesion)
    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )

    cerrado = await vinculo_aereo.cerrar_tramo(
        sesion, pedido, instante=AHORA + dt.timedelta(hours=6)
    )
    await sesion.flush()

    assert cerrado is True
    assert await vinculo_aereo.tramo_vigente(sesion, pedido) is None


async def test_cerrar_sin_tramo_abierto_no_falla(sesion, limpio) -> None:
    pedido = await _pedido(sesion)
    assert await vinculo_aereo.cerrar_tramo(sesion, pedido, instante=AHORA) is False


async def test_tras_cerrar_se_puede_abrir_otro_tramo(sesion, limpio) -> None:
    """Un envío puede tener varios tramos consecutivos sin solaparse."""
    pedido = await _pedido(sesion)
    await vinculo_aereo.resolver(
        sesion, pedido, "AVA072", _posiciones(("0ac9e1", "AVA072")), instante=AHORA
    )
    await vinculo_aereo.cerrar_tramo(sesion, pedido, instante=AHORA + dt.timedelta(hours=2))

    resultado = await vinculo_aereo.resolver(
        sesion,
        pedido,
        "AVA068",
        _posiciones(("0ac9e1", "AVA068")),
        instante=AHORA + dt.timedelta(hours=5),
    )
    await sesion.flush()

    assert resultado.tramo == 2
    assert resultado.abierto is True
