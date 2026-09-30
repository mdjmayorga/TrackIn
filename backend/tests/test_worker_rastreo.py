"""Pruebas del ciclo periódico de rastreo — `US-50`.

Contra la base y con **respuestas reales grabadas** de TICA (28/09/2026) y de
ShipsGo (`TASK-28`), servidas por clientes falsos: sin red y sin créditos.

Cada `commit` del worker cae en un *savepoint* de la transacción de la prueba,
así que todo se deshace al terminar, igual que en el resto de la suite.
"""

from __future__ import annotations

import datetime as dt
import json
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, select, update

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services import salud_fuentes
from app.services.rastreo.shipsgo_cliente import ErrorShipsGo
from app.services.rastreo.tica_cliente import ClienteTICA, Respuesta
from app.services.recalculo import CLAVE_UMBRAL
from app.workers import rastreo
from conftest import vaciar_auditoria

_TICA = Path(__file__).resolve().parents[1] / "scripts/spikes/tica/output"
_SHIPSGO = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
_PAYLOADS = _SHIPSGO / "06_payload_personal.json"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not ((_TICA / "02_busqueda_hawb.html").exists() and _PAYLOADS.exists()),
        reason="faltan las respuestas grabadas de TICA o de ShipsGo",
    ),
]

#: Mediodía UTC: dentro de la ventana aérea por defecto (6 a 22 h).
MEDIODIA = dt.datetime(2026, 9, 28, 12, 0, tzinfo=dt.UTC)
CONTENEDOR = "MRSU8507472"
ID_CONTENEDOR = 6734886


# --- Dobles -----------------------------------------------------------------


class TransporteTICA:
    """Sirve las páginas grabadas. `estado` simula un bloqueo o una caída."""

    def __init__(self, resultado: str = "02_busqueda_hawb.html", estado: int = 200) -> None:
        self.resultado = resultado
        self.estado = estado
        self.peticiones = 0

    async def __call__(
        self, metodo: str, url: str, *, datos: dict[str, str] | None = None
    ) -> Respuesta:
        self.peticiones += 1
        if self.estado != 200:
            return Respuesta(self.estado, "<html>Access Denied</html>")
        if "hcgconspadre" in url:
            archivo = "03_guia_madre.html"
        elif metodo == "POST":
            archivo = self.resultado
        else:
            archivo = "04_busqueda_vacia.html"
        return Respuesta(200, (_TICA / archivo).read_text(encoding="utf-8"))


class ShipsGoFalso:
    """Lista la cuenta y devuelve el embarque grabado del contenedor Maersk."""

    def __init__(self, registrados: list[dict[str, Any]] | None = None) -> None:
        datos = json.loads(_PAYLOADS.read_text(encoding="utf-8"))
        embarque = next(e for e in datos["embarques"] if e["contenedor"] == CONTENEDOR)
        self.shipment = embarque["payload_shipment"]
        self.geojson = embarque["payload_geojson"]
        self.registrados = (
            registrados
            if registrados is not None
            else [{"id": ID_CONTENEDOR, "container_number": CONTENEDOR}]
        )
        self.lecturas: list[int] = []
        self.error_al_leer: ErrorShipsGo | None = None

    async def consultar(self, ruta: str) -> dict[str, Any]:
        if ruta.startswith("/air"):
            return {"shipments": [], "meta": {"more": False}}
        return {"shipments": self.registrados, "meta": {"more": False}}

    async def leer(self, id_embarque: int, aereo: bool = False) -> dict[str, Any]:
        self.lecturas.append(id_embarque)
        if self.error_al_leer is not None:
            raise self.error_al_leer
        return self.shipment

    async def leer_geojson(self, id_embarque: int, aereo: bool = False) -> dict[str, Any] | None:
        return self.geojson


def _tica(transporte: TransporteTICA | None = None) -> ClienteTICA:
    return ClienteTICA(transporte or TransporteTICA(), pausa_s=0)


class _SesionPrestada:
    """La sesión de la prueba, con `commit`/`rollback` sobre un *savepoint*."""

    def __init__(self, sesion, punto) -> None:
        self._sesion = sesion
        self._punto = punto

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        await self._punto.commit()

    async def rollback(self) -> None:
        await self._punto.rollback()


@pytest.fixture
def fabrica(sesion):
    @asynccontextmanager
    async def _fabrica():
        punto = await sesion.begin_nested()
        try:
            yield _SesionPrestada(sesion, punto)
        finally:
            if punto.is_active:
                await punto.commit()

    return _fabrica


@pytest.fixture(autouse=True)
def salud_limpia():
    """El registro de salud vive en memoria y es global al proceso."""
    salud_fuentes.registro.olvidar_todo()
    yield
    salud_fuentes.registro.olvidar_todo()


@pytest.fixture
async def limpio(sesion):
    await vaciar_auditoria(sesion)
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    await sesion.flush()
    return sesion


async def _seguido(
    sesion, tipo: str, numero: str, via: str, oc: str, **pedido: Any
) -> tuple[ElementoRastreado, PedidoTransito]:
    """Un elemento rastreado con un pedido activo que viaja en él."""
    elemento = ElementoRastreado(
        tipo_tracking_externo=tipo, tracking_externo=numero, via_transporte=via
    )
    sesion.add(elemento)
    destino = await sesion.scalar(
        select(MaestroDestino).where(
            MaestroDestino.via_transporte == via, MaestroDestino.activo.is_(True)
        )
    )
    assert destino is not None
    proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-WRK-1"))
    if proveedor is None:
        proveedor = Proveedor(codigo="P-WRK-1", nombre="Proveedor")
        sesion.add(proveedor)
    material = await sesion.scalar(select(Material).where(Material.codigo == "M-WRK-1"))
    if material is None:
        material = Material(codigo="M-WRK-1", descripcion="Material", unidad_medida="KG")
        sesion.add(material)
    await sesion.flush()
    datos = {
        "oc_numero": oc,
        "posicion_oc": 10,
        "tracking_interno": f"TRK-{oc}-010",
        "id_proveedor": proveedor.id,
        "id_material": material.id,
        "id_destino": destino.id,
        "via_transporte": via,
        "cantidad_pedida": Decimal("1.000"),
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 10, 30),
        "lead_time_destino_dias": destino.lead_time_dias,
        "etapa_viaje": "EN_TRANSITO",
        "estado_calculado": "EN_TRANSITO",
        "id_elemento_rastreado": elemento.id,
    }
    datos.update(pedido)
    registro = PedidoTransito(**datos)
    sesion.add(registro)
    await sesion.flush()
    return elemento, registro


# --- TICA: la guía hija de punta a punta ------------------------------------


async def test_una_guia_hija_llega_sola_a_destino(sesion, limpio, fabrica) -> None:
    """El ciclo completo sin intervención: TICA → arribo → fecha proyectada."""
    elemento, pedido = await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900001")

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(tica=_tica()), instante=MEDIODIA
    )

    assert resumen.consultados == {"tica": 1}
    assert resumen.aplicados == 1
    assert resumen.arribos == 1
    assert elemento.guia_madre == "57434927513"
    assert pedido.etapa_viaje == "EN_DESTINO"
    assert pedido.estado_calculado == "EN_DESTINO"
    assert pedido.fecha_proyectada_disponible == dt.date(2026, 9, 18) + dt.timedelta(
        days=pedido.lead_time_destino_dias
    )


async def test_una_guia_que_no_aparece_espera_su_intervalo(sesion, limpio, fabrica) -> None:
    """Antes del arribo: se consulta, no se aplica, y el siguiente ciclo no insiste."""
    elemento, pedido = await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900002")
    transporte = TransporteTICA(resultado="04_busqueda_vacia.html")
    fuentes = rastreo.Fuentes(tica=_tica(transporte))
    estado = rastreo.EstadoWorker()

    primero = await rastreo.ejecutar_ciclo(fabrica, fuentes, estado, MEDIODIA)
    segundo = await rastreo.ejecutar_ciclo(
        fabrica, fuentes, estado, MEDIODIA + dt.timedelta(minutes=5)
    )

    assert primero.consultados == {"tica": 1} and primero.aplicados == 0
    assert pedido.etapa_viaje == "EN_TRANSITO"
    assert segundo.consultados == {}
    assert segundo.omitidos.get("intervalo_sin_vencer") == 1
    assert transporte.peticiones == 2  # formulario y búsqueda, una sola vez


async def test_un_bloqueo_de_tica_la_apaga_y_no_insiste(sesion, limpio, fabrica) -> None:
    """Akamai responde 403: una petición, la fuente degradada, y ni una más."""
    await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900003")
    await _seguido(sesion, "HAWB", "ABCD12345", "AEREO", "4599900004")
    transporte = TransporteTICA(estado=403)
    fuentes = rastreo.Fuentes(tica=_tica(transporte))
    estado = rastreo.EstadoWorker()

    primero = await rastreo.ejecutar_ciclo(fabrica, fuentes, estado, MEDIODIA)
    segundo = await rastreo.ejecutar_ciclo(
        fabrica, fuentes, estado, MEDIODIA + dt.timedelta(hours=7)
    )

    assert primero.errores == {"tica": "acceso_bloqueado"}
    assert primero.omitidos.get(rastreo.OMITIDO_FUENTE_DEGRADADA) == 1
    assert segundo.omitidos.get(rastreo.OMITIDO_FUENTE_DEGRADADA) == 2
    assert transporte.peticiones == 1


async def test_una_caida_transitoria_espera_antes_de_reintentar(sesion, limpio, fabrica) -> None:
    await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900005")
    transporte = TransporteTICA(estado=503)
    fuentes = rastreo.Fuentes(tica=_tica(transporte))
    estado = rastreo.EstadoWorker()

    primero = await rastreo.ejecutar_ciclo(fabrica, fuentes, estado, MEDIODIA)

    assert primero.errores == {"tica": "error_del_servidor"}
    assert "tica" in estado.en_espera_hasta
    # El elemento no quedó marcado como consultado (se revirtió): el siguiente
    # ciclo lo intentaría, pero la fuente está en espera.
    segundo = await rastreo.ejecutar_ciclo(fabrica, fuentes, estado, MEDIODIA)
    assert segundo.omitidos.get(rastreo.OMITIDO_FUENTE_EN_ESPERA) == 1
    assert transporte.peticiones == 1


async def test_la_caida_de_tica_no_detiene_a_shipsgo(sesion, limpio, fabrica) -> None:
    await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900006")
    await _seguido(sesion, "CONTENEDOR", CONTENEDOR, "MARITIMO", "4599900007")
    fuentes = rastreo.Fuentes(shipsgo=ShipsGoFalso(), tica=_tica(TransporteTICA(estado=403)))

    resumen = await rastreo.ejecutar_ciclo(fabrica, fuentes, instante=MEDIODIA)

    assert resumen.errores == {"tica": "acceso_bloqueado"}
    assert resumen.consultados.get("shipsgo") == 1
    assert resumen.aplicados == 1


# --- ShipsGo: solo lo que ya está pagado ------------------------------------


async def test_lee_el_embarque_registrado_y_recalcula(sesion, limpio, fabrica) -> None:
    elemento, pedido = await _seguido(sesion, "CONTENEDOR", CONTENEDOR, "MARITIMO", "4599900008")
    shipsgo = ShipsGoFalso()

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(shipsgo=shipsgo), instante=MEDIODIA
    )

    assert shipsgo.lecturas == [ID_CONTENEDOR]
    assert resumen.aplicados == 1 and resumen.recalculados == 1
    assert elemento.eta_api is not None
    assert pedido.fecha_proyectada_disponible is not None


async def test_sin_alta_no_se_gasta_nada(sesion, limpio, fabrica) -> None:
    """Dar de alta cuesta ~2 USD y lo decide una persona, no el ciclo."""
    await _seguido(sesion, "CONTENEDOR", "MSCU1234566", "MARITIMO", "4599900009")
    shipsgo = ShipsGoFalso()

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(shipsgo=shipsgo), instante=MEDIODIA
    )

    assert resumen.omitidos.get(rastreo.OMITIDO_SIN_ALTA) == 1
    assert shipsgo.lecturas == []


async def test_un_404_de_un_embarque_no_apaga_shipsgo(sesion, limpio, fabrica) -> None:
    """Un embarque que desapareció de la cuenta es problema suyo, no de la fuente."""
    await _seguido(sesion, "CONTENEDOR", CONTENEDOR, "MARITIMO", "4599900010")
    shipsgo = ShipsGoFalso()
    shipsgo.error_al_leer = ErrorShipsGo("embarque_no_registrado", "404")

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(shipsgo=shipsgo), instante=MEDIODIA
    )

    assert resumen.omitidos.get(rastreo.OMITIDO_SIN_ALTA) == 1
    assert salud_fuentes.registro.estado("shipsgo").debe_reintentar


async def test_el_indice_pagina_y_compara_sin_guiones() -> None:
    class Paginado:
        async def consultar(self, ruta: str) -> dict[str, Any]:
            if ruta == "/ocean/shipments?skip=0":
                return {
                    "shipments": [{"id": 1, "container_number": "MSCU1234566"}],
                    "meta": {"more": True},
                }
            if ruta == "/ocean/shipments?skip=1":
                return {
                    "shipments": [{"id": 2, "booking_number": "COSU6508789000"}],
                    "meta": {"more": False},
                }
            return {"shipments": [{"id": 3, "awb_number": "02012345675"}], "meta": {"more": False}}

    indice = await rastreo.indice_shipsgo(Paginado())  # type: ignore[arg-type]

    assert indice["MSCU1234566"] == (1, False)
    assert indice["COSU6508789000"] == (2, False)
    assert indice["02012345675"] == (3, True)


# --- Lo que el ciclo no consulta --------------------------------------------


async def test_sin_cliente_configurado_se_omite_con_su_motivo(sesion, limpio, fabrica) -> None:
    await _seguido(sesion, "CONTENEDOR", CONTENEDOR, "MARITIMO", "4599900011")

    resumen = await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), instante=MEDIODIA)

    assert resumen.omitidos.get(rastreo.OMITIDO_SIN_CLIENTE) == 1


async def test_un_mmsi_no_se_sondea(sesion, limpio, fabrica) -> None:
    """AIS es una suscripción, no un sondeo: no le toca a este ciclo."""
    await _seguido(sesion, "MMSI", "123456789", "MARITIMO", "4599900012")

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(shipsgo=ShipsGoFalso()), instante=MEDIODIA
    )

    assert resumen.omitidos.get(rastreo.OMITIDO_SIN_FUENTE) == 1


async def test_un_elemento_que_revienta_no_detiene_a_los_demas(
    sesion, limpio, fabrica, monkeypatch
) -> None:
    """RNF-14: un dato raro en un elemento no tumba el ciclo."""
    await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900013")
    await _seguido(sesion, "HAWB", "ROMPE0001", "AEREO", "4599900014")
    original = rastreo._consultar_tica

    async def consultar(sesion, elemento, fuentes, ahora):
        if elemento.tracking_externo == "ROMPE0001":
            raise ValueError("dato raro")
        return await original(sesion, elemento, fuentes, ahora)

    monkeypatch.setattr(rastreo, "_consultar_tica", consultar)

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(tica=_tica()), instante=MEDIODIA
    )

    assert resumen.errores == {"elemento:ROMPE0001": "error_inesperado"}
    assert resumen.aplicados == 1


# --- El bucle ---------------------------------------------------------------


async def test_el_bucle_sobrevive_a_un_ciclo_que_falla_entero(sesion, limpio, fabrica) -> None:
    """Si la base se cae en un ciclo, el worker espera y sigue."""
    llamadas = {"n": 0}

    @asynccontextmanager
    async def fabrica_que_falla_una_vez():
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise ConnectionError("la base no responde")
        async with fabrica() as sesion_prestada:
            yield sesion_prestada

    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)

    resumenes = await rastreo.ejecutar(
        fabrica_que_falla_una_vez, rastreo.Fuentes(), intervalo_s=30, ciclos=2, dormir=dormir
    )

    assert len(resumenes) == 1  # el primero falló, el segundo corrió
    assert esperas == [30]  # entre ciclos, no después del último


# --- La salud se publica para la API (`US-51`) ------------------------------


async def test_el_ciclo_publica_la_salud_de_las_fuentes(sesion, limpio, fabrica) -> None:
    """`/health` lo sirve otro proceso: lo que el worker sabe tiene que quedar
    en `salud_fuentes`, incluido un bloqueo de TICA."""
    from app.models.salud_fuente import SaludFuente

    await sesion.execute(delete(SaludFuente))
    await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900015")
    await _seguido(sesion, "CONTENEDOR", CONTENEDOR, "MARITIMO", "4599900016")
    fuentes = rastreo.Fuentes(shipsgo=ShipsGoFalso(), tica=_tica(TransporteTICA(estado=403)))

    await rastreo.ejecutar_ciclo(fabrica, fuentes, instante=MEDIODIA)

    filas = {f.nombre: f for f in await sesion.scalars(select(SaludFuente))}
    assert filas["tica"].degradada is True
    assert filas["tica"].motivo_ultimo_fallo == "acceso_bloqueado"
    assert filas["shipsgo"].degradada is False
    assert filas["shipsgo"].ultimo_contacto_ok == MEDIODIA
    assert filas["tica"].reportado_en == MEDIODIA


async def test_si_publicar_la_salud_falla_el_ciclo_sigue(
    sesion, limpio, fabrica, monkeypatch
) -> None:
    """Es informativo: perder una foto no justifica perder las lecturas."""
    await _seguido(sesion, "HAWB", "ZIVHYD017", "AEREO", "4599900017")

    async def falla(*_args, **_kwargs):
        raise RuntimeError("tabla ausente")

    monkeypatch.setattr(salud_fuentes, "guardar", falla)

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(tica=_tica()), instante=MEDIODIA
    )

    assert resumen.aplicados == 1


# --- US-12: un pedido que falla no se lleva a los demás ---------------------


async def test_un_pedido_que_falla_no_revierte_la_lectura_ni_a_sus_vecinos(
    sesion, limpio, fabrica, monkeypatch
) -> None:
    """RNF-14 por pedido: dos líneas en el mismo contenedor, una rompe un CHECK.

    Antes de `US-12` el error revertía el elemento entero: la ETA recién leída
    de ShipsGo y el recálculo de la otra línea se perdían con él.
    """
    elemento, sano = await _seguido(sesion, "CONTENEDOR", CONTENEDOR, "MARITIMO", "4599900020")
    roto = PedidoTransito(
        **{
            columna: getattr(sano, columna)
            for columna in (
                "id_proveedor",
                "id_material",
                "id_destino",
                "via_transporte",
                "cantidad_pedida",
                "unidad_medida",
                "fecha_entrega_pedido",
                "lead_time_destino_dias",
                "etapa_viaje",
                "estado_calculado",
                "id_elemento_rastreado",
            )
        },
        oc_numero="4599900021",
        posicion_oc=10,
        tracking_interno="TRK-4599900021-010",
    )
    sesion.add(roto)
    await sesion.flush()
    original = rastreo.recalculo.recalcular

    async def recalcular(sesion, pedido, **kwargs):
        resultado = await original(sesion, pedido, **kwargs)
        if pedido.oc_numero == "4599900021":
            pedido.estado_calculado = "NO_EXISTE"  # lo rechaza ck_..._estado_calculado
        return resultado

    monkeypatch.setattr(rastreo.recalculo, "recalcular", recalcular)

    resumen = await rastreo.ejecutar_ciclo(
        fabrica, rastreo.Fuentes(shipsgo=ShipsGoFalso()), instante=MEDIODIA
    )

    assert resumen.aplicados == 1
    assert resumen.recalculados == 1
    assert resumen.errores == {"pedido:TRK-4599900021-010": "error_de_recalculo"}
    await sesion.refresh(elemento)
    await sesion.refresh(sano)
    await sesion.refresh(roto)
    assert elemento.eta_api is not None
    assert sano.fecha_proyectada_disponible is not None
    assert roto.estado_calculado == "EN_TRANSITO"
    assert roto.fecha_proyectada_disponible is None


# --- US-17: un parámetro o un lead time editados en la base -----------------


async def _umbral(sesion, dias: int) -> None:
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == CLAVE_UMBRAL))
    sesion.add(
        ParametroSistema(
            clave=CLAVE_UMBRAL, valor=str(dias), tipo_dato="ENTERO", descripcion="Umbral de prueba"
        )
    )
    await sesion.flush()


async def _sin_rastreo(sesion) -> PedidoTransito:
    """Un pedido del archivo, sin elemento: ninguna lectura lo va a tocar.

    Tres días de margen entre la fecha proyectada y la comprometida.
    """
    _, plantilla = await _seguido(sesion, "HAWB", "PLANTILLA1", "AEREO", "4599900030")
    destino = await sesion.get(MaestroDestino, plantilla.id_destino)
    assert destino is not None
    await sesion.delete(plantilla)
    await sesion.flush()
    eta = dt.date(2026, 10, 10)
    pedido = PedidoTransito(
        oc_numero="4599900031",
        posicion_oc=10,
        tracking_interno="TRK-4599900031-010",
        id_proveedor=plantilla.id_proveedor,
        id_material=plantilla.id_material,
        id_destino=destino.id,
        via_transporte="AEREO",
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        eta_declarada=eta,
        fecha_entrega_pedido=eta + dt.timedelta(days=destino.lead_time_dias + 3),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        estado_calculado="SIN_TRACKING",
    )
    sesion.add(pedido)
    await sesion.flush()
    return pedido


async def test_al_arrancar_se_recalcula_todo(sesion, limpio, fabrica) -> None:
    """Lo que cambió con el worker apagado —una migración— se pone al día."""
    await _umbral(sesion, 2)
    pedido = await _sin_rastreo(sesion)

    resumen = await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), instante=MEDIODIA)

    assert resumen.recalculo_global is not None
    assert resumen.recalculo_global.startswith("arranque")
    assert pedido.fecha_proyectada_disponible is not None
    assert pedido.estado_cumplimiento == "A_TIEMPO"


async def test_sin_cambios_no_se_vuelve_a_barrer(sesion, limpio, fabrica) -> None:
    await _sin_rastreo(sesion)
    estado = rastreo.EstadoWorker()
    await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)

    segundo = await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)

    assert segundo.recalculo_global is None


async def test_cambiar_el_umbral_en_la_tabla_se_aplica_al_siguiente_ciclo(
    sesion, limpio, fabrica
) -> None:
    """Segundo criterio de `US-17`, con un pedido que ninguna lectura toca."""
    await _umbral(sesion, 2)
    pedido = await _sin_rastreo(sesion)
    estado = rastreo.EstadoWorker()
    await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)
    assert pedido.estado_cumplimiento == "A_TIEMPO"

    await _umbral(sesion, 5)  # tres días de margen ya no alcanzan
    resumen = await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)

    assert resumen.recalculo_global is not None
    assert resumen.recalculo_global.startswith("cambió")
    assert pedido.estado_cumplimiento == "EN_RIESGO"


async def test_un_lead_time_editado_a_mano_tambien_se_detecta(sesion, limpio, fabrica) -> None:
    """El caso de las migraciones `0009` y `0010`: nadie pasó por `cambiar_lead_time`."""
    pedido = await _sin_rastreo(sesion)
    estado = rastreo.EstadoWorker()
    await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)
    antes = pedido.fecha_proyectada_disponible
    assert antes is not None

    await sesion.execute(
        update(MaestroDestino)
        .where(MaestroDestino.id == pedido.id_destino)
        .values(lead_time_dias=MaestroDestino.lead_time_dias + 4)
    )
    sesion.expire_all()
    await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)

    await sesion.refresh(pedido)
    assert pedido.fecha_proyectada_disponible == antes + dt.timedelta(days=4)


async def test_si_el_recalculo_global_falla_se_reintenta(
    sesion, limpio, fabrica, monkeypatch
) -> None:
    async def rompe(sesion):
        raise RuntimeError("base rara")

    monkeypatch.setattr(rastreo.recalculo, "firma_del_calculo", rompe)
    estado = rastreo.EstadoWorker()

    resumen = await rastreo.ejecutar_ciclo(fabrica, rastreo.Fuentes(), estado, MEDIODIA)

    assert resumen.errores == {"recalculo_global": "error_inesperado"}
    assert estado.firma_calculo is None
