"""Pruebas de `US-14`: confirmar el desembarco y pasar a proceso aduanal.

La auditoría exige un usuario que exista (FK), así que aquí la API ve a un
usuario de Logística **real**, creado dentro de la transacción de la prueba.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import get_db
from app.main import app
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services import arribo
from app.workers import rastreo

pytestmark = pytest.mark.integration

#: La llegada que se confirma: un martes de la semana pasada, hora de Costa Rica.
LLEGADA = dt.datetime(2026, 9, 22, 8, 15, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
MOTIVO = "La naviera no reportó la descarga; confirmado con el agente aduanal"


class _SinCommit:
    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._sesion.flush()


async def _usuario(sesion, rol: str = "LOGISTICA") -> Usuario:
    cuenta = Usuario(
        usuario=f"{rol.lower()}.us14", nombre_completo=f"{rol} US-14", rol=rol, hash_contrasena="x"
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


@pytest.fixture
async def api(sesion) -> AsyncGenerator[tuple[AsyncClient, Any], None]:
    """Cliente con un usuario real; `como(rol)` cambia de rol en la misma prueba."""

    async def _misma_sesion():
        yield _SinCommit(sesion)

    async def como(rol: str) -> None:
        cuenta = await _usuario(sesion, rol)
        app.dependency_overrides[usuario_actual] = lambda: Autenticado(
            usuario=cuenta, sesion=Sesion(id=0, id_usuario=cuenta.id)
        )

    app.dependency_overrides[get_db] = _misma_sesion
    await como("LOGISTICA")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, como
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(usuario_actual, None)


async def _pedido(sesion, **kwargs) -> PedidoTransito:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    proveedor = Proveedor(codigo=f"P-US14-{len(kwargs)}", nombre="Proveedor")
    material = Material(codigo=f"M-US14-{len(kwargs)}", descripcion="Material", unidad_medida="KG")
    sesion.add_all([proveedor, material])
    await sesion.flush()
    datos = {
        "oc_numero": "4544400001",
        "posicion_oc": 10,
        "tracking_interno": "TRK-4544400001-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": "MARITIMO",
        "cantidad_pedida": Decimal("1.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 10, 30),
        "lead_time_destino_dias": destino.lead_time_dias,
        "etapa_viaje": "SIN_TRACKING",
        "estado_calculado": "SIN_TRACKING",
    }
    datos.update(kwargs)
    pedido = PedidoTransito(**datos)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def _rastreado(sesion, etapa: str = "EN_TRANSITO", **elemento_kwargs) -> PedidoTransito:
    elemento = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR",
        tracking_externo="MRSU0001414",
        via_transporte="MARITIMO",
        **elemento_kwargs,
    )
    sesion.add(elemento)
    await sesion.flush()
    return await _pedido(
        sesion, id_elemento_rastreado=elemento.id, etapa_viaje=etapa, estado_calculado=etapa
    )


def _url(pedido: PedidoTransito, accion: str) -> str:
    return f"/api/v1/pedidos/{pedido.id}/{accion}"


# --- Confirmar el desembarco ------------------------------------------------------


async def test_un_pedido_sin_rastreo_llega_cuando_alguien_lo_confirma(api, sesion) -> None:
    """El caso de 106 de los 107 pedidos: sin referencia, sin hito, sin AIS."""
    cliente, _ = api
    pedido = await _pedido(sesion)

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["etapa_viaje"] == "EN_DESTINO"
    assert cuerpo["calculo"]["origen"] == "ATA_CONFIRMADA"
    assert cuerpo["arribos"]["confirmado"] is not None
    destino = await sesion.get(MaestroDestino, pedido.id_destino)
    assert (
        cuerpo["fecha_proyectada_disponible"]
        == (
            LLEGADA.astimezone(dt.UTC).date() + dt.timedelta(days=destino.lead_time_dias)
        ).isoformat()
    )


async def test_la_llegada_confirmada_manda_sobre_la_eta_de_la_fuente(api, sesion) -> None:
    """Primer criterio: RN-14."""
    cliente, _ = api
    pedido = await _rastreado(sesion, eta_api=dt.datetime(2026, 10, 9, tzinfo=dt.UTC))

    cuerpo = (
        await cliente.post(
            _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
        )
    ).json()

    assert cuerpo["calculo"]["origen"] == "ATA_CONFIRMADA"
    assert cuerpo["eta_utilizada"].startswith("2026-09-22")


async def test_queda_auditado_con_el_autor_de_la_sesion(api, sesion) -> None:
    """Cuarto criterio."""
    cliente, _ = api
    pedido = await _pedido(sesion)

    await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    bitacora = (await cliente.get(_url(pedido, "bitacora"))).json()
    (asiento,) = bitacora
    assert asiento["tipo"] == "CONFIRMACION_DESEMBARCO"
    assert asiento["usuario"] == "logistica.us14"
    assert asiento["valor_anterior"] is None
    assert asiento["valor_nuevo"] == "2026-09-22T14:15:00+00:00"  # en UTC
    assert asiento["motivo"] == MOTIVO


@pytest.mark.parametrize(
    ("ata", "esperado"),
    [
        ((dt.datetime.now(dt.UTC) + dt.timedelta(days=1)).isoformat(), "no puede ser futura"),
        ("2026-09-22T08:15:00", "zona horaria"),
    ],
)
async def test_una_fecha_futura_o_sin_zona_se_rechaza(api, sesion, ata, esperado) -> None:
    """Segundo criterio, y la zona: sin ella, «08:15» es una hora distinta en cada servidor."""
    cliente, _ = api
    pedido = await _pedido(sesion)

    respuesta = await cliente.post(_url(pedido, "desembarco"), json={"ata": ata, "motivo": MOTIVO})

    assert respuesta.status_code == 422
    assert esperado in respuesta.json()["detail"]
    await sesion.refresh(pedido)
    assert pedido.ata_confirmada is None and pedido.etapa_viaje == "SIN_TRACKING"


async def test_sobrescribir_una_llegada_confirmada_exige_confirmarlo(api, sesion) -> None:
    """Tercer criterio."""
    cliente, _ = api
    pedido = await _pedido(sesion)
    await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )
    corregida = (LLEGADA - dt.timedelta(days=1)).isoformat()

    sin_confirmar = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": corregida, "motivo": "Fecha corregida por aduana"}
    )
    confirmado = await cliente.post(
        _url(pedido, "desembarco"),
        json={"ata": corregida, "motivo": "Fecha corregida por aduana", "confirmar": True},
    )

    assert sin_confirmar.status_code == 409
    assert sin_confirmar.json()["requiere_confirmacion"] is True
    actual = dt.datetime.fromisoformat(sin_confirmar.json()["ata_confirmada_actual"])
    assert actual == LLEGADA
    assert confirmado.status_code == 200
    segundo = (await cliente.get(_url(pedido, "bitacora"))).json()[-1]
    assert segundo["valor_anterior"].startswith("2026-09-22T14:15:00")
    assert segundo["valor_nuevo"].startswith("2026-09-21")


async def test_sin_motivo_no_se_confirma(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion)

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": " "}
    )

    assert respuesta.status_code == 422
    assert "motivo es obligatorio" in respuesta.json()["detail"]


async def test_un_pedido_cerrado_no_admite_la_confirmacion(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion, estado_calculado="CANCELADO", motivo_cierre="CANCELACION")

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 409
    assert "RN-13" in respuesta.json()["detail"]


async def test_solo_logistica_confirma(api, sesion) -> None:
    cliente, como = api
    pedido = await _pedido(sesion)
    await como("COMPRAS")

    respuesta = await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 403


async def test_un_pedido_que_no_existe_da_404(api) -> None:
    cliente, _ = api
    respuesta = await cliente.post(
        "/api/v1/pedidos/999999999/desembarco", json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    assert respuesta.status_code == 404


# --- Pasar a proceso aduanal ------------------------------------------------------


async def test_tras_el_desembarco_se_pasa_a_aduana(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion)
    await cliente.post(
        _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
    )

    respuesta = await cliente.post(
        _url(pedido, "paso-aduanal"), json={"motivo": "Documentos entregados al agente"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["etapa_viaje"] == "EN_PROCESO_ADUANAL"
    tipos = [a["tipo"] for a in (await cliente.get(_url(pedido, "bitacora"))).json()]
    assert tipos == ["CONFIRMACION_DESEMBARCO", "PASO_A_ADUANAL"]


async def test_si_el_arribo_lo_dio_la_fuente_no_hace_falta_confirmarlo(api, sesion) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa="EN_DESTINO", ata_api=LLEGADA)

    respuesta = await cliente.post(
        _url(pedido, "paso-aduanal"), json={"motivo": "Documentos entregados al agente"}
    )

    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    ("etapa", "esperado"),
    [
        ("EN_TRANSITO", "Confirme primero el desembarco"),
        ("EN_PROCESO_ADUANAL", "ya está en proceso aduanal"),
        ("RECIBIDO_EN_PLANTA", "ya pasó el proceso aduanal"),
    ],
)
async def test_solo_se_pasa_a_aduana_desde_en_destino(api, sesion, etapa, esperado) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa=etapa)

    respuesta = await cliente.post(
        _url(pedido, "paso-aduanal"), json={"motivo": "Documentos entregados al agente"}
    )

    assert respuesta.status_code == 409
    assert esperado in respuesta.json()["detail"]


# --- Las etapas solo avanzan --------------------------------------------------------


async def test_corregir_la_llegada_de_un_pedido_en_aduana_no_lo_devuelve(api, sesion) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa="EN_PROCESO_ADUANAL")

    cuerpo = (
        await cliente.post(
            _url(pedido, "desembarco"), json={"ata": LLEGADA.isoformat(), "motivo": MOTIVO}
        )
    ).json()

    assert cuerpo["etapa_viaje"] == "EN_PROCESO_ADUANAL"


async def test_el_worker_no_devuelve_a_destino_un_pedido_en_aduana(sesion) -> None:
    """Antes de `US-14`, cada lectura con el hito de arribo lo devolvía."""
    pedido = await _rastreado(sesion, etapa="EN_PROCESO_ADUANAL", ata_api=LLEGADA)

    resultado = await arribo.evaluar(sesion, pedido)

    assert resultado.arribado
    assert pedido.etapa_viaje == "EN_PROCESO_ADUANAL"


@pytest.mark.parametrize(
    ("antes", "de_la_fuente", "despues"),
    [
        ("EN_ORIGEN", "EN_TRANSITO", "EN_TRANSITO"),  # el BL de COSCO del 28/09
        ("EN_TRANSITO", "EN_ORIGEN", "EN_TRANSITO"),  # una lectura vieja no retrocede
        ("EN_DESTINO", "EN_TRANSITO", "EN_DESTINO"),
    ],
)
async def test_el_worker_aplica_la_etapa_de_la_fuente_solo_hacia_adelante(
    sesion, antes, de_la_fuente, despues
) -> None:
    pedido = await _rastreado(sesion, etapa=antes)
    elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)

    await rastreo._arribo_y_recalculo(
        sesion, elemento, rastreo.ResumenCiclo(instante=LLEGADA), LLEGADA, de_la_fuente
    )

    assert pedido.etapa_viaje == despues


# --- RN-02 en la base -----------------------------------------------------------------


async def test_sin_rastreo_ni_llegada_confirmada_la_etapa_sigue_atada(sesion) -> None:
    """La excepción de la migración `0018` es solo la llegada confirmada."""
    pedido = await _pedido(sesion)

    with pytest.raises(IntegrityError, match="ck_pedidos_transito_sin_tracking"):
        async with sesion.begin_nested():
            await sesion.execute(
                text("UPDATE pedidos_transito SET etapa_viaje = 'EN_DESTINO' WHERE id = :id"),
                {"id": pedido.id},
            )

    filas = await sesion.scalars(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert list(filas) == []


# --- US-18: la recepción en planta ya no cierra ----------------------------------------

RECIBIDO = dt.datetime(2026, 9, 29, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
MOTIVO_RECEPCION = "Ingresó a bodega con la guía de despacho completa"


async def _en_aduana(sesion, pedida: str = "100") -> PedidoTransito:
    elemento = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR",
        tracking_externo="MRSU0001818",
        via_transporte="MARITIMO",
    )
    sesion.add(elemento)
    await sesion.flush()
    return await _pedido(
        sesion,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_PROCESO_ADUANAL",
        estado_calculado="EN_PROCESO_ADUANAL",
        ata_confirmada=LLEGADA,
        cantidad_pedida=Decimal(pedida),
    )


def _recepcion(cantidad: str, motivo: str = MOTIVO_RECEPCION) -> dict[str, str]:
    return {"fecha": RECIBIDO.isoformat(), "cantidad": cantidad, "motivo": motivo}


@pytest.mark.parametrize("cantidad", ["100", "90", "130"])
async def test_dentro_de_la_tolerancia_queda_recibido_y_no_cerrado(api, sesion, cantidad) -> None:
    """Primer criterio. 90 es el borde del 10 %; recibir de más no lo impide."""
    cliente, _ = api
    pedido = await _en_aduana(sesion)

    respuesta = await cliente.post(_url(pedido, "recepcion"), json=_recepcion(cantidad))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["etapa_viaje"] == "RECIBIDO_EN_PLANTA"
    assert cuerpo["cierre"]["motivo_cierre"] is None
    assert Decimal(cuerpo["cierre"]["cantidad_recibida"]) == Decimal(cantidad)
    (asiento,) = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert asiento["tipo"] == "RECEPCION_PLANTA"
    assert asiento["valor_nuevo"] == f"{cantidad} KG el 2026-09-29T16:00:00+00:00"


async def test_por_debajo_de_la_tolerancia_no_avanza_y_ofrece_cerrar(api, sesion) -> None:
    """Segundo criterio."""
    cliente, _ = api
    pedido = await _en_aduana(sesion)

    respuesta = await cliente.post(_url(pedido, "recepcion"), json=_recepcion("89.999"))

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["ofrece_cierre_forzado"] is True
    assert Decimal(cuerpo["minimo_conforme"]) == Decimal("90")
    await sesion.refresh(pedido)
    assert pedido.etapa_viaje == "EN_PROCESO_ADUANAL"
    assert pedido.cantidad_recibida is None
    assert (await cliente.get(_url(pedido, "bitacora"))).json() == []


async def test_la_tolerancia_se_ajusta_sin_desplegar(api, sesion) -> None:
    cliente, _ = api
    await sesion.execute(
        text("UPDATE parametros_sistema SET valor = '25' WHERE clave = 'tolerancia_recepcion_pct'")
    )
    pedido = await _en_aduana(sesion)

    respuesta = await cliente.post(_url(pedido, "recepcion"), json=_recepcion("80"))

    assert respuesta.status_code == 200


async def test_el_cierre_forzado_cierra_con_lo_recibido(api, sesion) -> None:
    cliente, _ = api
    pedido = await _en_aduana(sesion)
    pedido.estado_cumplimiento = "RETRASADO"
    await sesion.flush()

    respuesta = await cliente.post(
        _url(pedido, "cierre-forzado"),
        json=_recepcion("60", "El proveedor confirmó que no enviará el resto"),
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado_calculado"] == "CERRADO"
    assert cuerpo["cierre"]["motivo_cierre"] == "CIERRE_FORZADO"
    # El cumplimiento queda como veredicto: el proveedor no cumplió.
    assert cuerpo["estado_cumplimiento"] == "RETRASADO"
    tipos = [a["tipo"] for a in (await cliente.get(_url(pedido, "bitacora"))).json()]
    assert tipos == ["RECEPCION_PLANTA", "CIERRE_FORZADO"]
    # Y cerrado, ya no admite nada: RN-13.
    otra = await cliente.post(_url(pedido, "recepcion"), json=_recepcion("100"))
    assert otra.status_code == 409


@pytest.mark.parametrize(
    ("etapa", "esperado"),
    [
        ("EN_DESTINO", "sin pasar aduana"),
        ("RECIBIDO_EN_PLANTA", "ya se recibió en planta"),
    ],
)
async def test_solo_se_recibe_lo_que_paso_aduana(api, sesion, etapa, esperado) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa=etapa)

    for accion in ("recepcion", "cierre-forzado"):
        respuesta = await cliente.post(_url(pedido, accion), json=_recepcion("1"))
        assert respuesta.status_code == 409
        assert esperado in respuesta.json()["detail"]


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        ({"cantidad": "-1"}, "greater than or equal to 0"),
        ({"fecha": "2026-09-29T10:00:00"}, "zona horaria"),
        ({"fecha": "2099-01-01T10:00:00-06:00"}, "no puede ser futura"),
        ({"motivo": "ok"}, "motivo es obligatorio"),
    ],
)
async def test_los_datos_invalidos_se_rechazan(api, sesion, datos, esperado) -> None:
    cliente, _ = api
    pedido = await _en_aduana(sesion)

    respuesta = await cliente.post(_url(pedido, "recepcion"), json={**_recepcion("100"), **datos})

    assert respuesta.status_code == 422
    assert esperado in respuesta.text


async def test_solo_logistica_recibe(api, sesion) -> None:
    cliente, como = api
    pedido = await _en_aduana(sesion)
    await como("PLANIFICACION")

    respuesta = await cliente.post(_url(pedido, "recepcion"), json=_recepcion("100"))

    assert respuesta.status_code == 403


async def test_recibido_sigue_activo_pero_ya_no_se_rastrea(api, sesion) -> None:
    """Tercer y cuarto criterio: cuenta como activo, y el planificador lo deja."""
    from app.services import planificador

    cliente, _ = api
    pedido = await _en_aduana(sesion)
    await cliente.post(_url(pedido, "recepcion"), json=_recepcion("100"))

    activos = (
        await cliente.get("/api/v1/pedidos", params={"oc": "4544400001", "limite": 200})
    ).json()
    assert [f["etapa_viaje"] for f in activos["items"]] == ["RECIBIDO_EN_PLANTA"]
    assert pedido.id_elemento_rastreado not in await planificador._elementos_con_pedidos_activos(
        sesion
    )


# --- US-47: la liberación de Calidad cierra el pedido ----------------------------------

LIBERADO = dt.datetime(2026, 10, 2, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
MOTIVO_LIBERACION = "Calidad aprobó el certificado de análisis del lote"


async def _recibido(api, sesion, recibida: str = "100") -> PedidoTransito:
    cliente, _ = api
    pedido = await _en_aduana(sesion)
    respuesta = await cliente.post(_url(pedido, "recepcion"), json=_recepcion(recibida))
    assert respuesta.status_code == 200, respuesta.text
    return pedido


def _liberacion(cantidad: str, motivo: str = MOTIVO_LIBERACION) -> dict[str, str]:
    return {"fecha": LIBERADO.isoformat(), "cantidad": cantidad, "motivo": motivo}


async def _detalle(cliente, pedido: PedidoTransito) -> dict[str, Any]:
    return (await cliente.get(f"/api/v1/pedidos/{pedido.id}")).json()


async def test_al_recibir_se_estima_la_ventana_de_calidad_como_rango(api, sesion) -> None:
    """Segundo y tercer criterio: 7 a 15 días hábiles desde el martes 29/09."""
    cliente, _ = api
    pedido = await _recibido(api, sesion)

    cuerpo = await _detalle(cliente, pedido)

    assert cuerpo["cierre"]["liberacion_estimada"] == {
        "desde": "2026-10-08",
        "hasta": "2026-10-20",
    }


async def test_la_ventana_cuenta_desde_el_dia_local_de_la_recepcion(sesion) -> None:
    """Jueves 20:00 en Costa Rica ya es viernes en UTC: manda el jueves."""
    from app.services import intervenciones

    jueves_noche = dt.datetime(2026, 10, 1, 20, 0, tzinfo=dt.timezone(dt.timedelta(hours=-6)))

    ventana = await intervenciones.estimar_liberacion(sesion, jueves_noche)

    assert ventana == (dt.date(2026, 10, 12), dt.date(2026, 10, 22))


async def test_la_ventana_se_ajusta_sin_desplegar(api, sesion) -> None:
    cliente, _ = api
    await sesion.execute(
        text(
            "UPDATE parametros_sistema SET valor = '3' "
            "WHERE clave IN ('ventana_calidad_habiles_min', 'ventana_calidad_habiles_max')"
        )
    )
    pedido = await _recibido(api, sesion)

    cuerpo = await _detalle(cliente, pedido)

    assert cuerpo["cierre"]["liberacion_estimada"] == {
        "desde": "2026-10-02",
        "hasta": "2026-10-02",
    }


async def test_liberar_el_total_cierra_y_sale_del_tablero_activo(api, sesion) -> None:
    """Primer y cuarto criterio."""
    cliente, _ = api
    pedido = await _recibido(api, sesion)

    respuesta = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("100"))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado_calculado"] == "CERRADO"
    assert cuerpo["cierre"]["motivo_cierre"] == "RECEPCION_CONFORME"
    assert dt.datetime.fromisoformat(cuerpo["cierre"]["fecha_liberacion_calidad"]) == LIBERADO
    activos = (await cliente.get("/api/v1/pedidos", params={"oc": "4544400001"})).json()
    assert activos["items"] == []
    asientos = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert [a["tipo"] for a in asientos] == ["RECEPCION_PLANTA", "LIBERACION_CALIDAD"]
    liberacion = asientos[1]
    assert liberacion["motivo"] == MOTIVO_LIBERACION
    assert liberacion["valor_anterior"] == "0 de 100 KG"
    assert liberacion["valor_nuevo"] == "100 de 100 KG el 2026-10-02T15:00:00+00:00"


async def test_se_libera_contra_lo_recibido_no_contra_lo_pedido(api, sesion) -> None:
    """Recibido 95 de 100, dentro de la tolerancia: liberar 95 es el total."""
    cliente, _ = api
    pedido = await _recibido(api, sesion, recibida="95")

    respuesta = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("95"))

    assert respuesta.json()["estado_calculado"] == "CERRADO"


async def test_una_liberacion_parcial_deja_la_linea_activa(api, sesion) -> None:
    """Quinto criterio: activa hasta liberar el total, y cada parte se audita."""
    cliente, _ = api
    pedido = await _recibido(api, sesion)

    parcial = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("40"))

    assert parcial.status_code == 200, parcial.text
    cuerpo = parcial.json()
    assert cuerpo["etapa_viaje"] == "RECIBIDO_EN_PLANTA"
    assert cuerpo["cierre"]["motivo_cierre"] is None
    assert Decimal(cuerpo["cierre"]["cantidad_liberada"]) == Decimal("40")
    assert cuerpo["cierre"]["fecha_liberacion_calidad"] is None
    activos = (await cliente.get("/api/v1/pedidos", params={"oc": "4544400001"})).json()
    assert [f["etapa_viaje"] for f in activos["items"]] == ["RECIBIDO_EN_PLANTA"]

    resto = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("60"))

    assert resto.json()["estado_calculado"] == "CERRADO"
    asientos = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert [a["valor_anterior"] for a in asientos if a["tipo"] == "LIBERACION_CALIDAD"] == [
        "0 de 100 KG",
        "40 de 100 KG",
    ]


async def test_no_se_libera_mas_de_lo_recibido(api, sesion) -> None:
    cliente, _ = api
    pedido = await _recibido(api, sesion)
    await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("70"))

    respuesta = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("31"))

    assert respuesta.status_code == 422
    assert "más de lo recibido" in respuesta.text
    await sesion.refresh(pedido)
    assert pedido.cantidad_liberada == Decimal("70")


@pytest.mark.parametrize("etapa", ["EN_DESTINO", "EN_PROCESO_ADUANAL"])
async def test_solo_se_libera_lo_recibido_en_planta(api, sesion, etapa) -> None:
    cliente, _ = api
    pedido = await _rastreado(sesion, etapa=etapa)

    respuesta = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("1"))

    assert respuesta.status_code == 409
    assert "Registre primero la recepción" in respuesta.json()["detail"]


async def test_un_pedido_cerrado_no_se_libera_otra_vez(api, sesion) -> None:
    cliente, _ = api
    pedido = await _recibido(api, sesion)
    await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("100"))

    respuesta = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("1"))

    assert respuesta.status_code == 409
    assert "RN-13" in respuesta.json()["detail"]


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        ({"cantidad": "0"}, "greater than 0"),
        ({"fecha": "2026-10-02T09:00:00"}, "zona horaria"),
        ({"fecha": "2099-01-01T10:00:00-06:00"}, "no puede ser futura"),
        ({"fecha": "2026-09-28T10:00:00-06:00"}, "anterior a la recepción"),
        ({"motivo": "ok"}, "motivo es obligatorio"),
    ],
)
async def test_los_datos_invalidos_de_la_liberacion_se_rechazan(
    api, sesion, datos, esperado
) -> None:
    cliente, _ = api
    pedido = await _recibido(api, sesion)

    respuesta = await cliente.post(
        _url(pedido, "liberacion-calidad"), json={**_liberacion("100"), **datos}
    )

    assert respuesta.status_code == 422
    assert esperado in respuesta.text


@pytest.mark.parametrize(("rol", "esperado"), [("PLANIFICACION", 200), ("COMPRAS", 403)])
async def test_libera_planificacion_o_logistica(api, sesion, rol, esperado) -> None:
    cliente, como = api
    pedido = await _recibido(api, sesion)
    await como(rol)

    respuesta = await cliente.post(_url(pedido, "liberacion-calidad"), json=_liberacion("100"))

    assert respuesta.status_code == esperado


# --- US-40: el ajuste manual de la fecha proyectada ------------------------------------

MOTIVO_AJUSTE = "El puerto anunció cierre por feriado el lunes"
COMPROMETIDA = dt.date(2026, 10, 30)


async def _proyectado(sesion, holgura_dias: int = 10) -> PedidoTransito:
    """Un pedido con ETA declarada que llega `holgura_dias` antes de lo comprometido."""
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    eta = COMPROMETIDA - dt.timedelta(days=destino.lead_time_dias + holgura_dias)
    return await _pedido(sesion, eta_declarada=eta, fecha_entrega_pedido=COMPROMETIDA)


def _ajuste(dias: int, motivo: str = MOTIVO_AJUSTE) -> dict[str, Any]:
    return {"dias": dias, "motivo": motivo}


async def test_el_ajuste_entra_en_la_formula_y_se_recalcula(api, sesion) -> None:
    """Primer criterio: con 15 días de ajuste, 10 de holgura pasan a 5 de atraso."""
    cliente, _ = api
    pedido = await _proyectado(sesion)

    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(15))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["fecha_proyectada_disponible"] == "2026-11-04"
    assert cuerpo["estado_cumplimiento"] == "RETRASADO"
    assert cuerpo["calculo"]["ajuste_manual_dias"] == 15
    assert cuerpo["calculo"]["margen_dias"] == -5


async def test_el_ajuste_aparece_como_sumando_propio(api, sesion) -> None:
    """Cuarto criterio, con los dos signos."""
    cliente, _ = api
    pedido = await _proyectado(sesion)

    adelanta = (await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(-2))).json()

    desglose = adelanta["calculo"]["desglose"]
    assert "d de lead time - 2 d de ajuste manual = 2026-10-18" in desglose
    assert adelanta["calculo"]["al_dia"] is True


async def test_cada_ajuste_queda_auditado_con_el_anterior_y_el_nuevo(api, sesion) -> None:
    """Segundo y tercer criterio. El ajuste reemplaza al anterior, no se acumula."""
    cliente, _ = api
    pedido = await _proyectado(sesion)

    await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(3))
    otro = await cliente.post(
        _url(pedido, "ajuste-manual"), json=_ajuste(5, "La naviera confirmó dos días más")
    )

    assert otro.json()["calculo"]["ajuste_manual_dias"] == 5
    asientos = (await cliente.get(_url(pedido, "bitacora"))).json()
    assert [(a["tipo"], a["valor_anterior"], a["valor_nuevo"]) for a in asientos] == [
        ("AJUSTE_MANUAL", "0", "3"),
        ("AJUSTE_MANUAL", "3", "5"),
    ]
    assert asientos[0]["motivo"] == MOTIVO_AJUSTE


async def test_poner_cero_quita_el_ajuste(api, sesion) -> None:
    cliente, _ = api
    pedido = await _proyectado(sesion)
    await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(4))

    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(0))

    assert "ajuste" not in respuesta.json()["calculo"]["desglose"]


async def test_repetir_el_mismo_ajuste_no_deja_asiento(api, sesion) -> None:
    cliente, _ = api
    pedido = await _proyectado(sesion)
    await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(4))

    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(4))

    assert respuesta.status_code == 409
    assert len((await cliente.get(_url(pedido, "bitacora"))).json()) == 1


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        ({"motivo": "ok"}, "motivo es obligatorio"),
        ({"dias": 366}, "less than or equal to 365"),
        ({"dias": -366}, "greater than or equal to -365"),
    ],
)
async def test_los_ajustes_invalidos_se_rechazan(api, sesion, datos, esperado) -> None:
    cliente, _ = api
    pedido = await _proyectado(sesion)

    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json={**_ajuste(3), **datos})

    assert respuesta.status_code == 422
    assert esperado in respuesta.text
    await sesion.refresh(pedido)
    assert pedido.ajuste_manual_dias == 0


async def test_un_pedido_cerrado_no_se_ajusta(api, sesion) -> None:
    cliente, _ = api
    pedido = await _pedido(sesion, motivo_cierre="CANCELACION", estado_calculado="CANCELADO")

    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(3))

    assert respuesta.status_code == 409
    assert "RN-13" in respuesta.json()["detail"]


async def test_solo_logistica_ajusta(api, sesion) -> None:
    cliente, como = api
    pedido = await _proyectado(sesion)
    await como("PLANIFICACION")

    respuesta = await cliente.post(_url(pedido, "ajuste-manual"), json=_ajuste(3))

    assert respuesta.status_code == 403
