"""Pruebas de `app.services.ingesta.registro` — `TASK-03`.

Este módulo es el único que conoce las implementaciones concretas de
`FuentePedidos`; todo lo demás depende del puerto. Es también el patrón sobre el
que van a montarse las fuentes de rastreo (`US-45` Vizion, `US-46` Portcast),
así que conviene fijar su contrato por pruebas antes de replicarlo.

**Ojo con dónde vive la validación.** `Settings.INGESTA_ADAPTADOR` es un
`Literal["semilla", "ninguno"]`: pydantic rechaza cualquier otro valor al
construir el objeto, de modo que las ramas defensivas de `obtener_fuente`
—nombre desconocido, mayúsculas, cadena vacía— **no son alcanzables** por la vía
normal. Se prueban igual con un doble, porque siguen siendo el contrato del
módulo y `US-31` va a ampliar el `Literal` con `ztracking`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.services.ingesta.base import FuentePedidos
from app.services.ingesta.registro import _FUENTES, obtener_fuente
from app.services.ingesta.semilla import FuenteSemilla


def _config(adaptador: str = "semilla", entorno: str = "development") -> Settings:
    """Settings aislado, sin depender del `.env` de la máquina."""
    return Settings(INGESTA_ADAPTADOR=adaptador, ENVIRONMENT=entorno)


@dataclass
class _ConfigLibre:
    """Doble de `Settings` sin la restricción del `Literal`.

    Permite ejercitar las ramas defensivas de `obtener_fuente` que hoy pydantic
    vuelve inalcanzables. No sustituye a `Settings` en ninguna otra prueba.
    """

    INGESTA_ADAPTADOR: str
    is_production: bool = False


# --- El contrato real, el que se alcanza vía Settings ----------------------


def test_devuelve_la_fuente_semilla() -> None:
    assert isinstance(obtener_fuente(_config("semilla")), FuenteSemilla)


def test_ninguno_devuelve_none_sin_fallar() -> None:
    """«Sin fuente» es un valor válido, no un error (tercer criterio de TASK-03)."""
    assert obtener_fuente(_config("ninguno")) is None


def test_la_fuente_cumple_el_puerto() -> None:
    """Si `FuenteSemilla` deja de satisfacer el Protocol, esto lo detecta."""
    fuente = obtener_fuente(_config("semilla"))
    assert isinstance(fuente, FuentePedidos)
    assert fuente.nombre and fuente.descripcion


def test_cada_llamada_construye_una_instancia_nueva() -> None:
    """El registro guarda constructores, no instancias compartidas."""
    assert obtener_fuente(_config()) is not obtener_fuente(_config())


def test_todo_lo_registrado_construye_una_fuente_valida() -> None:
    """Invariante del registro: ninguna entrada puede estar rota."""
    for nombre, constructor in _FUENTES.items():
        assert isinstance(constructor(), FuentePedidos), f"{nombre} no cumple el puerto"


@pytest.mark.parametrize("invalido", ["ztraking", "SEMILLA", "", "none", "inexistente"])
def test_settings_rechaza_los_adaptadores_que_no_existen(invalido: str) -> None:
    """La errata se detiene en la configuración, no en el registro.

    Documenta el comportamiento real: un valor mal escrito **impide arrancar**,
    en lugar de degradar a «sin fuente» como sugiere el docstring del módulo.
    """
    with pytest.raises(ValueError):
        _config(invalido)


# --- Producción ------------------------------------------------------------


def test_la_semilla_en_produccion_avisa_pero_no_bloquea(caplog) -> None:
    """Son datos inventados: no deberían verse en producción, pero tumbar el
    arranque por eso sería peor que dejarlo dicho."""
    with caplog.at_level(logging.WARNING):
        fuente = obtener_fuente(_config("semilla", entorno="production"))
    assert isinstance(fuente, FuenteSemilla)
    assert "producci" in caplog.text  # con o sin tilde


def test_la_semilla_en_desarrollo_no_avisa(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        obtener_fuente(_config("semilla", entorno="development"))
    assert "producci" not in caplog.text


# --- Ramas defensivas, hoy inalcanzables vía Settings ---------------------


@pytest.mark.parametrize("nombre", ["SEMILLA", "  Semilla  ", "sEmIlLa"])
def test_el_registro_tolera_mayusculas_y_espacios(nombre: str) -> None:
    assert isinstance(obtener_fuente(_ConfigLibre(nombre)), FuenteSemilla)


@pytest.mark.parametrize("nombre", ["", "   ", "ninguno", "none", "NINGUNO"])
def test_el_registro_trata_como_sin_fuente(nombre: str) -> None:
    assert obtener_fuente(_ConfigLibre(nombre)) is None


def test_adaptador_desconocido_degrada_a_sin_fuente(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        assert obtener_fuente(_ConfigLibre("ztraking")) is None
    assert "ztraking" in caplog.text
    assert "desconocido" in caplog.text


def test_el_adaptador_desconocido_lista_los_disponibles(caplog) -> None:
    """El log tiene que decir qué se puede poner, no solo que está mal."""
    with caplog.at_level(logging.WARNING):
        obtener_fuente(_ConfigLibre("inexistente"))
    for disponible in _FUENTES:
        assert disponible in caplog.text


# --- El puerto no persiste -------------------------------------------------


async def test_la_semilla_entrega_pedidos_sin_tocar_la_base() -> None:
    """Segundo criterio del puerto: obtener no persiste.

    Corre sin base de datos a propósito; si la fuente escribiera, fallaría.
    """
    fuente = obtener_fuente(_config("semilla"))
    assert fuente is not None
    pedidos = await fuente.obtener_pedidos()
    assert pedidos, "la semilla no devolvió ninguna línea"
    assert all(p.oc_numero for p in pedidos)
