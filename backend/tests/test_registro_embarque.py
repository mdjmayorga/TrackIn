"""Pruebas de `app.services.rastreo.registro_embarque` — `US-45` / RF-14.

Lo que se fija aquí es **lo que cuesta dinero**: cuándo se gasta un crédito,
cuándo no, y que el gasto quede con dueño.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.services.rastreo import registro_embarque
from app.services.rastreo.shipsgo_aerolineas import CatalogoAerolineas
from app.services.rastreo.shipsgo_cliente import ClienteShipsGo, Respuesta

pytestmark = pytest.mark.integration

#: Contenedor con dígito verificador correcto, del spike.
CONTENEDOR_BUENO = "MRSU8507472"
#: Mismo formato, dígito equivocado.
CONTENEDOR_MALO = "MSCU1234567"


@dataclass
class TransporteFalso:
    respuestas: list[Respuesta]
    llamadas: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)

    async def __call__(
        self,
        metodo: str,
        url: str,
        *,
        cabeceras: dict[str, str],
        cuerpo: dict[str, Any] | None = None,
    ) -> Respuesta:
        self.llamadas.append((metodo, url, cuerpo))
        return self.respuestas.pop(0)


def _cliente(*respuestas: Respuesta) -> tuple[ClienteShipsGo, TransporteFalso]:
    transporte = TransporteFalso(list(respuestas))
    return ClienteShipsGo(transporte, token="t"), transporte


@pytest.fixture
async def pedido(sesion) -> PedidoTransito:
    destino = await sesion.scalar(select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB"))
    assert destino is not None
    proveedor = Proveedor(codigo="P-SG-1", nombre="Proveedor")
    material = Material(codigo="M-SG-1", descripcion="Material", unidad_medida="KG")
    sesion.add_all([proveedor, material])
    await sesion.flush()

    nuevo = PedidoTransito(
        oc_numero="4566666666",
        posicion_oc=10,
        tracking_interno="TRK-4566666666-010",
        id_proveedor=proveedor.id,
        id_material=material.id,
        id_destino=destino.id,
        via_transporte="MARITIMO",
        cantidad_pedida=Decimal("1.000"),
        unidad_medida="KG",
        fecha_entrega_pedido=dt.date(2026, 10, 10),
        lead_time_destino_dias=destino.lead_time_dias,
        etapa_viaje="SIN_TRACKING",
        estado_calculado="SIN_TRACKING",
    )
    sesion.add(nuevo)
    await sesion.flush()
    return nuevo


@pytest.fixture
async def usuario(sesion) -> Usuario:
    nuevo = await sesion.scalar(select(Usuario).limit(1))
    if nuevo is None:
        nuevo = Usuario(
            usuario="tester-sg",
            nombre_completo="Tester ShipsGo",
            correo="tester-sg@example.com",
            hash_contrasena="x",
            rol="LOGISTICA",
        )
        sesion.add(nuevo)
        await sesion.flush()
    return nuevo


# --- Las guardas que evitan gastar -----------------------------------------


async def test_una_referencia_con_digito_malo_no_gasta_un_credito(sesion, pedido) -> None:
    """ShipsGo acepta y cobra cualquier cosa: la guarda es local.

    `XXXX0000000` devolvió `200 SUCCESS` y creó el embarque. La comprobación del
    dígito es lo único que separa una errata de una factura de 2 USD.
    """
    cliente, transporte = _cliente()

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "CONTENEDOR", CONTENEDOR_MALO
    )

    assert resultado.registrado is False
    assert resultado.motivo == registro_embarque.RECHAZO_REFERENCIA_INVALIDA
    assert transporte.llamadas == [], "no debe llegar a la red"


@pytest.mark.parametrize("tipo,numero", [("MMSI", "311001711"), ("VUELO", "LH507")])
async def test_no_se_paga_por_lo_que_una_fuente_gratuita_ya_sigue(
    sesion, pedido, tipo: str, numero: str
) -> None:
    """Un MMSI lo sigue AISStream gratis. Pagarlo sería tirar dinero."""
    cliente, transporte = _cliente()

    resultado = await registro_embarque.registrar(sesion, cliente, pedido, tipo, numero)

    assert resultado.registrado is False
    assert resultado.motivo == registro_embarque.RECHAZO_FUENTE_AJENA
    assert transporte.llamadas == []


# --- El alta y su auditoría ------------------------------------------------


async def test_el_alta_queda_auditada_como_asociacion_tracking(sesion, pedido, usuario) -> None:
    """RF-14, con el tipo del catálogo que `TASK-28` señaló."""
    cliente, _ = _cliente(Respuesta(200, {"id": 6734886}))

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "CONTENEDOR", CONTENEDOR_BUENO, id_usuario=usuario.id
    )
    await sesion.flush()

    assert resultado.registrado is True
    assert resultado.id_embarque == 6734886

    registro = await sesion.scalar(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert registro is not None
    assert registro.tipo_intervencion == registro_embarque.TIPO_INTERVENCION
    assert registro.valor_nuevo == "6734886"


async def test_la_auditoria_dice_si_costo(sesion, pedido, usuario) -> None:
    """Con ~750 USD al año hay que poder explicar línea por línea."""
    cliente, _ = _cliente(Respuesta(200, {"id": 1}))

    await registro_embarque.registrar(
        sesion, cliente, pedido, "CONTENEDOR", CONTENEDOR_BUENO, id_usuario=usuario.id
    )
    await sesion.flush()

    registro = await sesion.scalar(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert registro is not None
    assert "Consumió un crédito" in registro.motivo


async def test_un_409_se_audita_igual_pero_sin_costo(sesion, pedido, usuario) -> None:
    """Que saliera gratis es justo lo que alguien querrá comprobar después."""
    cliente, _ = _cliente(Respuesta(409, {"shipment": {"id": 42}}))

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "CONTENEDOR", CONTENEDOR_BUENO, id_usuario=usuario.id
    )
    await sesion.flush()

    assert resultado.consumio_credito is False
    registro = await sesion.scalar(
        select(AuditoriaIntervencion).where(AuditoriaIntervencion.id_pedido == pedido.id)
    )
    assert registro is not None
    assert "sin costo" in registro.motivo


async def test_sin_usuario_el_gasto_queda_en_el_log(sesion, pedido, caplog) -> None:
    """`US-42` todavía no existe, pero el cargo no puede quedar mudo."""
    import logging

    cliente, _ = _cliente(Respuesta(200, {"id": 1}))

    with caplog.at_level(logging.WARNING):
        resultado = await registro_embarque.registrar(
            sesion, cliente, pedido, "CONTENEDOR", CONTENEDOR_BUENO
        )

    assert resultado.registrado is True
    assert "sin usuario identificado" in caplog.text


async def test_la_referencia_se_normaliza_antes_de_pedirla(sesion, pedido) -> None:
    """Minúsculas y espacios del archivo no deben viajar al proveedor."""
    cliente, transporte = _cliente(Respuesta(200, {"id": 1}))

    await registro_embarque.registrar(sesion, cliente, pedido, " contenedor ", " mrsu 850747 2 ")

    assert transporte.llamadas[0][2] == {"container_number": CONTENEDOR_BUENO}


# --- La guarda aerea de US-46 ----------------------------------------------


def _catalogo_real() -> CatalogoAerolineas:
    ruta = Path(__file__).resolve().parents[1] / "scripts/spikes/task28/output"
    return CatalogoAerolineas.desde_payload(
        json.loads((ruta / "02b_shipsgo_airlines.json").read_text(encoding="utf-8"))
    )


MAWB_LUFTHANSA = "020-50685434"
#: Formato y digito verificador correctos, prefijo que nadie emite.
MAWB_SIN_AEROLINEA = "111-12345675"


async def test_un_prefijo_sin_cobertura_no_gasta_un_credito(sesion, pedido) -> None:
    """`US-46`: la comprobacion es **gratuita** y evita pagar por nada.

    Es la ventaja que la via maritima no tiene: alli hay que pagar el alta para
    averiguar si la naviera esta cubierta.
    """
    cliente, transporte = _cliente()

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "MAWB", MAWB_SIN_AEROLINEA, catalogo=_catalogo_real()
    )

    assert resultado.registrado is False
    assert resultado.motivo == registro_embarque.RECHAZO_AEROLINEA_SIN_COBERTURA
    assert transporte.llamadas == [], "no debe llegar a la red"


async def test_un_mawb_de_una_aerolinea_cubierta_si_se_da_de_alta(sesion, pedido) -> None:
    cliente, transporte = _cliente(Respuesta(200, {"id": 264179}))

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "MAWB", MAWB_LUFTHANSA, catalogo=_catalogo_real()
    )

    assert resultado.registrado is True
    assert resultado.id_embarque == 264179
    assert transporte.llamadas[0][1].endswith("/air/shipments")


async def test_sin_catalogo_el_alta_sigue_adelante(sesion, pedido) -> None:
    """Negar por «no pude comprobarlo» dejaria de rastrear envios validos
    porque fallo una consulta gratuita: el peor intercambio posible."""
    cliente, _ = _cliente(Respuesta(200, {"id": 1}))

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "MAWB", MAWB_LUFTHANSA, catalogo=CatalogoAerolineas([])
    )

    assert resultado.registrado is True


async def test_la_guarda_del_catalogo_no_afecta_al_maritimo(sesion, pedido) -> None:
    """Un contenedor no tiene prefijo de aerolinea que comprobar."""
    cliente, _ = _cliente(Respuesta(200, {"id": 1}))

    resultado = await registro_embarque.registrar(
        sesion, cliente, pedido, "CONTENEDOR", CONTENEDOR_BUENO, catalogo=_catalogo_real()
    )

    assert resultado.registrado is True
