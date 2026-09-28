"""Pruebas de `app.services.rastreo.destino_shipsgo` — `US-52`.

Con los **payloads reales grabados** en `TASK-28`: el BL COSCO `COSU6508789000`
(descarga en Caldera) y los contenedores Maersk (descargan en Moín, que ShipsGo
llama `CRPMN`). Sin red y sin créditos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.rastreo.destino_shipsgo import EQUIVALENCIAS, ResolutorDestinoShipsGo
from app.services.rastreo.shipsgo_cliente import ErrorShipsGo

_SALIDA = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
_MADUROS = _SALIDA / "06_payload_personal.json"
_PENDIENTES = _SALIDA / "07_pendientes_personal.json"

pytestmark = pytest.mark.skipif(
    not (_MADUROS.exists() and _PENDIENTES.exists()),
    reason="faltan los payloads grabados del spike TASK-28",
)


def _embarques() -> dict[int, dict[str, Any]]:
    embarques: dict[int, dict[str, Any]] = {}
    for archivo in (_MADUROS, _PENDIENTES):
        for registro in json.loads(archivo.read_text(encoding="utf-8"))["embarques"]:
            payload = registro["payload_shipment"]
            embarques[int(payload["id"])] = payload
    return embarques


class ClienteFalso:
    """La cuenta con los embarques grabados; cuenta cada llamada."""

    def __init__(self, embarques: dict[int, dict[str, Any]] | None = None) -> None:
        self.embarques = embarques if embarques is not None else _embarques()
        self.listados = 0
        self.lecturas: list[int] = []
        self.altas = 0
        self.error: ErrorShipsGo | None = None

    async def consultar(self, ruta: str) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        self.listados += 1
        aereo = ruta.startswith("/air")
        lote = [e for e in self.embarques.values() if bool(e.get("awb_number")) == aereo]
        return {"shipments": lote, "meta": {"more": False}}

    async def leer(self, id_embarque: int, aereo: bool = False) -> dict[str, Any]:
        self.lecturas.append(id_embarque)
        return self.embarques[id_embarque]

    async def dar_de_alta(self, *_args: Any) -> None:  # pragma: no cover - no debe llamarse
        self.altas += 1
        raise AssertionError("el resolutor nunca da de alta")


async def test_el_bl_de_cosco_descarga_en_caldera() -> None:
    """El caso real del 28/09: incoterm «CIF» sin puerto, y la naviera dice Caldera."""
    cliente = ClienteFalso()
    resolutor = ResolutorDestinoShipsGo(cliente)  # type: ignore[arg-type]

    assert await resolutor("BL", "COSU6508789000") == "CRCAL"
    assert cliente.altas == 0


async def test_moin_se_traduce_al_codigo_del_maestro() -> None:
    """ShipsGo dice `CRPMN` («Puerto Moín»); el maestro lo registra como `CRMOB`."""
    resolutor = ResolutorDestinoShipsGo(ClienteFalso())  # type: ignore[arg-type]

    assert await resolutor("CONTENEDOR", "MRSU8132490") == EQUIVALENCIAS["CRPMN"] == "CRMOB"


async def test_el_aeropuerto_se_traduce_de_iata_a_oaci() -> None:
    resolutor = ResolutorDestinoShipsGo(ClienteFalso())  # type: ignore[arg-type]

    assert await resolutor("MAWB", "020-50685434") == "MROC"


async def test_lo_no_registrado_no_se_da_de_alta() -> None:
    """Dar de alta cuesta un crédito: la línea queda como estaba."""
    cliente = ClienteFalso()
    resolutor = ResolutorDestinoShipsGo(cliente)  # type: ignore[arg-type]

    assert await resolutor("BL", "MAEU999999999") is None
    assert cliente.altas == 0
    assert cliente.lecturas == []


async def test_una_guia_hija_no_se_le_pregunta_a_shipsgo() -> None:
    """La guía hija la rastrea TICA; ShipsGo no la conoce."""
    cliente = ClienteFalso()
    resolutor = ResolutorDestinoShipsGo(cliente)  # type: ignore[arg-type]

    assert await resolutor("HAWB", "ZIVHYD017") is None
    assert cliente.listados == 0


async def test_el_indice_se_arma_una_vez_y_lo_resuelto_se_recuerda() -> None:
    """Un BL puede amparar varias líneas del mismo archivo."""
    cliente = ClienteFalso()
    resolutor = ResolutorDestinoShipsGo(cliente)  # type: ignore[arg-type]

    for _ in range(3):
        await resolutor("BL", "COSU6508789000")

    assert cliente.listados == 2  # marítimo y aéreo, una sola vez
    assert cliente.lecturas == [6734941]
    assert resolutor.lecturas == 1


async def test_un_embarque_que_madura_no_se_recuerda() -> None:
    """Recién dado de alta no tiene ruta; dentro de un rato puede tenerla."""
    embarques = _embarques()
    embarques[6734941] = {**embarques[6734941], "status": "NEW", "route": None, "containers": []}
    cliente = ClienteFalso(embarques)
    resolutor = ResolutorDestinoShipsGo(cliente)  # type: ignore[arg-type]

    assert await resolutor("BL", "COSU6508789000") is None
    assert await resolutor("BL", "COSU6508789000") is None
    assert cliente.lecturas == [6734941, 6734941]


async def test_si_shipsgo_falla_no_aborta_ni_insiste() -> None:
    cliente = ClienteFalso()
    cliente.error = ErrorShipsGo("error_del_servidor", "503")
    resolutor = ResolutorDestinoShipsGo(cliente)  # type: ignore[arg-type]

    assert await resolutor("BL", "COSU6508789000") is None
    cliente.error = None
    # El resto del lote no vuelve a intentarlo.
    assert await resolutor("CONTENEDOR", "MRSU8132490") is None
    assert cliente.listados == 0
