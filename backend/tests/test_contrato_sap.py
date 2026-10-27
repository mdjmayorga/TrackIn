"""El contrato de la API de SAP no se desfasa del sistema — `US-64`.

`docs/integraciones/sap/` es lo que tiene que cumplir quien construya la API de
SAP. Si mañana el lector del Excel suma un campo (como `solicitud_pedido` en
`US-63`) y nadie toca el contrato, la API nacería sin él. Estas pruebas fallan
en ese momento, no el día de la integración.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import typing
from pathlib import Path
from typing import Any

import pytest

from app.models.enums import TIPOS_PROVEEDOR, VIAS_TRANSPORTE
from app.schemas.pedidos import TipoReferencia
from app.services.ingesta.dto import PedidoCrudo

CARPETA = Path(__file__).resolve().parents[2] / "docs" / "integraciones" / "sap"

#: Lo que el lector deduce y la fuente no envía.
_DERIVADOS = {"referencia_desde_comentario"}
#: Lo que la fuente envía y el lector no guarda: `comentario` solo se lee para
#: buscar referencias escritas a mano (`US-52`), de donde sale el derivado.
_SOLO_ENTRADA = {"comentario"}


def _json(nombre: str) -> Any:
    return json.loads((CARPETA / nombre).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return _json("lote_pedidos.schema.json")


@pytest.fixture(scope="module")
def pedido(esquema) -> dict[str, Any]:
    return esquema["$defs"]["pedido"]


def _en_uso(pedido: dict[str, Any]) -> set[str]:
    return {
        campo
        for campo, definicion in pedido["properties"].items()
        if not definicion.get("description", "").startswith("RESERVADO")
    }


def _enum(definicion: dict[str, Any]) -> set[Any]:
    return {valor for valor in definicion["enum"] if valor is not None}


def test_los_campos_en_uso_son_los_del_lector(pedido) -> None:
    del_lector = {campo.name for campo in dataclasses.fields(PedidoCrudo)} - _DERIVADOS

    assert _en_uso(pedido) == del_lector | _SOLO_ENTRADA


def test_los_obligatorios_son_los_que_el_lector_exige(pedido) -> None:
    sin_valor_por_defecto = {
        campo.name
        for campo in dataclasses.fields(PedidoCrudo)
        if campo.default is dataclasses.MISSING and campo.default_factory is dataclasses.MISSING
    }

    assert set(pedido["required"]) == sin_valor_por_defecto


def test_los_vocabularios_coinciden_con_el_dominio(pedido) -> None:
    propiedades = pedido["properties"]

    assert _enum(propiedades["via_transporte"]) == set(VIAS_TRANSPORTE)
    assert _enum(propiedades["tipo_referencia"]) == set(typing.get_args(TipoReferencia))
    assert _enum(propiedades["tipo_proveedor"]) == set(TIPOS_PROVEEDOR)


def test_los_destinos_son_los_del_maestro(pedido) -> None:
    ruta = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0002_maestros_paises_destinos.py"
    )
    spec = importlib.util.spec_from_file_location("maestros_0002", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    assert _enum(pedido["properties"]["destino_codigo"]) == {d[0] for d in modulo.DESTINOS}


def _cumple(valor: Any, definicion: dict[str, Any], defs: dict[str, Any]) -> bool:
    """Validación mínima del esquema: tipo, enum, patrón y referencias a `fecha`."""
    if "oneOf" in definicion:
        return sum(_cumple(valor, opcion, defs) for opcion in definicion["oneOf"]) == 1
    if "$ref" in definicion:
        return _cumple(valor, defs[definicion["$ref"].rsplit("/", 1)[1]], defs)
    tipos = definicion.get("type", [])
    tipos = [tipos] if isinstance(tipos, str) else tipos
    por_tipo = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if tipos and not any(por_tipo[t](valor) for t in tipos):
        return False
    if "enum" in definicion and valor not in definicion["enum"]:
        return False
    if isinstance(valor, str) and "pattern" in definicion:
        return re.search(definicion["pattern"], valor) is not None
    return True


def test_el_ejemplo_cumple_el_esquema(esquema, pedido) -> None:
    ejemplo = _json("ejemplo_lote.json")
    defs = esquema["$defs"]

    assert set(ejemplo["lote"]) <= set(esquema["properties"]["lote"]["properties"])
    for linea in ejemplo["pedidos"]:
        assert set(pedido["required"]) <= set(linea)
        assert set(linea) <= set(pedido["properties"])
        for campo, valor in linea.items():
            assert _cumple(valor, pedido["properties"][campo], defs), campo
    # El ejemplo completo muestra todos los campos, también los reservados.
    assert set(ejemplo["pedidos"][0]) == set(pedido["properties"])


def test_postman_envia_el_ejemplo_y_todo_lo_documenta_el_readme(pedido) -> None:
    coleccion = _json("TrackIn_SAP.postman_collection.json")
    completo = json.loads(coleccion["item"][0]["request"]["body"]["raw"])
    readme = (CARPETA / "README.md").read_text(encoding="utf-8")

    assert completo["pedidos"] == _json("ejemplo_lote.json")["pedidos"]
    assert coleccion["item"][0]["request"]["url"]["raw"].endswith(
        "/api/v1/integraciones/sap/pedidos"
    )
    faltan = [campo for campo in pedido["properties"] if f"`{campo}`" not in readme]
    assert faltan == []
