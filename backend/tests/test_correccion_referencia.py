"""Corregir una referencia mal escrita — 29/10/2026.

Lo que lo motivó, en `trackin_dev`: un BL asociado como `BLMAEU274029064` («BL»
de más) se dio de alta en ShipsGo, costó un crédito y quedó `UNTRACKED`; otro,
`MAEU71108898`, no coincidía con el `271108898` de la cuenta. Ninguno de los dos
pedidos tenía posición ni mapa, y una referencia asociada no se podía cambiar.

Tres piezas: corregir la referencia de un pedido, buscar en la cuenta de ShipsGo
sin el código de la naviera, y limpiar o avisar antes de gastar el crédito.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

import test_intervenciones as base
from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado
from app.services import intervenciones
from app.services.rastreo.indice_shipsgo import buscar
from app.services.referencia import advertencia_referencia, validar_referencia

api = base.api
_url = base._url

# --- Buscar sin el código de la naviera ---------------------------------------------------


@pytest.mark.parametrize(
    ("en_trackin", "en_shipsgo"),
    [
        ("MAEU271108898", "271108898"),  # el caso del 29/10
        ("271108898", "MAEU271108898"),  # al revés
        ("MAEU271108898", "MAEU271108898"),  # exacto
        ("020-50685434", "02050685434"),  # la guía aérea, como antes
    ],
)
def test_encuentra_el_embarque_con_o_sin_el_codigo_de_la_naviera(en_trackin, en_shipsgo) -> None:
    indice = {en_shipsgo.replace("-", ""): (7, False)}

    assert buscar(indice, en_trackin) == (7, False)


def test_un_contenedor_no_se_confunde_sin_sus_letras() -> None:
    """Cuatro letras y siete dígitos: las letras son parte del número (ISO 6346)."""
    assert buscar({"8132490": (7, False)}, "MRSU8132490") is None
    assert buscar({"MRSU8132490": (7, False)}, "MSCU8132490") is None


def test_lo_que_no_esta_no_se_encuentra() -> None:
    assert buscar({"271102440": (7, False)}, "MAEU71108898") is None
    assert buscar({}, None) is None


# --- Limpiar «BL» y avisar antes de gastar ------------------------------------------------


@pytest.mark.parametrize("escrito", ["BLMAEU274029064", "BL MAEU274029064", "B/L-MAEU274029064"])
def test_el_bl_de_mas_delante_se_quita(escrito) -> None:
    resultado = validar_referencia("BL", escrito, "MARITIMO")

    assert resultado.valida
    assert resultado.numero == "MAEU274029064"


def test_un_bl_que_empieza_con_bl_de_verdad_no_se_toca() -> None:
    assert validar_referencia("BL", "BLX12345678", "MARITIMO").numero == "BLX12345678"


@pytest.mark.parametrize(
    ("numero", "dice"),
    [
        ("BLMAEU274029064", "Empieza con «BL»"),
        ("MAEU71108898", "9 dígitos después de MAEU; este tiene 8"),
        ("AB123", "Es corto para un BL"),
    ],
)
def test_avisa_lo_que_conviene_revisar_antes_del_alta(numero, dice) -> None:
    aviso = advertencia_referencia("BL", numero)

    assert aviso is not None and dice in aviso


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [("BL", "MAEU271108898"), ("BL", "COSU6508789000"), ("CONTENEDOR", "MRSU8132490")],
)
def test_una_referencia_normal_no_lleva_aviso(tipo, numero) -> None:
    assert advertencia_referencia(tipo, numero) is None


# --- Corregir la referencia de un pedido ----------------------------------------------------


async def _con_bl(sesion, numero: str = "BLMAEU274029064"):
    elemento = ElementoRastreado(
        tipo_tracking_externo="BL", tracking_externo=numero, via_transporte="MARITIMO"
    )
    sesion.add(elemento)
    await sesion.flush()
    pedido = await base._pedido(
        sesion,
        id_elemento_rastreado=elemento.id,
        etapa_viaje="EN_ORIGEN",
        estado_calculado="EN_ORIGEN",
    )
    return pedido, elemento


async def test_corrige_el_bl_conservando_el_tramo_del_equivocado(api, sesion) -> None:
    cliente, _ = api
    pedido, equivocado = await _con_bl(sesion)

    respuesta = await cliente.put(
        _url(pedido, "referencia"), json={"tipo": "BL", "numero": "MAEU274029064"}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["rastreo"]["referencia"] == "MAEU274029064"
    tramos = list(
        await sesion.scalars(
            select(PedidoElementoRastreado)
            .where(PedidoElementoRastreado.id_pedido == pedido.id)
            .order_by(PedidoElementoRastreado.tramo)
        )
    )
    assert [(t.id_elemento_rastreado == equivocado.id, t.fecha_hasta is None) for t in tramos] == [
        (True, False),
        (False, True),
    ]
    asiento = await sesion.scalar(
        select(AuditoriaIntervencion)
        .where(AuditoriaIntervencion.id_pedido == pedido.id)
        .order_by(AuditoriaIntervencion.id.desc())
        .limit(1)
    )
    assert asiento is not None
    assert (asiento.tipo_intervencion, asiento.valor_anterior, asiento.valor_nuevo) == (
        "ASOCIACION_TRACKING",
        "BL:BLMAEU274029064",
        "BL:MAEU274029064",
    )
    assert asiento.motivo == intervenciones.MOTIVO_CORRECCION_POR_OMISION


async def test_la_correccion_tambien_limpia_el_bl_de_mas(api, sesion) -> None:
    cliente, _ = api
    pedido, _ = await _con_bl(sesion, "MAEU71108898")

    respuesta = await cliente.put(
        _url(pedido, "referencia"), json={"tipo": "BL", "numero": "BLMAEU271108898"}
    )

    assert respuesta.json()["rastreo"]["referencia"] == "MAEU271108898"


async def test_la_misma_referencia_no_es_una_correccion(api, sesion) -> None:
    cliente, _ = api
    pedido, _ = await _con_bl(sesion, "MAEU274029064")

    respuesta = await cliente.put(
        _url(pedido, "referencia"), json={"tipo": "BL", "numero": "MAEU274029064"}
    )

    assert respuesta.status_code == 409
    assert "ya tiene esa referencia" in respuesta.json()["detail"]


async def test_una_referencia_invalida_no_cierra_ningun_tramo(api, sesion) -> None:
    cliente, _ = api
    pedido, _ = await _con_bl(sesion)

    # Un contenedor con el dígito de control equivocado.
    respuesta = await cliente.put(
        _url(pedido, "referencia"), json={"tipo": "CONTENEDOR", "numero": "MRSU8132491"}
    )

    assert respuesta.status_code == 422
    assert (
        await sesion.scalar(
            select(PedidoElementoRastreado).where(PedidoElementoRastreado.id_pedido == pedido.id)
        )
        is None
    )


async def test_sin_referencia_se_asocia_en_lugar_de_corregir(api, sesion) -> None:
    cliente, _ = api
    pedido = await base._pedido(sesion)

    respuesta = await cliente.put(
        _url(pedido, "referencia"), json={"tipo": "BL", "numero": "MAEU274029064"}
    )

    assert respuesta.status_code == 409
    assert "asóciela" in respuesta.json()["detail"]


@pytest.mark.parametrize(("rol", "esperado"), [("COMPRAS", 200), ("PLANIFICACION", 403)])
async def test_la_corrigen_quienes_asocian_referencias(api, sesion, rol, esperado) -> None:
    cliente, como = api
    await como(rol)
    pedido, _ = await _con_bl(sesion)

    respuesta = await cliente.put(
        _url(pedido, "referencia"), json={"tipo": "BL", "numero": "MAEU274029064"}
    )

    assert respuesta.status_code == esperado
