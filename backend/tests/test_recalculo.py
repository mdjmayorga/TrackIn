"""Pruebas de `app.services.recalculo` — `US-09` + `US-10` contra la base.

Las reglas puras se prueban en `test_proyeccion.py` y `test_estado.py`. Lo que
se verifica **aquí** es lo que solo la base puede decir:

- que lo escrito no viola los `CHECK` que implementan RN-02, RN-10 y RN-13;
- que el umbral sale de `parametros_sistema` de verdad, no de una constante;
- que el recálculo no pisa la etapa ni lo confirmado a mano.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services import proyeccion
from app.services.estado import A_TIEMPO, EN_RIESGO, RETRASADO, SIN_TRACKING
from app.services.recalculo import CLAVE_UMBRAL, recalcular, recalcular_todos

pytestmark = pytest.mark.integration

COMPROMETIDA = dt.date(2026, 10, 10)


async def _destino(sesion) -> MaestroDestino:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    assert destino is not None, "la migración 0002 siembra los cuatro destinos"
    return destino


async def _pedido(sesion, **kwargs) -> PedidoTransito:
    """Un pedido mínimo y válido, para variarle solo lo que cada prueba mira."""
    destino = await _destino(sesion)

    # Se reutilizan: varias pruebas crean dos pedidos y el código es único.
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-CALC-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-CALC-1", nombre="Proveedor de cálculo")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-CALC-1"))
    if material is None:
        material = Material(codigo="M-CALC-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()

    base = {
        "oc_numero": "4577777777",
        "posicion_oc": 10,
        "tracking_interno": "TRK-4577777777-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": "MARITIMO",
        "cantidad_pedida": Decimal("100.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": COMPROMETIDA,
        "lead_time_destino_dias": destino.lead_time_dias,
        "etapa_viaje": SIN_TRACKING,
        "estado_calculado": SIN_TRACKING,
    }
    base.update(kwargs)
    pedido = PedidoTransito(**base)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


@pytest.fixture
async def umbral_dos(sesion):
    """Fija el umbral en 2 días dentro de la transacción de la prueba."""
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == CLAVE_UMBRAL))
    sesion.add(
        ParametroSistema(
            clave=CLAVE_UMBRAL,
            valor="2",
            tipo_dato="ENTERO",
            descripcion="Umbral de prueba",
        )
    )
    await sesion.flush()
    return 2


# --- El umbral sale de la base ---------------------------------------------


async def test_el_umbral_se_lee_de_parametros_sistema(sesion, umbral_dos) -> None:
    """Quinto criterio de `US-10`: cambiarlo **no** exige desplegar código."""
    # Con umbral 2, una proyectada 3 días antes es A_TIEMPO.
    pedido = await _pedido(sesion, eta_declarada=COMPROMETIDA - dt.timedelta(days=8))
    resultado = await recalcular(sesion, pedido)
    assert resultado.estado_cumplimiento == A_TIEMPO

    # Se sube el umbral en la tabla y el mismo pedido pasa a EN_RIESGO.
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == CLAVE_UMBRAL))
    sesion.add(
        ParametroSistema(
            clave=CLAVE_UMBRAL, valor="10", tipo_dato="ENTERO", descripcion="Umbral ancho"
        )
    )
    await sesion.flush()

    assert (await recalcular(sesion, pedido)).estado_cumplimiento == EN_RIESGO


async def test_sin_fila_en_la_tabla_cae_al_defecto_del_catalogo(sesion) -> None:
    """`parametros.CATALOGO` es la autoridad y la fila solo lo sobreescribe."""
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == CLAVE_UMBRAL))
    await sesion.flush()

    pedido = await _pedido(sesion, eta_declarada=COMPROMETIDA - dt.timedelta(days=7))
    resultado = await recalcular(sesion, pedido)

    assert resultado.estado_cumplimiento is not None  # no revienta sin la fila


# --- Lo que escribe --------------------------------------------------------


async def test_persiste_la_fecha_el_estado_y_el_desglose(sesion, umbral_dos) -> None:
    pedido = await _pedido(sesion, eta_declarada=dt.date(2026, 10, 1))

    resultado = await recalcular(sesion, pedido)
    await sesion.flush()

    destino = await _destino(sesion)
    esperada = dt.date(2026, 10, 1) + dt.timedelta(days=destino.lead_time_dias)
    assert pedido.fecha_proyectada_disponible == esperada
    assert pedido.estado_cumplimiento == resultado.estado_cumplimiento
    assert pedido.estado_calculado == resultado.estado_calculado
    assert pedido.fecha_ultimo_recalculo is not None
    assert resultado.proyeccion.origen == proyeccion.ORIGEN_ETA_DECLARADA


async def test_guarda_la_eta_utilizada_como_instantanea(sesion, umbral_dos) -> None:
    """RF-05 pide el desglose; `eta_utilizada` es la base que se usó."""
    pedido = await _pedido(sesion, eta_declarada=dt.date(2026, 10, 1))
    await recalcular(sesion, pedido)

    assert pedido.eta_utilizada is not None
    assert pedido.eta_utilizada.date() == dt.date(2026, 10, 1)


async def test_sin_fecha_base_deja_todo_nulo_y_lo_explica(sesion, umbral_dos) -> None:
    """El caso del 100 % de las líneas que hoy entran desde el archivo."""
    pedido = await _pedido(sesion)

    resultado = await recalcular(sesion, pedido)
    await sesion.flush()

    assert pedido.fecha_proyectada_disponible is None
    assert pedido.estado_cumplimiento is None  # §1.4: `NULL` es «no se sabe»
    assert pedido.estado_calculado == SIN_TRACKING
    assert pedido.eta_utilizada is None
    assert "no tiene ATA confirmada" in resultado.proyeccion.motivo


async def test_refresca_la_instantanea_del_lead_time(sesion, umbral_dos) -> None:
    """RF-05: la columna guarda el valor **usado en este cálculo**."""
    destino = await _destino(sesion)
    pedido = await _pedido(sesion, eta_declarada=dt.date(2026, 10, 1))
    destino.lead_time_dias = 9
    await sesion.flush()

    await recalcular(sesion, pedido)

    assert pedido.lead_time_destino_dias == 9
    assert pedido.fecha_proyectada_disponible == dt.date(2026, 10, 10)


# --- Lo que NO toca --------------------------------------------------------


async def test_no_pisa_la_etapa_del_viaje(sesion, umbral_dos) -> None:
    """La etapa es la otra dimensión (§1.4) y la produce el rastreo, no esto."""
    elemento = ElementoRastreado(
        tipo_tracking_externo="MMSI", tracking_externo="311001711", via_transporte="MARITIMO"
    )
    sesion.add(elemento)
    await sesion.flush()

    pedido = await _pedido(
        sesion,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="EN_TRANSITO",
        id_elemento_rastreado=elemento.id,
        eta_declarada=dt.date(2026, 10, 1),
    )

    await recalcular(sesion, pedido)
    await sesion.flush()

    assert pedido.etapa_viaje == "EN_TRANSITO"


async def test_no_recalcula_un_pedido_cerrado(sesion, umbral_dos) -> None:
    """RN-13: terminal. Recalcularlo solo podría romper el `CHECK`."""
    pedido = await _pedido(
        sesion,
        eta_declarada=dt.date(2026, 10, 1),
        estado_calculado="CERRADO",
        motivo_cierre="CIERRE_FORZADO",
    )

    resultado = await recalcular(sesion, pedido)
    await sesion.flush()

    assert resultado.cambio is False
    assert pedido.estado_calculado == "CERRADO"
    assert "no se recalcula" in resultado.proyeccion.motivo


async def test_informa_si_algo_cambio(sesion, umbral_dos) -> None:
    """`US-12` va a necesitar saberlo para decidir si vale reescribir."""
    pedido = await _pedido(sesion, eta_declarada=dt.date(2026, 10, 1))

    primero = await recalcular(sesion, pedido)
    segundo = await recalcular(sesion, pedido)

    assert primero.cambio is True
    assert segundo.cambio is False


# --- Que lo escrito respete los CHECK de la tabla --------------------------


@pytest.mark.parametrize(
    ("dias_antes", "esperado"),
    # `margen == dias_antes`: la base ya descuenta el lead time. Con umbral 2:
    # 8 > 2 es holgura, 2 cae justo en la frontera, y -1 es llegar tarde.
    [(8, A_TIEMPO), (3, A_TIEMPO), (2, EN_RIESGO), (0, EN_RIESGO), (-1, RETRASADO)],
)
async def test_el_estado_calculado_entra_sin_violar_el_check(
    sesion, umbral_dos, dias_antes: int, esperado: str
) -> None:
    """Con etapa `EN_TRANSITO` el riesgo manda, y el `CHECK` lo admite.

    Es la prueba que las reglas puras no pueden dar: que el valor derivado cabe
    en el dominio que la columna acepta.
    """
    elemento = ElementoRastreado(
        tipo_tracking_externo="MMSI", tracking_externo="311001712", via_transporte="MARITIMO"
    )
    sesion.add(elemento)
    await sesion.flush()

    destino = await _destino(sesion)
    # La base se elige para que la proyectada caiga `dias_antes` de la comprometida.
    base = COMPROMETIDA - dt.timedelta(days=dias_antes + destino.lead_time_dias)
    pedido = await _pedido(
        sesion,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="EN_TRANSITO",
        id_elemento_rastreado=elemento.id,
        eta_declarada=base,
    )

    resultado = await recalcular(sesion, pedido)
    await sesion.flush()  # si el CHECK se violara, reventaría aquí

    assert resultado.estado_cumplimiento == esperado


# --- El barrido masivo -----------------------------------------------------


@pytest.fixture
async def sin_pedidos(sesion):
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    await sesion.flush()
    return sesion


async def test_recalcular_todos_resume_lo_que_paso(sesion, sin_pedidos, umbral_dos) -> None:
    await _pedido(sesion, eta_declarada=dt.date(2026, 10, 1))
    await _pedido(sesion, oc_numero="4577777778", tracking_interno="TRK-4577777778-010")

    resumen = await recalcular_todos(sesion)

    assert resumen.evaluados == 2
    assert resumen.con_fecha == 1
    assert resumen.sin_fecha == 1
    assert resumen.por_estado is not None
    assert sum(resumen.por_estado.values()) == 2


async def test_recalcular_todos_agrupa_los_motivos_de_no_proyectar(
    sesion, sin_pedidos, umbral_dos
) -> None:
    """Es la vista accionable: dice qué falta para que el motor sirva."""
    await _pedido(sesion)
    await _pedido(sesion, oc_numero="4577777779", tracking_interno="TRK-4577777779-010")

    resumen = await recalcular_todos(sesion)

    assert resumen.por_motivo_sin_fecha is not None
    (motivo,) = resumen.por_motivo_sin_fecha
    assert "no tiene ATA confirmada" in motivo
    assert resumen.por_motivo_sin_fecha[motivo] == 2


async def test_recalcular_todos_salta_los_cerrados(sesion, sin_pedidos, umbral_dos) -> None:
    """Un terminal de RN-13 no cambia: recorrerlo sería trabajo perdido."""
    await _pedido(
        sesion,
        eta_declarada=dt.date(2026, 10, 1),
        estado_calculado="CANCELADO",
        motivo_cierre="CANCELACION",
    )

    resumen = await recalcular_todos(sesion)

    assert resumen.evaluados == 0
