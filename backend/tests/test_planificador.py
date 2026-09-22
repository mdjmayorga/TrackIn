"""Pruebas de `app.services.planificador` — `US-07` / RF-08.

Lo que se fija aquí son los tres puntos donde esta historia cambió al cerrar
`TASK-28`, que son justo los que se implementan mal si uno lee el criterio
original:

1. La frecuencia se relee **en cada tic**, no se captura al arrancar.
2. Un embarque **madurando** no es un fallo ni una respuesta vacía.
3. Lo que cuesta dinero es el **alta**, no la consulta.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.services import parametros, planificador
from app.services.rastreo.registro_embarque import TIPO_INTERVENCION

pytestmark = pytest.mark.integration

#: Mediodía: dentro de la ventana aérea por defecto (6 a 22).
MEDIODIA = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
MADRUGADA = dt.datetime(2026, 9, 22, 3, 0, tzinfo=dt.UTC)


async def _fijar(sesion, clave: str, valor: str) -> None:
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    sesion.add(
        ParametroSistema(
            clave=clave, valor=valor, tipo_dato="ENTERO", descripcion="Valor de prueba"
        )
    )
    await sesion.flush()


async def _elemento(
    sesion,
    tracking: str,
    via: str = "MARITIMO",
    ultima: dt.datetime | None = None,
    activo: bool = True,
) -> ElementoRastreado:
    nuevo = ElementoRastreado(
        tipo_tracking_externo="CONTENEDOR" if via == "MARITIMO" else "MAWB",
        tracking_externo=tracking,
        via_transporte=via,
        ultima_actualizacion_api=ultima,
        activo=activo,
    )
    sesion.add(nuevo)
    await sesion.flush()
    return nuevo


async def _pedido(sesion, elemento: ElementoRastreado, oc: str, **kwargs) -> PedidoTransito:
    destino = await sesion.scalar(
        select(MaestroDestino).where(
            MaestroDestino.via_transporte == elemento.via_transporte,
            MaestroDestino.activo.is_(True),
        )
    )
    assert destino is not None
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-PLA-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-PLA-1", nombre="Proveedor")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-PLA-1"))
    if material is None:
        material = Material(codigo="M-PLA-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()

    base = {
        "oc_numero": oc,
        "posicion_oc": 10,
        "tracking_interno": f"TRK-{oc}-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": elemento.via_transporte,
        "cantidad_pedida": Decimal("1.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 10, 10),
        "lead_time_destino_dias": destino.lead_time_dias,
        "etapa_viaje": "EN_TRANSITO",
        "estado_calculado": "EN_TRANSITO",
        "id_elemento_rastreado": elemento.id,
    }
    base.update(kwargs)
    pedido = PedidoTransito(**base)
    sesion.add(pedido)
    await sesion.flush()
    return pedido


@pytest.fixture
async def limpio(sesion):
    await sesion.execute(delete(AuditoriaIntervencion))
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    await sesion.flush()
    return sesion


# --- El primer criterio: sin reiniciar el servicio -------------------------


async def test_la_frecuencia_se_relee_en_cada_tic(sesion, limpio) -> None:
    """*«Cuando modifico el parámetro, el planificador aplica el nuevo intervalo
    sin reiniciar el servicio»*.

    Se prueba cambiándolo **entre dos llamadas** y viendo que el mismo elemento
    cambia de omitido a planificado.
    """
    hace_dos_horas = MEDIODIA - dt.timedelta(hours=2)
    elemento = await _elemento(sesion, "MRSU8507472", ultima=hace_dos_horas)
    await _pedido(sesion, elemento, "4599000001")

    await _fijar(sesion, planificador.CLAVE_FRECUENCIA_MARITIMA, "360")  # 6 h
    primero = await planificador.planificar(sesion, MEDIODIA)
    assert primero.total == 0

    await _fijar(sesion, planificador.CLAVE_FRECUENCIA_MARITIMA, "60")  # 1 h
    segundo = await planificador.planificar(sesion, MEDIODIA)

    assert segundo.total == 1


async def test_un_elemento_nunca_consultado_va_ya(sesion, limpio) -> None:
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    await _pedido(sesion, elemento, "4599000001")

    plan = await planificar_en(sesion)

    assert [t.tracking for t in plan.tareas] == ["MRSU8507472"]


async def planificar_en(sesion, instante: dt.datetime = MEDIODIA):
    return await planificador.planificar(sesion, instante)


async def test_el_intervalo_sin_vencer_se_omite_con_su_motivo(sesion, limpio) -> None:
    elemento = await _elemento(sesion, "MRSU8507472", ultima=MEDIODIA - dt.timedelta(minutes=5))
    await _pedido(sesion, elemento, "4599000001")

    plan = await planificar_en(sesion)

    assert plan.total == 0
    assert plan.motivos_omitidos() == {planificador.OMITIDO_SIN_VENCER: 1}


async def test_cada_via_usa_su_propia_frecuencia(sesion, limpio) -> None:
    """La aérea es más corta: los hitos CIMP se mueven más rápido que un buque."""
    await _fijar(sesion, planificador.CLAVE_FRECUENCIA_AEREA, "60")
    await _fijar(sesion, planificador.CLAVE_FRECUENCIA_MARITIMA, "360")
    hace_dos_horas = MEDIODIA - dt.timedelta(hours=2)

    aereo = await _elemento(sesion, "020-50685434", via="AEREO", ultima=hace_dos_horas)
    maritimo = await _elemento(sesion, "MRSU8507472", ultima=hace_dos_horas)
    await _pedido(sesion, aereo, "4599000001")
    await _pedido(sesion, maritimo, "4599000002")

    plan = await planificar_en(sesion)

    assert plan.por_via() == {"AEREO": 1}


# --- El segundo criterio: la ventana activa --------------------------------


async def test_fuera_de_la_ventana_el_aereo_se_suspende(sesion, limpio) -> None:
    """*«Fuera de la ventana suspendo el sondeo»*."""
    aereo = await _elemento(sesion, "020-50685434", via="AEREO", ultima=None)
    await _pedido(sesion, aereo, "4599000001")

    plan = await planificar_en(sesion, MADRUGADA)

    assert plan.total == 0
    assert plan.motivos_omitidos() == {planificador.OMITIDO_FUERA_DE_VENTANA: 1}


async def test_la_ventana_no_afecta_al_maritimo(sesion, limpio) -> None:
    """Un buque no descansa de noche."""
    maritimo = await _elemento(sesion, "MRSU8507472", ultima=None)
    await _pedido(sesion, maritimo, "4599000001")

    plan = await planificar_en(sesion, MADRUGADA)

    assert plan.total == 1


@pytest.mark.parametrize(
    ("inicio", "fin", "hora", "dentro"),
    [
        (6, 22, 12, True),
        (6, 22, 3, False),
        (6, 22, 22, False),  # el fin es exclusivo
        (6, 22, 6, True),  # el inicio es inclusivo
        (22, 6, 23, True),  # ventana que cruza la medianoche
        (22, 6, 3, True),
        (22, 6, 12, False),
    ],
)
def test_la_ventana_soporta_cruzar_la_medianoche(
    inicio: int, fin: int, hora: int, dentro: bool
) -> None:
    """Nada impide configurarla así, y fallar ahí sería silencioso: se
    sondearía justo al revés de lo pedido."""
    politica = planificador.Politica(60, 360, inicio, fin, 120, 20)
    instante = dt.datetime(2026, 9, 22, hora, 0, tzinfo=dt.UTC)

    assert politica.en_ventana(instante) is dentro


# --- El tercer estado: dado de alta pero sin datos -------------------------


async def test_un_embarque_madurando_se_reprograma_a_corto_plazo(sesion, limpio) -> None:
    """A los 45 s del alta devolvía `NEW`; a los ~90 s estaba completo.

    Esperar seis horas por él sería tener pagado un embarque y no mirarlo.
    """
    await _fijar(sesion, planificador.CLAVE_MADURACION, "120")
    hace_tres_minutos = MEDIODIA - dt.timedelta(minutes=3)
    elemento = await _elemento(sesion, "MRSU8507472", ultima=hace_tres_minutos)
    await _pedido(sesion, elemento, "4599000001")

    # Sin marcar: seis horas de intervalo, no le toca.
    assert (await planificar_en(sesion)).total == 0

    # Marcado como madurando: los 120 s ya vencieron.
    plan = await planificador.planificar(sesion, MEDIODIA, madurando={elemento.id})

    assert plan.total == 1
    assert plan.tareas[0].madurando is True


async def test_madurar_no_cuenta_como_fallo(sesion, limpio) -> None:
    """Tratarlo como fallo degradaría la fuente por algo que no falló.

    El plan lo distingue con su propia marca, no con un motivo de omisión.
    """
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    await _pedido(sesion, elemento, "4599000001")

    plan = await planificador.planificar(sesion, MEDIODIA, madurando={elemento.id})

    assert plan.omitidos == []
    assert plan.tareas[0].madurando is True


# --- Lo que sale del ciclo -------------------------------------------------


async def test_un_elemento_apagado_no_se_consulta(sesion, limpio) -> None:
    """Decisión B7: `US-11` lo apaga al arribar y aquí deja de aparecer."""
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None, activo=False)
    await _pedido(sesion, elemento, "4599000001")

    plan = await planificar_en(sesion)

    assert plan.total == 0
    assert plan.motivos_omitidos() == {planificador.OMITIDO_INACTIVO: 1}


async def test_un_elemento_sin_pedidos_vivos_no_se_consulta(sesion, limpio) -> None:
    """Cubre el caso de que la única línea que lo usaba se cerrara por RN-13:
    el elemento sigue `activo` pero ya no lleva carga nuestra."""
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    await _pedido(
        sesion,
        elemento,
        "4599000001",
        estado_calculado="CANCELADO",
        motivo_cierre="CANCELACION",
    )

    plan = await planificar_en(sesion)

    assert plan.total == 0
    assert plan.motivos_omitidos() == {planificador.OMITIDO_SIN_PEDIDOS: 1}


async def test_un_elemento_sin_ningun_pedido_no_se_consulta(sesion, limpio) -> None:
    await _elemento(sesion, "MRSU8507472", ultima=None)

    plan = await planificar_en(sesion)

    assert plan.motivos_omitidos() == {planificador.OMITIDO_SIN_PEDIDOS: 1}


async def test_basta_un_pedido_vivo_para_seguir_consultando(sesion, limpio) -> None:
    """Un contenedor ampara varias líneas: una cerrada no apaga a las demás."""
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    await _pedido(
        sesion,
        elemento,
        "4599000001",
        estado_calculado="CERRADO",
        motivo_cierre="CIERRE_FORZADO",
    )
    await _pedido(sesion, elemento, "4599000002")

    plan = await planificar_en(sesion)

    assert plan.total == 1


async def test_el_ais_no_se_planifica(sesion, limpio) -> None:
    """`US-02` es una suscripción persistente por WebSocket, no un sondeo.

    Un MMSI no tiene intervalo que configurar: su bucle vive en `colector_ais`.
    """
    assert "MARITIMO" in planificador.VIAS_SONDEADAS
    elemento = ElementoRastreado(
        tipo_tracking_externo="MMSI", tracking_externo="311001711", via_transporte="MARITIMO"
    )
    sesion.add(elemento)
    await sesion.flush()
    await _pedido(sesion, elemento, "4599000001")

    plan = await planificar_en(sesion)

    # Sí aparece: la vía es marítima. Lo que no se planifica es el *transporte*
    # AIS, y eso lo decide quien ejecuta el plan según el tipo de referencia.
    assert plan.total == 1


# --- Lo que sí cuesta dinero: las altas ------------------------------------


@pytest.fixture
async def usuario(sesion) -> Usuario:
    existente = await sesion.scalar(select(Usuario).limit(1))
    if existente is None:
        existente = Usuario(
            usuario="tester-pla",
            nombre_completo="Tester Planificador",
            correo="tester-pla@example.com",
            hash_contrasena="x",
            rol="LOGISTICA",
        )
        sesion.add(existente)
        await sesion.flush()
    return existente


async def _alta_auditada(sesion, pedido, usuario, instante: dt.datetime) -> None:
    sesion.add(
        AuditoriaIntervencion(
            id_pedido=pedido.id,
            id_usuario=usuario.id,
            fecha_hora=instante,
            tipo_intervencion=TIPO_INTERVENCION,
            campo_afectado="shipsgo_id_embarque",
            valor_nuevo="1",
            motivo="Alta de prueba",
        )
    )
    await sesion.flush()


async def test_las_altas_se_cuentan_desde_la_auditoria(sesion, limpio, usuario) -> None:
    """Y no desde un contador en memoria: el gasto tiene que sobrevivir a un
    reinicio, porque es dinero."""
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    pedido = await _pedido(sesion, elemento, "4599000001")
    for _ in range(3):
        await _alta_auditada(sesion, pedido, usuario, MEDIODIA)

    assert await planificador.altas_del_dia(sesion, MEDIODIA) == 3


async def test_las_altas_de_ayer_no_cuentan_hoy(sesion, limpio, usuario) -> None:
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    pedido = await _pedido(sesion, elemento, "4599000001")
    await _alta_auditada(sesion, pedido, usuario, MEDIODIA - dt.timedelta(days=1))

    assert await planificador.altas_del_dia(sesion, MEDIODIA) == 0


async def test_pasar_del_umbral_avisa(sesion, limpio, usuario, caplog) -> None:
    """Veinte altas en un día son señal de que algo se registra en bucle."""
    import logging

    await _fijar(sesion, planificador.CLAVE_ALTAS_MAXIMAS, "2")
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    pedido = await _pedido(sesion, elemento, "4599000001")
    for _ in range(3):
        await _alta_auditada(sesion, pedido, usuario, MEDIODIA)

    with caplog.at_level(logging.WARNING):
        altas, excedido = await planificador.revisar_consumo(sesion, MEDIODIA)

    assert (altas, excedido) == (3, True)
    assert "altas hoy" in caplog.text
    assert "USD" in caplog.text


async def test_por_debajo_del_umbral_no_avisa(sesion, limpio, usuario, caplog) -> None:
    import logging

    await _fijar(sesion, planificador.CLAVE_ALTAS_MAXIMAS, "20")
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    pedido = await _pedido(sesion, elemento, "4599000001")
    await _alta_auditada(sesion, pedido, usuario, MEDIODIA)

    with caplog.at_level(logging.WARNING):
        altas, excedido = await planificador.revisar_consumo(sesion, MEDIODIA)

    assert (altas, excedido) == (1, False)
    assert "altas hoy" not in caplog.text


# --- Invariantes -----------------------------------------------------------


def test_los_parametros_del_planificador_estan_declarados() -> None:
    """Leer una clave sin declarar lanza `KeyError` en producción."""
    for clave in (
        planificador.CLAVE_FRECUENCIA_AEREA,
        planificador.CLAVE_FRECUENCIA_MARITIMA,
        planificador.CLAVE_VENTANA_INICIO,
        planificador.CLAVE_VENTANA_FIN,
        planificador.CLAVE_MADURACION,
        planificador.CLAVE_ALTAS_MAXIMAS,
    ):
        assert clave in parametros.CATALOGO


async def test_sin_filas_en_la_tabla_se_usan_los_defectos(sesion, limpio) -> None:
    """El planificador funciona con `parametros_sistema` vacía (`US-17`)."""
    for clave in (
        planificador.CLAVE_FRECUENCIA_AEREA,
        planificador.CLAVE_FRECUENCIA_MARITIMA,
        planificador.CLAVE_VENTANA_INICIO,
        planificador.CLAVE_VENTANA_FIN,
        planificador.CLAVE_MADURACION,
        planificador.CLAVE_ALTAS_MAXIMAS,
    ):
        await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    await sesion.flush()

    politica = await planificador.politica_vigente(sesion)

    assert politica.frecuencia_aerea_min == parametros.CATALOGO["frecuencia_aerea_min"].defecto
    assert politica.ventana_inicio_h == parametros.CATALOGO["ventana_aerea_inicio_h"].defecto


async def test_el_resumen_se_lee_solo(sesion, limpio) -> None:
    elemento = await _elemento(sesion, "MRSU8507472", ultima=None)
    await _pedido(sesion, elemento, "4599000001")
    await _elemento(sesion, "MRSU8132490", ultima=None, activo=False)

    resumen = (await planificar_en(sesion)).resumen()

    assert "1 a consultar" in resumen
    assert planificador.OMITIDO_INACTIVO in resumen
