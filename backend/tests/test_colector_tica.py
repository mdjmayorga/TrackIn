"""Pruebas de `app.services.rastreo.colector_tica` — `US-49`.

Contra la base y con las **respuestas reales de TICA** del 28/09/2026: lo que
se verifica es que la llegada de la aduana termina donde `arribo.evaluar` la
busca, y que una guía que todavía no aparece no se toma como fallo.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services import arribo
from app.services.rastreo import colector_tica
from app.services.rastreo.shipsgo_aerolineas import Aerolinea, CatalogoAerolineas
from app.services.rastreo.tica_cliente import ClienteTICA, Respuesta

_SALIDA = Path(__file__).resolve().parents[1] / "scripts/spikes/tica/output"
_BUSQUEDA = _SALIDA / "02_busqueda_hawb.html"
_MADRE = _SALIDA / "03_guia_madre.html"
_VACIA = _SALIDA / "04_busqueda_vacia.html"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (_BUSQUEDA.exists() and _MADRE.exists() and _VACIA.exists()),
        reason="faltan las respuestas grabadas del spike de TICA",
    ),
]

#: El día en que se midió: la guía había llegado diez días antes.
INSTANTE = dt.datetime(2026, 9, 28, 18, 0, tzinfo=dt.UTC)


class TransporteGrabado:
    def __init__(self, resultado: Path) -> None:
        self.resultado = resultado

    async def __call__(
        self, metodo: str, url: str, *, datos: dict[str, str] | None = None
    ) -> Respuesta:
        if "hcgconspadre" in url:
            return Respuesta(200, _MADRE.read_text(encoding="utf-8"))
        if metodo == "POST":
            return Respuesta(200, self.resultado.read_text(encoding="utf-8"))
        return Respuesta(200, _VACIA.read_text(encoding="utf-8"))


def _cliente(resultado: Path = _BUSQUEDA) -> ClienteTICA:
    return ClienteTICA(TransporteGrabado(resultado), pausa_s=0)


@pytest.fixture
async def guia(sesion) -> ElementoRastreado:
    """La guía hija real de la OC 4500018603-10, con un pedido aéreo de prueba."""
    elemento = ElementoRastreado(
        tipo_tracking_externo="HAWB", tracking_externo="ZIVHYD017", via_transporte="AEREO"
    )
    sesion.add(elemento)
    destino = await sesion.scalar(
        select(MaestroDestino).where(
            MaestroDestino.via_transporte == "AEREO", MaestroDestino.activo.is_(True)
        )
    )
    assert destino is not None
    proveedor = Proveedor(codigo="P-TICA-1", nombre="Proveedor de la India")
    material = Material(codigo="M-TICA-1", descripcion="Fluoxetina", unidad_medida="KG")
    sesion.add_all([proveedor, material])
    await sesion.flush()
    sesion.add(
        PedidoTransito(
            # Una OC que no existe: la base de desarrollo puede tener cargado el
            # Z-tracking real, donde la 4500018603-10 sí está.
            oc_numero="4599918603",
            posicion_oc=10,
            tracking_interno="TRK-4599918603-010",
            id_proveedor=proveedor.id,
            id_material=material.id,
            id_destino=destino.id,
            via_transporte="AEREO",
            cantidad_pedida=Decimal("1.000"),
            unidad_medida="KG",
            fecha_entrega_pedido=dt.date(2026, 10, 30),
            lead_time_destino_dias=destino.lead_time_dias,
            etapa_viaje="EN_TRANSITO",
            estado_calculado="EN_TRANSITO",
            id_elemento_rastreado=elemento.id,
        )
    )
    await sesion.flush()
    return elemento


async def test_la_llegada_de_la_aduana_queda_como_ata_de_la_fuente(sesion, guia) -> None:
    resultado = await colector_tica.procesar(sesion, guia, _cliente(), instante=INSTANTE)
    await sesion.flush()

    assert resultado.aplicada
    # Medianoche del 18/09 en Costa Rica, que es UTC-6 todo el año.
    assert guia.ata_api == dt.datetime(2026, 9, 18, 6, 0, tzinfo=dt.UTC)
    assert guia.manifiesto_aduana == "26017849"


async def test_guarda_la_guia_madre_y_su_aerolinea(sesion, guia) -> None:
    await colector_tica.procesar(sesion, guia, _cliente(), instante=INSTANTE)

    assert guia.guia_madre == "57434927513"
    assert guia.nombre == "TACA INTERNATIONAL AIRLINES S A"


async def test_guarda_el_payload_de_la_aduana(sesion, guia) -> None:
    """RNF-13: `historial_tracking` exige coordenadas y TICA no las da."""
    await colector_tica.procesar(sesion, guia, _cliente(), instante=INSTANTE)
    await sesion.flush()
    await sesion.refresh(guia)

    assert guia.payload_aduana is not None
    assert guia.payload_aduana["fuente"] == "tica"
    assert guia.payload_aduana["madre"]["numero"] == "57434927513"


async def test_arribo_mueve_el_pedido_a_destino_con_la_llegada_de_la_aduana(sesion, guia) -> None:
    """La cadena completa: TICA → `ata_api` → `arribo.evaluar` → `EN_DESTINO`."""
    await colector_tica.procesar(sesion, guia, _cliente(), instante=INSTANTE)
    await sesion.flush()
    pedido = await sesion.scalar(
        select(PedidoTransito).where(PedidoTransito.id_elemento_rastreado == guia.id)
    )

    llegada = await arribo.evaluar(sesion, pedido, INSTANTE)

    assert llegada.arribado
    assert llegada.origen == arribo.ORIGEN_FUENTE  # un documento oficial, no una deducción
    assert not llegada.inferido
    assert pedido.etapa_viaje == "EN_DESTINO"
    assert not guia.activo  # decisión B7: ya no hay nada que seguir


async def test_antes_del_arribo_no_aparecer_no_es_un_fallo(sesion, guia) -> None:
    resultado = await colector_tica.procesar(sesion, guia, _cliente(_VACIA), instante=INSTANTE)

    assert not resultado.aplicada
    assert resultado.motivo == colector_tica.DESCARTE_SIN_MANIFIESTO
    assert guia.ata_api is None
    # Se anota la consulta para que el planificador espere su intervalo.
    assert guia.ultima_actualizacion_api == INSTANTE


async def test_una_guia_que_no_es_hija_no_se_consulta(sesion) -> None:
    mawb = ElementoRastreado(
        tipo_tracking_externo="MAWB", tracking_externo="020-12345675", via_transporte="AEREO"
    )
    sesion.add(mawb)
    await sesion.flush()

    resultado = await colector_tica.procesar(sesion, mawb, _cliente(), instante=INSTANTE)

    assert resultado.motivo == colector_tica.DESCARTE_NO_ES_HIJA
    assert mawb.ultima_actualizacion_api is None


@pytest.mark.parametrize(("activa", "esperado"), [(True, True), (False, False)])
async def test_senala_si_la_madre_se_podria_seguir_en_shipsgo(
    sesion, guia, activa: bool, esperado: bool
) -> None:
    """Solo informa: dar de alta cuesta un crédito y lo decide una persona.
    La madre real, `574`, es de Allied Air, inactiva en ShipsGo."""
    catalogo = CatalogoAerolineas([Aerolinea("4W", "ALLIED AIR", ("574",), activa=activa)])

    resultado = await colector_tica.procesar(
        sesion, guia, _cliente(), catalogo=catalogo, instante=INSTANTE
    )

    assert resultado.madre_rastreable_shipsgo is esperado


def test_la_fecha_del_manifiesto_es_medianoche_en_costa_rica() -> None:
    instante = colector_tica.llegada_a_instante(dt.date(2026, 9, 18))
    assert instante.astimezone(colector_tica.ZONA_CR).date() == dt.date(2026, 9, 18)
    assert instante.astimezone(colector_tica.ZONA_CR).hour == 0
