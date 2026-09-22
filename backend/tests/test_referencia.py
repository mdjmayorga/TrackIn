"""Pruebas de `app.services.referencia` — RF-03 / `US-01`.

Cubre las dos preguntas que el módulo separa a propósito: si la referencia está
bien escrita, y si hoy existe una fuente contratada que la siga. La segunda
depende de `TASK-28`, que sigue abierta: por eso un contenedor válido se acepta
pero **no** es rastreable todavía.

Los casos de formato salen del contrato de `TASK-30` y de la muestra real del
Z-tracking (`docs/analisis/2026-Agosto-WK36_anonimizado.csv`).
"""

from __future__ import annotations

import pytest

from app.models.enums import TIPOS_TRACKING
from app.services import referencia as ref
from app.services.referencia import (
    ResultadoReferencia,
    fuente_de,
    normalizar_referencia,
    validar_referencia,
)

# --- normalizar_referencia -------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("mscu1234567", "MSCU1234567"),
        ("  MSCU1234567  ", "MSCU1234567"),
        ("MSCU 123456 7", "MSCU1234567"),  # el archivo trae espacios internos
        ("020-12345675", "020-12345675"),  # el guion del MAWB se conserva
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalizar_referencia(entrada: str | None, esperado: str | None) -> None:
    assert normalizar_referencia(entrada) == esperado


def test_normalizar_referencia_acepta_no_cadenas() -> None:
    """El Excel entrega números como enteros cuando la celda es numérica."""
    assert normalizar_referencia(123456789) == "123456789"  # type: ignore[arg-type]


# --- Formato válido --------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [
        ("CONTENEDOR", "MSCU1234567"),  # ISO 6346
        ("CONTENEDOR", "mscu1234567"),  # minúsculas: se normalizan
        ("MMSI", "123456789"),  # nueve dígitos
        ("IMO", "1234567"),  # siete dígitos, sin prefijo
        ("IMO", "IMO1234567"),  # con el prefijo textual
        ("MAWB", "020-12345675"),  # prefijo de aerolínea + ocho
        ("MAWB", "02012345675"),  # el mismo, sin guion
        ("BL", "CUALQUIER-COSA-123"),  # sin patrón universal
        ("BOOKING", "BKG0001"),
        ("BUQUE", "EVER GIVEN"),
        ("VUELO", "LH507"),
        ("contenedor", "MSCU1234567"),  # el tipo también se normaliza
    ],
)
def test_referencias_con_formato_valido(tipo: str, numero: str) -> None:
    resultado = validar_referencia(tipo, numero)
    assert resultado.valida, resultado.motivo
    assert bool(resultado) is True  # __bool__ delega en `valida`


# --- Formato inválido ------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [
        ("CONTENEDOR", "MSC1234567"),  # tres letras, no cuatro
        ("CONTENEDOR", "MSCU123456"),  # seis dígitos, no siete
        ("CONTENEDOR", "1234MSCU567"),  # letras y dígitos invertidos
        ("MMSI", "12345678"),  # ocho dígitos
        ("MMSI", "1234567890"),  # diez dígitos
        ("MMSI", "ABCDEFGHI"),  # letras
        ("IMO", "123456"),  # seis dígitos
        ("MAWB", "0201234567"),  # diez dígitos, falta uno
    ],
)
def test_referencias_con_formato_invalido(tipo: str, numero: str) -> None:
    resultado = validar_referencia(tipo, numero)
    assert not resultado.valida
    assert not resultado.rastreable
    assert tipo.upper() in resultado.motivo


def test_mawb_mal_formado_sugiere_que_sea_un_hawb() -> None:
    """El error más frecuente de la vía aérea, según el contrato de TASK-30.

    Si el agente de carga entrega la guía hija, ninguna API la resuelve. El
    motivo tiene que decirlo, porque quien corrige el archivo no lo sabe.
    """
    resultado = validar_referencia("MAWB", "ABC-12345678")
    assert not resultado.valida
    assert "HAWB" in resultado.motivo


def test_tipo_desconocido_se_rechaza_y_lista_los_admitidos() -> None:
    resultado = validar_referencia("CODIGO_INVENTADO", "123")
    assert not resultado.valida
    assert "CODIGO_INVENTADO" in resultado.motivo
    for admitido in TIPOS_TRACKING:
        assert admitido in resultado.motivo


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [(None, "MSCU1234567"), ("CONTENEDOR", None), (None, None), ("", ""), ("  ", "  ")],
)
def test_falta_tipo_o_numero(tipo: str | None, numero: str | None) -> None:
    resultado = validar_referencia(tipo, numero)
    assert not resultado.valida
    assert "Falta" in resultado.motivo


# --- Rastreabilidad: depende de qué fuentes están contratadas --------------


@pytest.mark.parametrize(("tipo", "numero"), [("MMSI", "123456789"), ("VUELO", "LH507")])
def test_fuentes_gratuitas_si_rastrean(tipo: str, numero: str) -> None:
    """AISStream y OpenSky están conectadas: estas sí se siguen hoy."""
    resultado = validar_referencia(tipo, numero)
    assert resultado.valida and resultado.rastreable


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [
        ("CONTENEDOR", "MSCU1234567"),  # ShipsGo Ocean
        ("BL", "BL-0001"),  # ShipsGo Ocean
        ("BOOKING", "BKG0001"),  # ShipsGo Ocean
        ("MAWB", "020-12345675"),  # ShipsGo Air
    ],
)
def test_fuentes_de_pago_se_aceptan_pero_no_rastrean_todavia(tipo: str, numero: str) -> None:
    """ShipsGo está **validada pero sin créditos**.

    El tercer criterio de `US-01`: la referencia se guarda igual y el motivo
    explica por qué el pedido sigue sin rastreo automático. `TASK-28` cerró el
    14/09 con un go, pero los dos trials de 3 altas se agotaron y la compra se
    difiere al arranque. Cuando se compren los créditos hay que mover `shipsgo`
    a `_FUENTES_DISPONIBLES` y esta prueba va a fallar — es el recordatorio.
    """
    resultado = validar_referencia(tipo, numero)
    assert resultado.valida, resultado.motivo
    assert not resultado.rastreable
    assert "shipsgo" in resultado.motivo
    assert "créditos" in resultado.motivo


def test_buque_se_acepta_pero_ninguna_fuente_lo_sigue() -> None:
    """Un nombre de buque no es una clave de consulta en ninguna API."""
    resultado = validar_referencia("BUQUE", "EVER GIVEN")
    assert resultado.valida
    assert not resultado.rastreable
    assert "MMSI" in resultado.motivo  # dice cómo resolverlo


# --- fuente_de -------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "esperado"),
    [
        ("CONTENEDOR", "shipsgo"),
        ("MAWB", "shipsgo"),
        ("MMSI", "aisstream"),
        ("VUELO", "opensky"),
        ("BUQUE", "ninguna"),
        ("  contenedor  ", "shipsgo"),  # normaliza igual que validar_referencia
        ("INVENTADO", None),
        (None, None),
        ("", None),
    ],
)
def test_fuente_de(tipo: str | None, esperado: str | None) -> None:
    assert fuente_de(tipo) == esperado


# --- Invariantes del módulo ------------------------------------------------


def test_todo_tipo_admitido_tiene_patron_y_fuente() -> None:
    """Evita el olvido al ampliar `TIPOS_TRACKING`.

    Un tipo sin entrada en `_FUENTE_POR_TIPO` cae en el `.get(..., "ninguna")`
    y se vuelve silenciosamente no rastreable, que es un fallo difícil de ver.
    """
    for tipo in TIPOS_TRACKING:
        assert tipo in ref._PATRONES, f"{tipo} no declara patrón (usar None si no tiene)"
        assert tipo in ref._FUENTE_POR_TIPO, f"{tipo} no declara fuente"


def test_no_hay_patrones_ni_fuentes_de_tipos_inexistentes() -> None:
    assert set(ref._PATRONES) == set(TIPOS_TRACKING)
    assert set(ref._FUENTE_POR_TIPO) == set(TIPOS_TRACKING)


def test_el_resultado_es_inmutable() -> None:
    """`frozen=True`: el veredicto no se retoca después de emitirlo."""
    resultado = validar_referencia("MMSI", "123456789")
    with pytest.raises(AttributeError):
        resultado.valida = False  # type: ignore[misc]


def test_el_resultado_conserva_los_valores_normalizados() -> None:
    resultado = validar_referencia("  contenedor ", " mscu 1234567 ")
    assert resultado == ResultadoReferencia(
        valida=True,
        tipo="CONTENEDOR",
        numero="MSCU1234567",
        rastreable=False,
        motivo=resultado.motivo,
    )
