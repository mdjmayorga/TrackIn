"""Pruebas de `app.services.historial` — RF-21 / RNF-13 (`US-04`).

Cubre los cuatro criterios de la historia: la lectura se guarda con su payload
crudo, el registro es inmutable, el submuestreo limita una posición por elemento
por intervalo, y el intervalo se cambia sin desplegar código.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text, update

from app.models.elemento_rastreado import ElementoRastreado
from app.models.historial_tracking import HistorialTracking
from app.models.parametro_sistema import ParametroSistema
from app.services import parametros
from app.services.historial import (
    DESCARTE_DUPLICADA,
    DESCARTE_SUBMUESTREO,
    registrar_lote,
    registrar_posicion,
    ultima_lectura,
)

pytestmark = pytest.mark.integration

#: Instante base de las pruebas. Con zona: el servicio rechaza fechas ingenuas.
T0 = dt.datetime(2026, 9, 8, 12, 0, 0, tzinfo=dt.UTC)

#: Moín, aproximadamente. Sirve para comprobar el orden lon/lat.
LAT_MOIN = 10.0
LON_MOIN = -83.08

_contador = iter(range(1, 10_000))


async def _elemento(sesion) -> ElementoRastreado:
    n = next(_contador)
    elemento = ElementoRastreado(
        tipo_tracking_externo="MMSI",
        tracking_externo=f"9{n:08d}",
        via_transporte="MARITIMO",
    )
    sesion.add(elemento)
    await sesion.flush()
    return elemento


async def _intervalo(sesion, segundos: int) -> None:
    clave = "intervalo_minimo_persistencia_s"
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    sesion.add(
        ParametroSistema(
            clave=clave,
            valor=str(segundos),
            tipo_dato="ENTERO",
            descripcion="Intervalo fijado por la prueba.",
        )
    )
    await sesion.flush()


def _lectura(**extra):
    base = {
        "fecha_registro": T0,
        "latitud": LAT_MOIN,
        "longitud": LON_MOIN,
        "payload": {"origen": "prueba"},
    }
    base.update(extra)
    return base


# --- Guardado y payload crudo ---------------------------------------------


async def test_guarda_la_lectura_con_su_payload(sesion) -> None:
    elemento = await _elemento(sesion)
    crudo = {"MMSI": 123456789, "SOG": 12.4, "anidado": {"a": [1, 2]}}

    resultado = await registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        **_lectura(payload=crudo, velocidad=12.4, rumbo=87.5, estado_api="UnderWay"),
    )

    assert resultado.guardada and bool(resultado) is True
    registro = resultado.registro
    assert registro is not None
    assert registro.payload_api == crudo  # íntegro, tal como llegó (RNF-13)
    assert registro.velocidad == Decimal("12.40")
    assert registro.rumbo == Decimal("87.50")
    assert registro.estado_api == "UnderWay"


async def test_la_posicion_queda_en_el_orden_correcto(sesion) -> None:
    """PostGIS toma `lon, lat`; las fuentes reportan `lat, lon`.

    Invertirlos no falla: coloca la carga en otro continente. Se verifica
    leyendo de vuelta las coordenadas desde la base.
    """
    elemento = await _elemento(sesion)
    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    await sesion.flush()

    fila = (
        await sesion.execute(
            text(
                "SELECT ST_Y(posicion::geometry) AS lat, ST_X(posicion::geometry) AS lon "
                "FROM historial_tracking WHERE id_elemento_rastreado = :e"
            ),
            {"e": elemento.id},
        )
    ).one()
    assert fila.lat == pytest.approx(LAT_MOIN)
    assert fila.lon == pytest.approx(LON_MOIN)


async def test_rechaza_una_fecha_sin_zona_horaria(sesion) -> None:
    """Una fecha ingenua se leería como hora local y descuadraría el intervalo."""
    elemento = await _elemento(sesion)
    with pytest.raises(ValueError, match="zona horaria"):
        await registrar_posicion(
            sesion,
            id_elemento=elemento.id,
            **_lectura(fecha_registro=dt.datetime(2026, 9, 8, 12, 0, 0)),
        )


async def test_ultima_lectura_devuelve_la_mas_reciente(sesion) -> None:
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 0)
    for minutos in (0, 10, 5):  # fuera de orden a propósito
        await registrar_posicion(
            sesion,
            id_elemento=elemento.id,
            **_lectura(fecha_registro=T0 + dt.timedelta(minutes=minutos)),
        )
    ultima = await ultima_lectura(sesion, elemento.id)
    assert ultima is not None
    assert ultima.fecha_registro == T0 + dt.timedelta(minutes=10)


async def test_ultima_lectura_sin_historial(sesion) -> None:
    elemento = await _elemento(sesion)
    assert await ultima_lectura(sesion, elemento.id) is None


# --- Submuestreo -----------------------------------------------------------


async def test_descarta_una_lectura_demasiado_proxima(sesion) -> None:
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 300)

    primera = await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    segunda = await registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        **_lectura(fecha_registro=T0 + dt.timedelta(seconds=60)),
    )

    assert primera.guardada
    assert not segunda.guardada
    assert segunda.motivo == DESCARTE_SUBMUESTREO


async def test_acepta_una_lectura_pasado_el_intervalo(sesion) -> None:
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 300)

    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    segunda = await registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        **_lectura(fecha_registro=T0 + dt.timedelta(seconds=300)),
    )
    assert segunda.guardada


async def test_el_submuestreo_es_por_elemento(sesion) -> None:
    """Dos naves distintas no se estorban entre sí."""
    uno, otro = await _elemento(sesion), await _elemento(sesion)
    await _intervalo(sesion, 300)

    assert (await registrar_posicion(sesion, id_elemento=uno.id, **_lectura())).guardada
    assert (await registrar_posicion(sesion, id_elemento=otro.id, **_lectura())).guardada


async def test_el_intervalo_se_cambia_sin_desplegar_codigo(sesion) -> None:
    """Cuarto criterio de `US-04`, y la razón de ser de `parametros_sistema`."""
    elemento = await _elemento(sesion)
    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    proxima = _lectura(fecha_registro=T0 + dt.timedelta(seconds=60))

    await _intervalo(sesion, 300)
    assert not (await registrar_posicion(sesion, id_elemento=elemento.id, **proxima)).guardada

    await _intervalo(sesion, 30)
    assert (await registrar_posicion(sesion, id_elemento=elemento.id, **proxima)).guardada


async def test_forzar_salta_el_submuestreo(sesion) -> None:
    """La lectura que confirma un arribo no se puede perder por el intervalo."""
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 3600)

    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    forzada = await registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        forzar=True,
        **_lectura(fecha_registro=T0 + dt.timedelta(seconds=10)),
    )
    assert forzada.guardada


async def test_una_lectura_fuera_de_orden_tambien_se_submuestrea(sesion) -> None:
    """Llegar tarde no la vuelve valiosa: no aporta un punto nuevo al trayecto."""
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 300)

    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    atrasada = await registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        **_lectura(fecha_registro=T0 - dt.timedelta(seconds=60)),
    )
    assert not atrasada.guardada
    assert atrasada.motivo == DESCARTE_SUBMUESTREO


async def test_sin_fila_de_parametro_usa_el_defecto(sesion) -> None:
    clave = "intervalo_minimo_persistencia_s"
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    await sesion.flush()
    defecto = parametros.CATALOGO[clave].defecto

    elemento = await _elemento(sesion)
    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    dentro = await registrar_posicion(
        sesion,
        id_elemento=elemento.id,
        **_lectura(fecha_registro=T0 + dt.timedelta(seconds=defecto - 1)),
    )
    assert not dentro.guardada


# --- Idempotencia ----------------------------------------------------------


async def test_la_misma_lectura_no_se_guarda_dos_veces(sesion) -> None:
    """Ocurre cuando el worker reprocesa o la fuente reenvía."""
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 0)

    assert (await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())).guardada
    repetida = await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    assert not repetida.guardada
    assert repetida.motivo == DESCARTE_DUPLICADA


async def test_forzar_no_salta_la_idempotencia(sesion) -> None:
    """`forzar` es para el submuestreo; duplicar una lectura es siempre un error."""
    elemento = await _elemento(sesion)
    await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    repetida = await registrar_posicion(sesion, id_elemento=elemento.id, forzar=True, **_lectura())
    assert not repetida.guardada
    assert repetida.motivo == DESCARTE_DUPLICADA


# --- Inmutabilidad (disparador de la migración 0003) ----------------------


async def test_no_se_puede_modificar_un_registro(sesion) -> None:
    """Segundo criterio de `US-04`. Lo impone la base, no el ORM."""
    elemento = await _elemento(sesion)
    resultado = await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    assert resultado.registro is not None

    with pytest.raises(Exception, match="inmutable"):
        await sesion.execute(
            update(HistorialTracking)
            .where(HistorialTracking.id == resultado.registro.id)
            .values(estado_api="alterado")
        )


async def test_no_se_puede_borrar_un_registro(sesion) -> None:
    """`DELETE` se bloquea igual que `UPDATE`: la retención de `TASK-10` tendrá
    que desactivar el disparador a propósito."""
    elemento = await _elemento(sesion)
    resultado = await registrar_posicion(sesion, id_elemento=elemento.id, **_lectura())
    assert resultado.registro is not None

    with pytest.raises(Exception, match="inmutable"):
        await sesion.execute(
            delete(HistorialTracking).where(HistorialTracking.id == resultado.registro.id)
        )


# --- Lotes -----------------------------------------------------------------


async def test_registrar_lote_cuenta_cada_resultado(sesion) -> None:
    """El submuestreo también aplica **dentro** del lote: un worker que acumula
    mensajes un minuto no puede meterlos todos por venir juntos."""
    elemento = await _elemento(sesion)
    await _intervalo(sesion, 300)

    lecturas = [
        _lectura(id_elemento=elemento.id, fecha_registro=T0),
        _lectura(id_elemento=elemento.id, fecha_registro=T0 + dt.timedelta(seconds=30)),
        _lectura(id_elemento=elemento.id, fecha_registro=T0 + dt.timedelta(seconds=60)),
        _lectura(id_elemento=elemento.id, fecha_registro=T0 + dt.timedelta(seconds=600)),
        _lectura(id_elemento=elemento.id, fecha_registro=T0),  # repetida
    ]
    conteo = await registrar_lote(sesion, lecturas)

    assert conteo["guardadas"] == 2  # la primera y la de +600 s
    assert conteo[DESCARTE_SUBMUESTREO] == 2
    assert conteo[DESCARTE_DUPLICADA] == 1

    total = await sesion.scalar(
        select(func.count())
        .select_from(HistorialTracking)
        .where(HistorialTracking.id_elemento_rastreado == elemento.id)
    )
    assert total == 2


async def test_registrar_lote_vacio(sesion) -> None:
    conteo = await registrar_lote(sesion, [])
    assert conteo == {"guardadas": 0, DESCARTE_SUBMUESTREO: 0, DESCARTE_DUPLICADA: 0}
