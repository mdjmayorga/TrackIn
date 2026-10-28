"""El historial puede crecer sin frenar el panel — `TASK-10`, RNF-22.

Decisión del 28/10/2026: **no se borra historial.** Con ShipsGo el volumen es
chico (~150 000 filas al año; ver la nota de `TASK-10` en el backlog), y RNF-13
pide conservar el payload original, que ShipsGo archiva. Lo que sostiene RNF-22
es el diseño: el panel lee la posición **desnormalizada** del embarque
(`elementos_rastreados.posicion_actual`, `trayecto_aereo`), nunca el historial.

Estas pruebas cuidan ese diseño. La primera registra todo el SQL que corre
detrás del panel, los mapas y el detalle, y falla si alguno toca
`historial_tracking`: así, una consulta nueva que lo recorriera se detecta el
día que se escribe y no cuando la tabla ya pesa. La segunda verifica que la
única lectura del historial que hace el worker —la última posición de un
embarque— se resuelve con el índice y no recorriendo la tabla.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

import test_pedidos_api as base
from app.services import historial

pytestmark = pytest.mark.integration

api = base.api

#: Lo que se pide al abrir el panel y el detalle de un pedido.
_LECTURAS_DEL_PANEL = (
    "/api/v1/pedidos",
    "/api/v1/pedidos/indicadores",
    "/api/v1/pedidos/proximos-arribos",
    "/api/v1/pedidos/mapa/MARITIMO",
    "/api/v1/pedidos/mapa/AEREO",
)


async def _con_historial(sesion) -> Any:
    """Un pedido rastreado con historial de posiciones, para que haya qué evitar."""
    elemento = await base._elemento(
        sesion,
        tipo_tracking_externo="BL",
        tracking_externo="BLHISTORIAL01",
        posicion_actual=historial.punto_wkt(-79.5, 9.3),
        ultima_actualizacion_api=dt.datetime.now(dt.UTC),
    )
    pedido = await base._pedido(
        sesion,
        "4588900099",
        10,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_TRANSITO",
        estado_calculado="EN_TRANSITO",
    )
    inicio = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
    for hora in range(0, 48, 6):
        await historial.registrar_posicion(
            sesion,
            id_elemento=elemento.id,
            fecha_registro=inicio + dt.timedelta(hours=hora),
            latitud=9.0 + hora / 100,
            longitud=-80.0,
            payload={"lectura": hora},
        )
    await sesion.flush()
    return elemento, pedido


async def test_el_panel_y_el_detalle_no_recorren_el_historial(api, sesion) -> None:
    _, pedido = await _con_historial(sesion)
    consultas: list[str] = []

    def _anotar(_conn, _cursor, sentencia, *_args) -> None:
        consultas.append(sentencia)

    event.listen(Engine, "before_cursor_execute", _anotar)
    try:
        for url in (*_LECTURAS_DEL_PANEL, f"/api/v1/pedidos/{pedido.id}"):
            respuesta = await api.get(url)
            assert respuesta.status_code == 200, (url, respuesta.text)
    finally:
        event.remove(Engine, "before_cursor_execute", _anotar)

    assert consultas, "el registro de SQL no capturó nada: la prueba no estaría probando"
    que_tocan = [c for c in consultas if "historial_tracking" in c]
    assert que_tocan == [], que_tocan


async def test_la_ultima_posicion_de_un_embarque_usa_el_indice(sesion) -> None:
    """Con una tabla chica el planificador prefiere recorrerla; se le prohíbe para ver
    si el índice sirve. Si no sirviera, el plan seguiría siendo un `Seq Scan`."""
    elemento, _ = await _con_historial(sesion)
    await sesion.execute(text("SET LOCAL enable_seqscan = off"))

    plan = "\n".join(
        fila[0]
        for fila in await sesion.execute(
            text(
                "EXPLAIN SELECT * FROM historial_tracking WHERE id_elemento_rastreado = :id "
                "ORDER BY fecha_registro DESC LIMIT 1"
            ),
            {"id": elemento.id},
        )
    )

    assert "Seq Scan" not in plan, plan
    assert "historial_tracking_" in plan, plan  # uno de los dos índices (elemento, fecha)
