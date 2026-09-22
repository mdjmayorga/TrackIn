"""Pruebas de `app.services.parametros` — RF-24 / RNF-07 / RNF-15.

La propiedad central del módulo es que **el sistema funciona con la tabla
vacía**: el catálogo declara el valor por defecto y la fila solo lo sobreescribe.
Eso es lo que permite que un parámetro nuevo no rompa un despliegue viejo.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.models.parametro_sistema import ParametroSistema
from app.services import parametros

pytestmark = pytest.mark.integration


async def _fijar(sesion, clave: str, valor: str) -> None:
    """Escribe el parámetro dentro de la transacción que se revierte."""
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    definicion = parametros.CATALOGO[clave]
    sesion.add(
        ParametroSistema(
            clave=clave,
            valor=valor,
            tipo_dato=definicion.tipo_dato,
            descripcion=definicion.descripcion[:200],
        )
    )
    await sesion.flush()


# --- El catálogo -----------------------------------------------------------


def test_el_catalogo_es_coherente() -> None:
    """La clave del diccionario y la del objeto no pueden divergir."""
    for clave, definicion in parametros.CATALOGO.items():
        assert definicion.clave == clave
        assert definicion.descripcion
        assert definicion.tipo_dato in {"ENTERO", "DECIMAL", "BOOLEANO", "TEXTO"}


def test_los_defectos_respetan_su_tipo_declarado() -> None:
    for definicion in parametros.CATALOGO.values():
        if definicion.tipo_dato == "ENTERO":
            assert isinstance(definicion.defecto, int)
        elif definicion.tipo_dato == "DECIMAL":
            assert isinstance(definicion.defecto, Decimal)


async def test_leer_una_clave_no_declarada_es_un_error(sesion) -> None:
    """Un typo al leer debe reventar acá, no devolver `None` silenciosamente."""
    with pytest.raises(KeyError, match="no declarado"):
        await parametros.obtener(sesion, "parametro_que_no_existe")


# --- Precedencia: la fila gana, el defecto respalda ------------------------


async def test_la_migracion_sembro_los_parametros(sesion) -> None:
    """Las siembran `0003`, `0004` y `0008`, para que quien administra las
    descubra sin leer el código. La prueba recorre `CATALOGO` entero, así que
    un parámetro nuevo sin migración la rompe."""
    for clave in parametros.CATALOGO:
        fila = await sesion.get(ParametroSistema, clave)
        assert fila is not None, f"{clave} no quedó sembrado por ninguna migración"


async def test_la_fila_sobreescribe_el_defecto(sesion) -> None:
    await _fijar(sesion, "intervalo_minimo_persistencia_s", "42")
    assert await parametros.obtener_entero(sesion, "intervalo_minimo_persistencia_s") == 42


async def test_sin_fila_se_usa_el_defecto(sesion) -> None:
    """La propiedad que permite arrancar con la tabla vacía."""
    clave = "intervalo_minimo_persistencia_s"
    await sesion.execute(delete(ParametroSistema).where(ParametroSistema.clave == clave))
    await sesion.flush()
    assert await parametros.obtener(sesion, clave) == parametros.CATALOGO[clave].defecto


async def test_un_valor_ilegible_cae_al_defecto_sin_fallar(sesion, caplog) -> None:
    """Una errata en una fila de configuración no debe dejar el sistema roto."""
    clave = "intervalo_minimo_persistencia_s"
    await _fijar(sesion, clave, "trescientos")
    valor = await parametros.obtener(sesion, clave)
    assert valor == parametros.CATALOGO[clave].defecto
    assert "trescientos" in caplog.text


# --- Conversión de tipos ---------------------------------------------------


async def test_decimal_conserva_la_precision(sesion) -> None:
    await _fijar(sesion, "velocidad_minima_eta_nudos", "0.5")
    assert await parametros.obtener_decimal(sesion, "velocidad_minima_eta_nudos") == Decimal("0.5")


async def test_obtener_entero_estrecha_el_tipo(sesion) -> None:
    valor = await parametros.obtener_entero(sesion, "umbral_riesgo_dias")
    assert isinstance(valor, int)


@pytest.mark.parametrize(
    ("bruto", "tipo_dato", "esperado"),
    [
        ("300", "ENTERO", 300),
        ("-5", "ENTERO", -5),
        ("1.5", "DECIMAL", Decimal("1.5")),
        ("true", "BOOLEANO", True),
        ("SI", "BOOLEANO", True),
        ("sí", "BOOLEANO", True),
        ("1", "BOOLEANO", True),
        ("false", "BOOLEANO", False),
        ("cualquier cosa", "BOOLEANO", False),
        ("un texto", "TEXTO", "un texto"),
    ],
)
def test_conversion_por_tipo(bruto: str, tipo_dato: str, esperado) -> None:
    """`BOOLEANO` y `TEXTO` todavía no los usa ningún parámetro del catálogo.

    Se prueban igual: la conversión es parte del contrato del módulo y el primer
    parámetro de esos tipos no debería estrenar código sin cubrir.
    """
    convertido = parametros._convertir(bruto, tipo_dato, "umbral_riesgo_dias")
    assert convertido == esperado
    assert isinstance(convertido, type(esperado))


def test_un_decimal_ilegible_cae_al_defecto() -> None:
    defecto = parametros.CATALOGO["velocidad_minima_eta_nudos"].defecto
    assert parametros._convertir("rapido", "DECIMAL", "velocidad_minima_eta_nudos") == defecto


async def test_los_valores_sembrados_coinciden_con_los_defectos(sesion) -> None:
    """Si la migración y el catálogo divergen, el comportamiento cambia según
    haya corrido la migración o no. Esta prueba lo impide."""
    for clave, definicion in parametros.CATALOGO.items():
        assert (
            await parametros.obtener(sesion, clave) == definicion.defecto
        ), f"{clave}: la fila sembrada no coincide con CATALOGO"
