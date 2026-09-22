"""Pruebas de la vía aérea de ShipsGo — `US-46`.

Contra el **MAWB real grabado** por `TASK-28` el 14/09/2026: `020-50685434` de
Lufthansa Cargo, PEK → FRA → SJO, diez hitos IATA CIMP todos en `ACT`. Y contra
el **catálogo real** de 207 aerolíneas capturado en la fase 2.

Lo que se fija aquí es que la vía aérea comparte el intérprete con la marítima
sin que ninguna de las dos se contamine: mismos hitos, distintos códigos.

Sin base y sin red.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from app.services.rastreo.shipsgo import (
    ETAPA_POR_EVENTO_AEREO,
    EVENTOS_DE_ARRIBO_AEREO,
    VIA_AEREA,
    VIA_MARITIMA,
    Hito,
    es_arribo,
    interpretar,
)
from app.services.rastreo.shipsgo_aerolineas import (
    CatalogoAerolineas,
    cargar,
    prefijo_de,
)

_SALIDA = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
_PENDIENTES = _SALIDA / "07_pendientes_personal.json"
_AEROLINEAS = _SALIDA / "02b_shipsgo_airlines.json"

pytestmark = pytest.mark.skipif(
    not (_PENDIENTES.exists() and _AEROLINEAS.exists()),
    reason="faltan los payloads grabados del spike TASK-28",
)

MAWB = "020-50685434"


def _aereo() -> tuple[dict[str, Any], dict[str, Any] | None]:
    datos = json.loads(_PENDIENTES.read_text(encoding="utf-8"))
    embarque = next(e for e in datos["embarques"] if e["via"] == "air")
    return embarque["payload_shipment"], embarque.get("payload_geojson")


def _catalogo() -> CatalogoAerolineas:
    return CatalogoAerolineas.desde_payload(json.loads(_AEROLINEAS.read_text(encoding="utf-8")))


def _lectura():
    shipment, geojson = _aereo()
    return interpretar(shipment, geojson)


# --- La vía se deduce del payload ------------------------------------------


def test_un_awb_declara_la_via_aerea() -> None:
    """No hace falta decírselo: el payload aéreo trae `awb_number`."""
    assert _lectura().via == VIA_AEREA


def test_el_maritimo_sigue_siendo_maritimo() -> None:
    """La vía aérea no puede contaminar a la otra."""
    assert interpretar({"id": 1, "container_number": "X", "route": {}}).via == VIA_MARITIMA


# --- La ruta aérea usa otras claves ----------------------------------------


def test_el_destino_sale_del_codigo_iata() -> None:
    """Marítimo usa `code` (UN/LOCODE); aéreo, `iata`."""
    lectura = _lectura()

    assert lectura.puerto_destino == "SJO"
    assert lectura.puerto_destino_nombre is not None
    assert "Santamar" in lectura.puerto_destino_nombre


def test_la_eta_sale_de_date_of_rcf() -> None:
    """El equivalente aéreo de la descarga: recibido del vuelo en destino."""
    lectura = _lectura()

    assert lectura.eta is not None
    assert lectura.eta.date() == dt.date(2026, 9, 5)


def test_el_etd_sale_de_date_of_dep() -> None:
    """Lo que `US-43` necesita para la vista completa."""
    lectura = _lectura()

    assert lectura.etd is not None
    assert lectura.etd.date() == dt.date(2026, 9, 4)


def test_la_aerolinea_llega_con_nombre() -> None:
    assert _lectura().naviera == "LUFTHANSA CARGO"


# --- Los hitos IATA CIMP ---------------------------------------------------


def test_los_diez_hitos_cimp_se_leen() -> None:
    """Medido: 10 eventos, todos `ACT`."""
    lectura = _lectura()

    assert len(lectura.hitos) == 10
    assert all(h.ocurrido for h in lectura.hitos)
    assert {h.evento for h in lectura.hitos} == {"RCS", "DEP", "MAN", "ARR", "RCF", "DLV"}


def test_el_evento_manifestado_no_mueve_la_etapa() -> None:
    """`MAN` es documental, no un movimiento de la carga.

    Es el equivalente aéreo de `EMSH` y `GTIN` en marítimo.
    """
    assert "MAN" not in ETAPA_POR_EVENTO_AEREO
    assert "MAN" not in EVENTOS_DE_ARRIBO_AEREO


def test_la_entrega_al_agente_no_es_recepcion_en_planta() -> None:
    """`DLV` es `EN_DESTINO`, no `RECIBIDO_EN_PLANTA`.

    Que la aerolínea entregue la carga al agente en el aeropuerto no es que
    haya entrado a la planta de Gutis: eso lo registra una persona (`US-18`), y
    el paso a proceso aduanal es manual por decisión del 04/09.
    """
    lectura = _lectura()

    assert "DLV" in EVENTOS_DE_ARRIBO_AEREO
    assert lectura.estado_fuente == "DELIVERED"
    assert lectura.etapa == "EN_DESTINO"


def test_una_escala_no_da_por_llegado() -> None:
    """La misma trampa del transbordo marítimo, con otros códigos.

    Esta guía hizo `ARR` y `RCF` en Fráncfort sin haber llegado a San José.
    """
    lectura = _lectura()
    en_francfort = [h for h in lectura.hitos if h.puerto == "FRA" and es_arribo(h, VIA_AEREA)]

    assert len(en_francfort) >= 2, "hubo arribos intermedios de verdad"
    # Y aun así la ATA es la de San José, no la de Fráncfort.
    assert lectura.ata is not None
    llegada_sjo = next(h for h in lectura.hitos if h.puerto == "SJO" and h.evento == "ARR")
    assert lectura.ata == llegada_sjo.instante


def test_el_arribo_se_confirma_en_el_destino() -> None:
    assert _lectura().arribado is True


def test_los_codigos_maritimos_no_valen_en_aereo() -> None:
    """`ARRV` es marítimo; el aéreo usa `ARR`. Mezclarlos daría falsos arribos."""
    hito = Hito("ARRV", True, None, "SJO", None, None, None)

    assert es_arribo(hito, VIA_MARITIMA) is True
    assert es_arribo(hito, VIA_AEREA) is False


# --- La conexión es el transbordo aéreo ------------------------------------


def test_la_conexion_se_detecta_como_cambio_de_vuelo() -> None:
    """*«La conexión aparece como cambio de vuelo, igual que el transbordo
    marítimo aparece como cambio de nave. El mismo tratamiento sirve.»*
    """
    lectura = _lectura()

    assert [v.nombre for v in lectura.vehiculos] == ["LH8431", "LH518"]
    assert lectura.hay_transbordo is True


def test_un_vuelo_no_tiene_imo() -> None:
    """El IMO es de la OMI y solo aplica a naves."""
    assert all(v.imo is None for v in _lectura().vehiculos)


def test_el_vuelo_llega_como_cadena_y_no_como_objeto() -> None:
    """Marítimo entrega `{"name", "imo"}`; aéreo, `"LH8431"` a secas."""
    lectura = interpretar(
        {
            "awb_number": "020-50685434",
            "status": "IN_TRANSIT",
            "movements": [{"event": "DEP", "status": "ACT", "flight": "LH8431"}],
        }
    )

    assert lectura.vehiculos[0].nombre == "LH8431"


# --- El envío partido ------------------------------------------------------


def test_el_envio_medido_no_venia_partido() -> None:
    """Fija el hecho: `status_split: false`, `status_extended: {DELIVERED: 1}`."""
    assert _lectura().partes == {}


def test_un_envio_partido_refleja_la_parte_menos_avanzada() -> None:
    """Cuarto criterio de `US-46`.

    Decir que llegó cuando llegó la mitad es la clase de optimismo que hace
    que alguien planifique producción con material que no está.
    """
    lectura = interpretar(
        {
            "awb_number": "020-50685434",
            "status": "DELIVERED",
            "status_split": True,
            "status_extended": {"DELIVERED": 1, "IN_TRANSIT": 2},
            "route": {"destination": {"location": {"iata": "SJO"}}},
            "movements": [
                {"event": "RCF", "status": "ACT", "location": {"iata": "SJO"}},
            ],
        }
    )

    assert lectura.partes == {"DELIVERED": 1, "IN_TRANSIT": 2}
    assert lectura.etapa == "EN_TRANSITO", "manda la parte que no ha llegado"


def test_un_envio_partido_con_todo_igual_no_retrocede() -> None:
    lectura = interpretar(
        {
            "awb_number": "020-50685434",
            "status": "DELIVERED",
            "status_split": True,
            "status_extended": {"DELIVERED": 3},
            "route": {"destination": {"location": {"iata": "SJO"}}},
            "movements": [{"event": "RCF", "status": "ACT", "location": {"iata": "SJO"}}],
        }
    )

    assert lectura.etapa == "EN_DESTINO"


# --- El catálogo de aerolíneas: la comprobación gratuita --------------------


@pytest.mark.parametrize(
    ("mawb", "esperado"),
    [
        ("020-50685434", "020"),
        ("02050685434", "020"),
        ("  020-50685434  ", "020"),
        ("ABC-12345678", None),  # un HAWB del agente de carga
        ("020-1234567", None),  # falta un dígito
        ("", None),
        (None, None),
    ],
)
def test_el_prefijo_se_extrae_del_mawb(mawb: str | None, esperado: str | None) -> None:
    assert prefijo_de(mawb) == esperado


def test_el_catalogo_real_trae_las_doscientas_siete() -> None:
    catalogo = _catalogo()

    assert len(catalogo.aerolineas) == 207
    assert bool(catalogo) is True


def test_el_mawb_real_resuelve_a_lufthansa() -> None:
    aerolinea = _catalogo().resolver(MAWB)

    assert aerolinea is not None
    assert aerolinea.iata == "LH"
    assert aerolinea.nombre == "LUFTHANSA CARGO"
    assert "020" in aerolinea.prefijos


def test_una_aerolinea_puede_tener_varios_prefijos() -> None:
    """Lufthansa emite con `020` y `220`."""
    catalogo = _catalogo()

    assert catalogo.resolver("220-50685434") is not None
    assert catalogo.resolver("220-50685434") == catalogo.resolver("020-50685434")


def test_un_hawb_no_resuelve() -> None:
    """El error más frecuente de la vía aérea, según el contrato de `TASK-30`."""
    assert _catalogo().cubre("ABC-12345678") is False


def test_un_catalogo_vacio_no_sirve_para_negar_cobertura() -> None:
    """Es la diferencia entre «no cubre» y «no pude leer el catálogo».

    Negar el alta por lo segundo dejaría de rastrear envíos válidos porque una
    consulta **gratuita** falló, que es el peor intercambio posible.
    """
    vacio = CatalogoAerolineas([])

    assert bool(vacio) is False
    assert vacio.resolver(MAWB) is None


# --- La carga paginada -----------------------------------------------------


class _ClienteFalso:
    def __init__(self, paginas: list[dict[str, Any]]) -> None:
        self.paginas = paginas
        self.rutas: list[str] = []

    async def consultar(self, ruta: str) -> dict[str, Any]:
        self.rutas.append(ruta)
        return self.paginas.pop(0) if self.paginas else {"airlines": []}


async def test_carga_el_catalogo_paginando() -> None:
    cliente = _ClienteFalso(
        [
            {"airlines": [{"iata": "LH", "name": "LUFTHANSA", "prefixes": ["020"]}]},
            {"airlines": [{"iata": "CA", "name": "AIR CHINA", "prefixes": ["999"]}]},
            {"airlines": []},
        ]
    )

    catalogo = await cargar(cliente)

    assert len(catalogo.aerolineas) == 2
    assert len(cliente.rutas) == 3


async def test_una_paginacion_ignorada_no_gira_sin_fin() -> None:
    """`TASK-28` midió que ShipsGo **ignora en silencio** los parámetros que no
    conoce. Si el nombre del parámetro cambiara, volvería la misma página."""
    misma = {"airlines": [{"iata": "LH", "name": "LUFTHANSA", "prefixes": ["020"]}]}
    cliente = _ClienteFalso([dict(misma) for _ in range(50)])

    catalogo = await cargar(cliente, paginas_maximas=20)

    assert len(catalogo.aerolineas) == 1
    assert len(cliente.rutas) == 2, "se corta al ver que repite"
