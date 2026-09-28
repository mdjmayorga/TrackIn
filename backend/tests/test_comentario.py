"""Pruebas de `app.services.ingesta.comentario` — `US-52`.

Con los comentarios **reales** de «Comentario comprador» del Z-tracking WK38
(28/09/2026): lo que se fija es que lo que Logística escribe a mano se lea
bien, y que lo que no es una referencia no se convierta en una.
"""

from __future__ import annotations

import pytest

from app.services.ingesta.comentario import referencia_en_comentario


@pytest.mark.parametrize(
    ("comentario", "esperado"),
    [
        # OC 4500016185-10: el BL de COSCO que descarga en Caldera.
        ("ETA CR 03 OCT _ BL COSU6508789000 ", ("BL", "COSU6508789000")),
        # OC 4500018062: una guía madre de Lufthansa Cargo, once dígitos.
        (
            "COA Aprobado \nDocumentos de envio aprobados /  AWB 02025244995 / ETA 11SEP\nTL 30SEP",
            ("MAWB", "02025244995"),
        ),
        # OC 4500018603-10: dice «AWB», pero es la guía hija del agente de carga.
        ("AWB NO: ZIVHYD017  / ETA CR 8 SEP\n", ("HAWB", "ZIVHYD017")),
        ("MAWB 020-12345675", ("MAWB", "020-12345675")),
        ("HAWB: SPX-99812", ("HAWB", "SPX-99812")),
        ("booking # 271108898", ("BOOKING", "271108898")),
        ("contenedor MRSU8132490 en patio", ("CONTENEDOR", "MRSU8132490")),
    ],
)
def test_reconoce_las_referencias_escritas_a_mano(
    comentario: str, esperado: tuple[str, str]
) -> None:
    assert referencia_en_comentario(comentario) == esperado


@pytest.mark.parametrize(
    "comentario",
    [
        # Reales: nombran el documento pero todavía no hay número.
        "COMPRA ANUAL 2026\n4500016187-2\nPendiente BL y ETA  SEP 25",
        "ETA 30 SEP / APROBAR GUIA",
        "BL no disponible",
        # Un número de orden no es un contenedor.
        "ver 4500016187-2",
        "",
        None,
    ],
)
def test_lo_que_no_es_referencia_no_se_inventa(comentario: str | None) -> None:
    assert referencia_en_comentario(comentario) is None


def test_el_bl_gana_al_contenedor_suelto() -> None:
    """Un BL ampara todos sus contenedores con un solo crédito."""
    assert referencia_en_comentario("MRSU8132490 / BL COSU6508789000") == (
        "BL",
        "COSU6508789000",
    )
