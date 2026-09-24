"""Pruebas de `app.services.normalizacion` — RN-17 / `TASK-29`.

Los casos **no son inventados**: salen de la muestra real del Z-tracking del
03/09/2026 (`docs/analisis/2026-Agosto-WK36_anonimizado.csv`, 429 líneas). Cada
suciedad que se prueba aquí aparece de verdad en ese archivo, y la regla de
RN-17 es que ninguna aborta la carga: lo que no resuelve queda en `None` y la
línea se marca para revisión.
"""

from __future__ import annotations

import pytest

from app.services.normalizacion import (
    INCOTERMS,
    VALORES_NO_DATO,
    destino_nombrado_en_incoterm,
    normalizar_incoterm,
    normalizar_temperatura,
    normalizar_texto,
    normalizar_via,
    resolver_pais,
)

# --- normalizar_texto ------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("india", "INDIA"),
        ("  China  ", "CHINA"),
        ("ESPAÑA", "ESPANA"),  # la ñ se descompone y pierde el diacrítico
        ("Mexico", "MEXICO"),
        ("México", "MEXICO"),  # con y sin tilde colapsan al mismo valor
        ("ESTADOS   UNIDOS", "ESTADOS UNIDOS"),  # espacios internos repetidos
        ("Bélgica", "BELGICA"),
    ],
)
def test_normalizar_texto(entrada: str, esperado: str) -> None:
    assert normalizar_texto(entrada) == esperado


@pytest.mark.parametrize("marcador", sorted(VALORES_NO_DATO))
def test_los_marcadores_de_no_dato_dan_none(marcador: str) -> None:
    """`PENDIENTE`, la errata `PEDIENTE`, `N/A`… no son datos, son ausencia."""
    assert normalizar_texto(marcador) is None


def test_los_marcadores_de_no_dato_tambien_sucios() -> None:
    assert normalizar_texto("  pendiente  ") is None
    assert normalizar_texto("Pedientes"[:-1]) is None  # la errata real, capitalizada


def test_normalizar_texto_con_none() -> None:
    assert normalizar_texto(None) is None


def test_normalizar_texto_acepta_no_cadenas() -> None:
    """Las celdas numéricas del Excel llegan como int, no como str."""
    assert normalizar_texto(2026) == "2026"  # type: ignore[arg-type]


# --- normalizar_via --------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("MARITIMO", "MARITIMO"),
        ("Marítimo", "MARITIMO"),  # con tilde
        ("AEREO", "AEREO"),
        ("Terrestre", "TERRESTRE"),
        ("TERRESTRE", "TERRESTRE"),
    ],
)
def test_normalizar_via_resuelve_las_tres(entrada: str, esperado: str) -> None:
    assert normalizar_via(entrada) == esperado


def test_via_con_columna_desplazada_no_resuelve() -> None:
    """En la muestra, tres líneas traen `INDIA` en la columna de transporte.

    Es un país, no una vía. Devolver `None` es lo correcto: la línea entra y se
    marca para revisión, en vez de inventar una vía.
    """
    assert normalizar_via("INDIA") is None


def test_via_multivalor_no_resuelve() -> None:
    """Una línea real trae `AEREO\\nMARITIMO`: el envío se partió en dos.

    No se puede elegir una sin perder información, así que se revisa a mano.
    """
    assert normalizar_via("AEREO\nMARITIMO") is None


@pytest.mark.parametrize("entrada", ["PENDIENTE", "N/A", "", None])
def test_via_sin_dato(entrada: str | None) -> None:
    assert normalizar_via(entrada) is None


# --- normalizar_incoterm ---------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("EXW", "EXW"),
        ("Exw", "EXW"),  # conviven ambas grafías en el archivo
        ("CIF", "CIF"),
        ("CIF LIMON", "CIF"),  # el lugar convenido se descarta
        ("CIF TERRESTRE", "CIF"),
        ("CIP", "CIP"),
        ("FCA", "FCA"),
        ("FOB", "FOB"),
        ("CPT", "CPT"),
        ("LOCAL", "LOCAL"),  # valor propio de Gutis para compras nacionales
    ],
)
def test_normalizar_incoterm(entrada: str, esperado: str) -> None:
    assert normalizar_incoterm(entrada) == esperado


@pytest.mark.parametrize("entrada", ["XXX", "NO ES UN INCOTERM", "PENDIENTE", None])
def test_incoterm_no_resoluble(entrada: str | None) -> None:
    assert normalizar_incoterm(entrada) is None


def test_todo_incoterm_del_catalogo_se_resuelve_a_si_mismo() -> None:
    for codigo in INCOTERMS:
        assert normalizar_incoterm(codigo) == codigo


# --- normalizar_temperatura ------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Ambiente", "AMBIENTE"),
        ("AMBIENTE", "AMBIENTE"),
        ("Entre 2°-8° C", "2-8 C"),  # cadena de frío
        ("2-8 C", "2-8 C"),
        ("Entre 15°-25° C", "15-25 C"),
        ("15-25 C", "15-25 C"),
    ],
)
def test_normalizar_temperatura(entrada: str, esperado: str) -> None:
    assert normalizar_temperatura(entrada) == esperado


def test_temperatura_desconocida_se_conserva_tal_cual() -> None:
    """No se pierde información: lo que no encaja se guarda como vino.

    Un rango nuevo tiene que poder leerse aunque el catálogo no lo contemple.
    """
    assert normalizar_temperatura("Entre -20 y -10 C") == "ENTRE -20 Y -10 C"


@pytest.mark.parametrize("entrada", ["PENDIENTE", "N/A", "", None])
def test_temperatura_sin_dato(entrada: str | None) -> None:
    assert normalizar_temperatura(entrada) is None


def test_ambiente_tiene_prioridad_sobre_los_rangos() -> None:
    """Si el texto menciona ambiente, manda, aunque traiga números sueltos."""
    assert normalizar_temperatura("Ambiente 2 a 8") == "AMBIENTE"


# --- resolver_pais (requiere la base con los datos semilla de 0002) --------


@pytest.mark.integration
@pytest.mark.parametrize(
    ("grafia", "codigo_esperado"),
    [
        ("INDIA", "IN"),
        ("India", "IN"),
        ("CHINA", "CN"),
        ("BRASIL", "BR"),
        ("ESPAÑA", "ES"),  # con ñ
        ("ESPANA", "ES"),  # sin ñ: el alias está normalizado en el maestro
        ("Mexico", "MX"),
        ("México", "MX"),
    ],
)
async def test_resolver_pais_por_alias(sesion, grafia: str, codigo_esperado: str) -> None:
    pais = await resolver_pais(sesion, grafia)
    assert pais is not None, f"{grafia!r} no resolvió contra el maestro"
    assert pais.codigo == codigo_esperado


@pytest.mark.integration
async def test_resolver_pais_por_codigo_iso(sesion) -> None:
    """Dos letras se buscan primero como código ISO, antes que como alias."""
    pais = await resolver_pais(sesion, "CR")
    assert pais is not None
    assert pais.codigo == "CR"


@pytest.mark.integration
async def test_usa_y_estados_unidos_resuelven_al_mismo_pais(sesion) -> None:
    """La suciedad más citada de la muestra: dos grafías, un solo país."""
    por_sigla = await resolver_pais(sesion, "USA")
    por_nombre = await resolver_pais(sesion, "ESTADOS UNIDOS")
    assert por_sigla is not None and por_nombre is not None
    assert por_sigla.codigo == por_nombre.codigo == "US"


@pytest.mark.integration
@pytest.mark.parametrize("grafia", ["PENDIENTE", "N/A", "", None, "PAIS QUE NO EXISTE"])
async def test_resolver_pais_no_resoluble(sesion, grafia: str | None) -> None:
    """`None` significa «revisar esta línea», no «abortar el lote» (RN-17)."""
    assert await resolver_pais(sesion, grafia) is None


# --- destino_nombrado_en_incoterm ------------------------------------------

#: Los tres puertos del maestro, como los ve la función: código y nombre.
#: Se pasan explícitos para que estas pruebas no necesiten base de datos.
_PUERTOS = [("CRMOB", "Moín"), ("CRLIO", "Puerto Limón"), ("CRCAL", "Puerto Caldera")]


@pytest.mark.parametrize(
    ("incoterm", "esperado"),
    [
        # Lo que Planificación confirmó el 23/09/2026, y lo que el archivo trae
        # hoy en 18 de sus 110 líneas marítimas.
        ("CIF LIMON", "CRLIO"),
        # La tilde del maestro («Puerto Limón») no tiene que estar en el archivo.
        ("CIF LIMÓN", "CRLIO"),
        ("cif limon", "CRLIO"),
        # El prefijo genérico sobra: se pacta el lugar, no el nombre completo.
        ("CIF PUERTO LIMON", "CRLIO"),
        # Ninguno de estos existe todavía en el archivo, y ya se resuelven.
        ("FOB CALDERA", "CRCAL"),
        ("CIF MOIN", "CRMOB"),
        ("DAP MOÍN", "CRMOB"),
        # Sin lugar no hay nada que resolver: son 89 de las 110 líneas.
        ("EXW", None),
        ("CIF", None),
        ("FOB", None),
        # Dos puertos es tan ambiguo como ninguno: Caldera es Pacífico.
        ("CIF LIMON / CALDERA", None),
        # Un lugar que no es ninguno de los destinos no inventa uno.
        ("CIF SHANGHAI", None),
        ("PENDIENTE", None),
        ("N/A", None),
        ("", None),
        (None, None),
    ],
)
def test_destino_nombrado_en_incoterm(incoterm: str | None, esperado: str | None) -> None:
    assert destino_nombrado_en_incoterm(incoterm, _PUERTOS) == esperado


def test_el_lugar_se_busca_por_palabra_entera() -> None:
    """Sin límite de palabra, cualquier subcadena daría un falso positivo.

    `LIMONAL` es un lugar de Costa Rica y no es Puerto Limón.
    """
    assert destino_nombrado_en_incoterm("CIF LIMONAL", _PUERTOS) is None


def test_sin_candidatos_no_resuelve_nada() -> None:
    """Una vía sin destinos activos en el maestro: no hay entre qué elegir."""
    assert destino_nombrado_en_incoterm("CIF LIMON", []) is None


def test_el_codigo_del_incoterm_nunca_es_un_lugar() -> None:
    """Si un destino se llamara como un incoterm, el código no lo elegiría.

    Rebuscado, pero es lo que separa «quién paga el flete» de «dónde atraca»:
    la función mira el lugar, no el código.
    """
    assert destino_nombrado_en_incoterm("CIF", [("XXCIF", "CIF")]) is None
