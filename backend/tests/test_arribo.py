"""Pruebas de `app.services.arribo` — `US-11` / RN-05.

Contra la base **y contra PostGIS**: la geocerca es una distancia sobre el
elipsoide, y probarla con un doble solo verificaría que se llama a
`ST_Distance`, no que Moín y Limón —que están a 5,5 km— no se confunden.

Las coordenadas salen de los cuatro destinos reales que siembra la migración
`0002`, confirmados por Planeación el 04/09.
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
from app.services import arribo, historial

pytestmark = pytest.mark.integration

#: Moín, el destino de contenedores del Caribe. Radio propio de 2 km.
MOIN = (-83.0800, 10.0000)
#: Un punto a ~40 km de Moín: fuera de su radio de 2 km, dentro de 50 km.
ALTA_MAR = (-82.7200, 10.0000)


async def _destino(sesion, codigo: str) -> MaestroDestino:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == codigo))
    assert destino is not None, "la migración 0002 siembra los cuatro destinos"
    return destino


async def _maestros(sesion) -> tuple[Proveedor, Material]:
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-ARR-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-ARR-1", nombre="Proveedor de arribos")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-ARR-1"))
    if material is None:
        material = Material(codigo="M-ARR-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()
    return proveedor, material


async def _elemento(
    sesion,
    tracking: str = "MRSU8507472",
    via: str = "MARITIMO",
    posicion: tuple[float, float] | None = None,
    ata_api: dt.datetime | None = None,
) -> ElementoRastreado:
    nuevo = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR",
        tracking_externo=tracking,
        via_transporte=via,
        ata_api=ata_api,
    )
    if posicion is not None:
        nuevo.posicion_actual = historial.punto_wkt(*posicion)
    sesion.add(nuevo)
    await sesion.flush()
    return nuevo


async def _pedido(
    sesion,
    elemento: ElementoRastreado | None = None,
    destino_codigo: str = "CRMOB",
    oc: str = "4588888888",
    **kwargs,
) -> PedidoTransito:
    destino = await _destino(sesion, destino_codigo)
    proveedor, material = await _maestros(sesion)

    base = {
        "oc_numero": oc,
        "posicion_oc": 10,
        "tracking_interno": f"TRK-{oc}-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": destino.via_transporte,
        "cantidad_pedida": Decimal("1.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 10, 10),
        "lead_time_destino_dias": destino.lead_time_dias,
        # RN-02: con elemento asociado la etapa no puede ser `SIN_TRACKING`.
        "etapa_viaje": "EN_TRANSITO" if elemento is not None else "SIN_TRACKING",
        "estado_calculado": "EN_TRANSITO" if elemento is not None else "SIN_TRACKING",
        "id_elemento_rastreado": elemento.id if elemento is not None else None,
    }
    base.update(kwargs)
    pedido = PedidoTransito(**base)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


@pytest.fixture
async def sin_pedidos(sesion):
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    await sesion.flush()
    return sesion


# --- La señal primaria: el hito de la fuente -------------------------------


async def test_un_hito_de_arribo_da_por_llegado(sesion, sin_pedidos) -> None:
    """El mecanismo primario desde que se midió que no hay cobertura AIS.

    `colector_shipsgo` solo puebla `ata_api` con hitos **en el destino**: los
    arribos a puertos de transbordo no llegan hasta acá.
    """
    llegada = dt.datetime(2026, 9, 15, 18, 0, tzinfo=dt.UTC)
    elemento = await _elemento(sesion, ata_api=llegada)
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)
    await sesion.flush()

    assert resultado.arribado is True
    assert resultado.origen == arribo.ORIGEN_FUENTE
    assert resultado.instante == llegada
    assert pedido.etapa_viaje == "EN_DESTINO"


async def test_un_hito_no_se_marca_como_inferido(sesion, sin_pedidos) -> None:
    """RN-05 exige distinguir los tres orígenes.

    Un `DISC` de la naviera **no** es una deducción nuestra: es un dato.
    Marcarlo como inferido haría que el usuario desconfiara de lo que no debe.
    """
    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.inferido is False
    assert pedido.ata_inferida is None


async def test_el_hito_gana_a_la_geocerca(sesion, sin_pedidos) -> None:
    """Aunque la nave esté lejos: el hito es explícito y la distancia deduce."""
    elemento = await _elemento(
        sesion, posicion=ALTA_MAR, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC)
    )
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.origen == arribo.ORIGEN_FUENTE


# --- Lo confirmado a mano manda --------------------------------------------


async def test_una_ata_confirmada_no_se_reevalua(sesion, sin_pedidos) -> None:
    """Ya lo confirmó una persona (`US-14`). No hay nada que deducir."""
    confirmada = dt.datetime(2026, 9, 14, tzinfo=dt.UTC)
    elemento = await _elemento(sesion, posicion=ALTA_MAR)
    pedido = await _pedido(sesion, elemento, ata_confirmada=confirmada)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.origen == arribo.ORIGEN_CONFIRMADO
    assert resultado.instante == confirmada


# --- La geocerca, como verificación secundaria -----------------------------


async def test_dentro_del_radio_se_infiere_el_arribo(sesion, sin_pedidos) -> None:
    """Y se marca **como inferido**, que es lo que exige RN-05."""
    elemento = await _elemento(sesion, posicion=MOIN)
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)
    await sesion.flush()

    assert resultado.arribado is True
    assert resultado.origen == arribo.ORIGEN_GEOCERCA
    assert resultado.inferido is True
    assert pedido.ata_inferida is not None
    assert pedido.etapa_viaje == "EN_DESTINO"


async def test_fuera_del_radio_no_se_infiere_nada(sesion, sin_pedidos) -> None:
    elemento = await _elemento(sesion, posicion=ALTA_MAR)
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is False
    assert resultado.motivo == arribo.SIN_ARRIBO
    assert resultado.distancia_m is not None
    assert resultado.distancia_m > 2000  # el radio de Moín
    assert pedido.etapa_viaje == "EN_TRANSITO"


async def test_sin_posicion_no_hay_geocerca_que_evaluar(sesion, sin_pedidos) -> None:
    """Es lo normal: ShipsGo no garantiza la posición —el BL de COSCO vino sin
    ella— y el AIS no cubre ningún puerto de Gutis."""
    elemento = await _elemento(sesion, posicion=None)
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is False
    assert resultado.distancia_m is None


# --- Moín y Limón: la razón de que el radio sea por destino ----------------


async def test_el_radio_propio_del_destino_manda_sobre_el_global(sesion, sin_pedidos) -> None:
    """Moín declara 2 km; el parámetro global son 50 km.

    Con el global, un buque en Moín contaría como arribado a Limón y al revés:
    están a 5,5 km. Por eso los dos bajaron a 2 km en la migración `0002`.
    """
    moin = await _destino(sesion, "CRMOB")
    assert moin.radio_geocerca_km == 2

    # Un punto a ~4 km de Moín: fuera de sus 2 km, muy dentro de 50 km.
    elemento = await _elemento(sesion, posicion=(-83.0435, 10.0000))
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is False, "el radio propio de 2 km es el que manda"
    assert resultado.distancia_m is not None
    assert 3000 < resultado.distancia_m < 5000


async def test_un_buque_en_moin_no_arriba_a_limon(sesion, sin_pedidos) -> None:
    """La confusión concreta que los radios de 2 km evitan."""
    elemento = await _elemento(sesion, posicion=MOIN)
    pedido = await _pedido(sesion, elemento, destino_codigo="CRLIO")

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is False
    assert resultado.distancia_m is not None
    assert 4000 < resultado.distancia_m < 7000  # los ~5,5 km medidos


async def test_sin_radio_propio_se_usa_el_global(sesion, sin_pedidos) -> None:
    """Y el global sale de `parametros_sistema`, ajustable sin desplegar."""
    moin = await _destino(sesion, "CRMOB")
    moin.radio_geocerca_km = None
    await sesion.execute(
        delete(ParametroSistema).where(ParametroSistema.clave == arribo.CLAVE_RADIO)
    )
    sesion.add(
        ParametroSistema(
            clave=arribo.CLAVE_RADIO,
            valor="50",
            tipo_dato="ENTERO",
            descripcion="Radio de prueba",
        )
    )
    await sesion.flush()

    elemento = await _elemento(sesion, posicion=(-83.0435, 10.0000))  # ~4 km
    pedido = await _pedido(sesion, elemento)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is True, "4 km caben en los 50 km globales"


async def test_el_radio_global_se_cambia_sin_desplegar(sesion, sin_pedidos) -> None:
    """Cuarto criterio de `US-11`."""
    moin = await _destino(sesion, "CRMOB")
    moin.radio_geocerca_km = None
    await sesion.execute(
        delete(ParametroSistema).where(ParametroSistema.clave == arribo.CLAVE_RADIO)
    )
    sesion.add(
        ParametroSistema(
            clave=arribo.CLAVE_RADIO, valor="1", tipo_dato="ENTERO", descripcion="Estrecho"
        )
    )
    await sesion.flush()

    elemento = await _elemento(sesion, posicion=(-83.0435, 10.0000))  # ~4 km
    pedido = await _pedido(sesion, elemento)

    assert (await arribo.evaluar(sesion, pedido)).arribado is False


# --- La vía aérea no usa geocerca ------------------------------------------


async def test_en_aereo_la_geocerca_no_cuenta(sesion, sin_pedidos) -> None:
    """Decisión del 25/08: 50 km alrededor de un aeropuerto capturan tráfico
    en sobrevuelo. Un avión rumbo a Panamá entraría sin haber aterrizado."""
    aeropuerto = await _destino(sesion, "MROC")
    elemento = await _elemento(
        sesion, tracking="020-50685434", via="AEREO", posicion=(-84.2088, 9.9939)
    )
    pedido = await _pedido(sesion, elemento, destino_codigo=aeropuerto.codigo)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is False
    assert resultado.motivo == arribo.SIN_ARRIBO


async def test_en_aereo_el_hito_si_cuenta(sesion, sin_pedidos) -> None:
    """`RCF` en el aeropuerto de destino, que es lo que mapea `US-46`."""
    elemento = await _elemento(
        sesion,
        tracking="020-50685434",
        via="AEREO",
        ata_api=dt.datetime(2026, 9, 5, 18, 43, tzinfo=dt.UTC),
    )
    pedido = await _pedido(sesion, elemento, destino_codigo="MROC")

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is True
    assert resultado.origen == arribo.ORIGEN_FUENTE


# --- Apagar el elemento: decisión B7 del 01/09 -----------------------------


async def test_el_elemento_se_apaga_cuando_todos_sus_pedidos_llegaron(sesion, sin_pedidos) -> None:
    """La nave zarpa hacia otro puerto y su posición deja de representar la
    carga; seguir consultándola es pagar por un dato que ya no significa nada."""
    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    pedido = await _pedido(sesion, elemento)

    await arribo.evaluar(sesion, pedido)
    await sesion.flush()

    assert elemento.activo is False


async def test_no_se_apaga_si_queda_un_pedido_en_camino(sesion, sin_pedidos) -> None:
    """Un contenedor puede amparar varias líneas: apagarlo con una sola
    arribada dejaría ciegas a las demás."""
    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    uno = await _pedido(sesion, elemento, oc="4588888801")
    await _pedido(sesion, elemento, oc="4588888802")

    await arribo.evaluar(sesion, uno)
    await sesion.flush()

    assert elemento.activo is True


async def test_se_apaga_al_llegar_el_ultimo(sesion, sin_pedidos) -> None:
    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    uno = await _pedido(sesion, elemento, oc="4588888801")
    otro = await _pedido(sesion, elemento, oc="4588888802")

    await arribo.evaluar(sesion, uno)
    await arribo.evaluar(sesion, otro)
    await sesion.flush()

    assert elemento.activo is False


async def test_un_pedido_cerrado_no_impide_apagar(sesion, sin_pedidos) -> None:
    """Un terminal de RN-13 ya no espera nada de la nave."""
    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    uno = await _pedido(sesion, elemento, oc="4588888801")
    await _pedido(
        sesion,
        elemento,
        oc="4588888802",
        estado_calculado="CANCELADO",
        motivo_cierre="CANCELACION",
    )

    await arribo.evaluar(sesion, uno)
    await sesion.flush()

    assert elemento.activo is False


# --- Sin rastreo -----------------------------------------------------------


async def test_un_pedido_sin_elemento_no_se_evalua(sesion, sin_pedidos) -> None:
    """Es el estado del 100 % de las líneas que hoy entran del archivo."""
    pedido = await _pedido(sesion, elemento=None)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado is False
    assert resultado.motivo == arribo.SIN_ELEMENTO


# --- El barrido ------------------------------------------------------------


async def test_el_barrido_resume_por_origen(sesion, sin_pedidos) -> None:
    por_hito = await _elemento(
        sesion, tracking="MRSU8507472", ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC)
    )
    por_geocerca = await _elemento(sesion, tracking="MRSU8132490", posicion=MOIN)
    lejos = await _elemento(sesion, tracking="TGBU4872990", posicion=ALTA_MAR)
    await _pedido(sesion, por_hito, oc="4588888801")
    await _pedido(sesion, por_geocerca, oc="4588888802")
    await _pedido(sesion, lejos, oc="4588888803")

    resumen = await arribo.evaluar_todos(sesion)

    assert resumen.evaluados == 3
    assert resumen.arribados == 2
    assert resumen.por_fuente == 1
    assert resumen.por_geocerca == 1
    assert resumen.elementos_apagados == 2


async def test_el_barrido_salta_lo_que_ya_esta_en_destino(sesion, sin_pedidos) -> None:
    """No hay arribo que detectar en algo que ya llegó."""
    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    await _pedido(sesion, elemento, etapa_viaje="EN_DESTINO", estado_calculado="EN_DESTINO")

    resumen = await arribo.evaluar_todos(sesion)

    assert resumen.evaluados == 0


async def test_el_barrido_sobre_una_base_vacia_no_falla(sesion, sin_pedidos) -> None:
    resumen = await arribo.evaluar_todos(sesion)
    assert resumen.evaluados == 0


# --- Las dos dimensiones del estado componen (US-11 + US-10) ---------------


async def test_el_arribo_mueve_la_etapa_y_el_recalculo_deriva_el_estado(
    sesion, sin_pedidos
) -> None:
    """Cada modulo escribe **su** dimension, y juntas dan el estado unico.

    `arribo` pone `etapa_viaje` (RN-02..RN-06) y `recalculo` deriva
    `estado_calculado` de las dos (§1.4). Acoplarlos dentro de uno de los dos
    volveria a colapsar las preguntas que el modelo separo a proposito; el
    orden lo decide el planificador de `US-07`.
    """
    from app.services.recalculo import recalcular

    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    # Fecha proyectada holgada: el cumplimiento no debe tapar la etapa.
    pedido = await _pedido(sesion, elemento, eta_declarada=dt.date(2026, 9, 15))

    await arribo.evaluar(sesion, pedido)
    resultado = await recalcular(sesion, pedido)
    await sesion.flush()

    assert pedido.etapa_viaje == "EN_DESTINO"
    assert resultado.estado_calculado == "EN_DESTINO"


async def test_el_riesgo_sigue_mandando_sobre_la_etapa_recien_puesta(sesion, sin_pedidos) -> None:
    """Llegar tarde a destino sigue siendo llegar tarde.

    Es la precedencia de §1.4: el riesgo gana a la etapa porque es la
    informacion por la que existe el sistema.
    """
    from app.services.recalculo import recalcular

    elemento = await _elemento(sesion, ata_api=dt.datetime(2026, 9, 15, tzinfo=dt.UTC))
    # Proyectada muy posterior a la comprometida (2026-10-10).
    pedido = await _pedido(sesion, elemento, eta_declarada=dt.date(2026, 11, 20))

    await arribo.evaluar(sesion, pedido)
    resultado = await recalcular(sesion, pedido)
    await sesion.flush()

    assert pedido.etapa_viaje == "EN_DESTINO"
    assert resultado.estado_calculado == "RETRASADO"


async def test_la_geocerca_ve_una_posicion_recien_escrita(sesion, sin_pedidos) -> None:
    """Regresion: sin *flush* la subconsulta leia la posicion vieja.

    `colector_shipsgo` asigna `posicion_actual` **despues** de su propio
    *flush*, asi que al evaluar el arribo a continuacion el valor seguia
    pendiente en memoria. `ST_Distance(NULL, ...)` devuelve `NULL`, que este
    modulo lee como «no hay posicion» — un caso legitimo — y la geocerca no
    disparaba nunca, sin un solo error a la vista.
    """
    import json
    from pathlib import Path

    from app.services.rastreo import colector_shipsgo

    grabado = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
    payload = json.loads((grabado / "06_payload_personal.json").read_text(encoding="utf-8"))
    embarque = payload["embarques"][0]

    elemento = await _elemento(sesion, posicion=None)
    pedido = await _pedido(sesion, elemento)

    # Escribe la posicion (Caribe panameno, ~357 km de Moin) y evalua **sin**
    # flush intermedio, que es como lo hara el planificador de `US-07`.
    await colector_shipsgo.procesar(
        sesion, elemento, embarque["payload_shipment"], embarque["payload_geojson"]
    )
    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.distancia_m is not None, "la posicion recien escrita tiene que verse"
    assert 300_000 < resultado.distancia_m < 400_000
    assert resultado.arribado is False
