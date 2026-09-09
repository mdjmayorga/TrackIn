"""Pruebas de `app.services.ingesta.carga` — `TASK-03` / RF-01, RN-17.

Casi todas tocan la base: el módulo existe para escribir en ella, y probarlo
con dobles solo verificaría que las llamadas se hacen, no que la fila entra sin
violar un `CHECK`. Van marcadas `integration` y corren dentro de la transacción
que la fixture `sesion` revierte.

La propiedad central es la de RN-17: **una línea mala no aborta el lote**.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import delete, select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services.ingesta.carga import (
    RECHAZO_SIN_DESTINO,
    RECHAZO_SIN_VIA,
    LineaRechazada,
    ResultadoCarga,
    cargar,
    cargar_pedido,
    generar_tracking_interno,
    resolver_destino,
)
from app.services.ingesta.dto import PedidoCrudo
from app.services.ingesta.semilla import PEDIDOS_SEMILLA, FuenteSemilla


def _crudo(**kwargs) -> PedidoCrudo:
    """Una línea limpia, para variarle solo lo que cada prueba estudia."""
    base = {
        "oc_numero": "4599999999",
        "posicion_oc": 10,
        "proveedor_codigo": "P-TEST-1",
        "proveedor_nombre": "Proveedor de prueba",
        "material_codigo": "M-TEST-1",
        "material_descripcion": "Material de prueba",
        "cantidad": 100.0,
        "unidad_medida": "KG",
        "fecha_entrega_pedido": dt.date(2026, 10, 1),
        "destino_codigo": "CRMOB",
        "via_transporte": "MARITIMO",
        "pais_origen": "BRASIL",
        "incoterm": "CIF LIMON",
        "temperatura": "Ambiente",
    }
    return PedidoCrudo(**{**base, **kwargs})


class FuenteFalsa:
    """Fuente de mentira que entrega exactamente lo que se le da."""

    nombre = "prueba"
    descripcion = "Fuente de prueba"

    def __init__(self, pedidos: list[PedidoCrudo]) -> None:
        self._pedidos = pedidos

    async def obtener_pedidos(self) -> list[PedidoCrudo]:
        return list(self._pedidos)


# --- El código interno -----------------------------------------------------


def test_el_tracking_interno_se_deriva_de_la_clave_natural() -> None:
    assert generar_tracking_interno("4500016171", 10) == "TRK-4500016171-010"


def test_el_tracking_interno_es_estable() -> None:
    """Se deriva, no se correlativa: el código que alguien apuntó en un correo
    sigue sirviendo después de reconstruir la base."""
    assert generar_tracking_interno("4500016171", 10) == generar_tracking_interno("4500016171", 10)


def test_el_tracking_interno_cabe_en_la_columna() -> None:
    """`VARCHAR(30)`. Con OC de 20 caracteres seguiría entrando."""
    assert len(generar_tracking_interno("4" * 20, 999)) <= 30


# --- El resultado del lote -------------------------------------------------


def test_el_resultado_cuadra_las_cuentas() -> None:
    resultado = ResultadoCarga(
        cargados=6,
        omitidos=1,
        rechazadas=[LineaRechazada("450", 10, RECHAZO_SIN_VIA, "sin vía")],
        rastreables=0,
        sin_rastreo_hoy=4,
    )
    assert resultado.leidas == 8
    assert resultado.sin_tracking == 2


def test_la_linea_rechazada_se_lee_sola() -> None:
    """Se imprime tal cual en el informe del script."""
    linea = LineaRechazada("4500019233", 20, RECHAZO_SIN_VIA, "la vía 'PENDIENTE' no es una vía")
    assert str(linea) == "4500019233-20: la vía 'PENDIENTE' no es una vía"


# --- Resolución del destino ------------------------------------------------


@pytest.mark.integration
class TestResolverDestino:
    async def test_por_codigo(self, sesion) -> None:
        destino, motivo = await resolver_destino(sesion, "CRMOB", "MARITIMO")
        assert destino is not None and destino.codigo == "CRMOB"
        assert motivo == "codigo"

    async def test_un_codigo_que_no_existe_no_se_inventa(self, sesion) -> None:
        destino, motivo = await resolver_destino(sesion, "XXXXX", "MARITIMO")
        assert destino is None
        assert "no está en el maestro" in motivo

    async def test_se_infiere_cuando_la_via_tiene_un_solo_destino(self, sesion) -> None:
        """Hay un aeropuerto. El DTO contempla esta inferencia explícitamente."""
        destino, motivo = await resolver_destino(sesion, None, "AEREO")
        assert destino is not None and destino.via_transporte == "AEREO"
        assert motivo == "inferido de la vía"

    async def test_no_se_adivina_entre_varios_puertos(self, sesion) -> None:
        """Caldera es Pacífico y Moín es Caribe: colocar un buque en el océano
        equivocado estropea la geocerca y el ETA sin que nada falle a la vista."""
        destino, motivo = await resolver_destino(sesion, None, "MARITIMO")
        assert destino is None
        assert "no se adivina" in motivo

    async def test_una_via_sin_destinos_no_resuelve(self, sesion) -> None:
        destino, motivo = await resolver_destino(sesion, None, "TERRESTRE")
        assert destino is None
        assert "no tiene ninguno" in motivo

    async def test_sin_via_ni_codigo_no_hay_nada_que_hacer(self, sesion) -> None:
        destino, motivo = await resolver_destino(sesion, None, None)
        assert destino is None
        assert "tampoco se pudo resolver" in motivo


# --- Carga de una línea ----------------------------------------------------


@pytest.mark.integration
class TestCargarPedido:
    async def test_una_linea_limpia_entra(self, sesion) -> None:
        pedido, estado, _ = await cargar_pedido(sesion, _crudo())

        assert estado == "cargado"
        assert pedido is not None
        assert pedido.tracking_interno == "TRK-4599999999-010"
        assert pedido.etapa_viaje == "SIN_TRACKING"

    async def test_los_campos_sucios_se_normalizan(self, sesion) -> None:
        """RN-17 sobre los defectos reales de la muestra del 03/09."""
        pedido, _, _ = await cargar_pedido(
            sesion, _crudo(incoterm="Exw", temperatura="Entre 2°-8° C", pais_origen="USA")
        )

        assert pedido is not None
        assert pedido.incoterm == "EXW"  # se descarta el lugar convenido
        assert pedido.temperatura == "2-8 C"
        assert pedido.id_pais_origen is not None  # `USA` resolvió por alias

    async def test_dos_grafias_del_mismo_pais_dan_el_mismo_id(self, sesion) -> None:
        """`USA` y `ESTADOS UNIDOS` conviven en el archivo real."""
        uno, _, _ = await cargar_pedido(sesion, _crudo(oc_numero="4599999001", pais_origen="USA"))
        otro, _, _ = await cargar_pedido(
            sesion, _crudo(oc_numero="4599999002", pais_origen="ESTADOS UNIDOS")
        )

        assert uno is not None and otro is not None
        assert uno.id_pais_origen == otro.id_pais_origen

    async def test_el_lead_time_se_copia_del_destino(self, sesion) -> None:
        """Desnormalizado a propósito: editar el maestro no puede reescribir un
        desglose ya calculado (RF-05)."""
        pedido, _, _ = await cargar_pedido(sesion, _crudo())
        assert pedido is not None
        destino, _ = await resolver_destino(sesion, "CRMOB", "MARITIMO")
        assert destino is not None
        assert pedido.lead_time_destino_dias == destino.lead_time_dias

    async def test_el_proveedor_y_el_material_se_crean_al_descubrirlos(self, sesion) -> None:
        """El archivo es hoy la única fuente de maestros."""
        await cargar_pedido(sesion, _crudo(proveedor_codigo="P-NUEVO", material_codigo="M-NUEVO"))

        assert await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-NUEVO"))
        assert await sesion.scalar(select(Material).where(Material.codigo == "M-NUEVO"))

    async def test_el_proveedor_no_se_duplica_entre_lineas(self, sesion) -> None:
        """Varias líneas de la misma OC comparten proveedor."""
        await cargar_pedido(sesion, _crudo(oc_numero="4599999001"))
        await cargar_pedido(sesion, _crudo(oc_numero="4599999002"))

        proveedores = list(
            await sesion.scalars(select(Proveedor).where(Proveedor.codigo == "P-TEST-1"))
        )
        assert len(proveedores) == 1

    async def test_una_linea_ya_cargada_se_omite(self, sesion) -> None:
        """Idempotencia por clave natural: correr el cargador dos veces es seguro."""
        await cargar_pedido(sesion, _crudo())
        pedido, estado, _ = await cargar_pedido(sesion, _crudo())

        assert estado == "omitido"
        assert pedido is not None

    async def test_sin_via_se_rechaza_con_motivo(self, sesion) -> None:
        pedido, estado, detalle = await cargar_pedido(sesion, _crudo(via_transporte="PENDIENTE"))

        assert pedido is None
        assert estado == RECHAZO_SIN_VIA
        assert "no es una vía de transporte" in detalle

    async def test_sin_destino_resoluble_se_rechaza_con_motivo(self, sesion) -> None:
        pedido, estado, detalle = await cargar_pedido(
            sesion, _crudo(destino_codigo=None, via_transporte="MARITIMO")
        )

        assert pedido is None
        assert estado == RECHAZO_SIN_DESTINO
        assert "no se adivina" in detalle

    async def test_el_maestro_manda_sobre_la_via_del_archivo(self, sesion) -> None:
        """El destino es dato verificado; la columna del archivo es texto libre."""
        pedido, _, _ = await cargar_pedido(
            sesion, _crudo(destino_codigo="MROC", via_transporte="MARITIMO")
        )
        assert pedido is not None
        assert pedido.via_transporte == "AEREO"


# --- El lote completo ------------------------------------------------------


@pytest.fixture
async def sin_pedidos(sesion):
    """Deja `pedidos_transito` vacía **dentro de la transacción de la prueba**.

    Hace falta porque el entorno de desarrollo tiene la semilla ya cargada y
    *commiteada* —para eso existe el script—, así que una prueba que contara
    filas absolutas mediría lo que dejó la última demostración. El borrado se
    revierte al terminar y los datos vuelven intactos.

    El orden importa: el pedido apunta al elemento rastreado.
    """
    await sesion.execute(delete(PedidoTransito))
    await sesion.execute(delete(ElementoRastreado))
    await sesion.flush()
    return sesion


@pytest.mark.integration
class TestCargarLote:
    async def test_la_semilla_entera_se_carga(self, sesion, sin_pedidos) -> None:
        """El caso que se demuestra: 8 líneas, 6 entran y 2 quedan a la vista."""
        resultado = await cargar(sesion, FuenteSemilla())

        assert resultado.leidas == len(PEDIDOS_SEMILLA) == 8
        assert resultado.cargados == 6
        assert len(resultado.rechazadas) == 2

    async def test_las_dos_rechazadas_son_las_sucias_y_dicen_por_que(
        self, sesion, sin_pedidos
    ) -> None:
        resultado = await cargar(sesion, FuenteSemilla())

        motivos = {(r.oc_numero, r.motivo) for r in resultado.rechazadas}
        assert ("4500019110", RECHAZO_SIN_DESTINO) in motivos  # terrestre, sin puerto
        assert ("4500019233", RECHAZO_SIN_VIA) in motivos  # vía `PENDIENTE`
        assert all(r.detalle for r in resultado.rechazadas)

    async def test_una_linea_mala_no_impide_las_buenas(self, sesion, sin_pedidos) -> None:
        """La propiedad central de RN-17, aislada: la basura va en medio."""
        resultado = await cargar(
            sesion,
            FuenteFalsa(
                [
                    _crudo(oc_numero="4599999001"),
                    _crudo(oc_numero="4599999002", via_transporte="PEDIENTE"),
                    _crudo(oc_numero="4599999003"),
                ]
            ),
        )

        assert resultado.cargados == 2
        assert len(resultado.rechazadas) == 1

    async def test_ninguna_referencia_de_la_semilla_es_rastreable_hoy(
        self, sesion, sin_pedidos
    ) -> None:
        """Con Vizion y Portcast aprobados pero **sin contratar**, las cuatro
        referencias son válidas y ninguna se puede seguir. Es el hallazgo que
        `US-01` dejó anotado, y esta prueba lo fija hasta que se contraten."""
        resultado = await cargar(sesion, FuenteSemilla())

        assert resultado.rastreables == 0
        assert resultado.sin_rastreo_hoy == 4
        assert resultado.sin_tracking == 2

    async def test_las_lineas_con_referencia_salen_de_sin_tracking(
        self, sesion, sin_pedidos
    ) -> None:
        """RN-02 por `CHECK`: hay elemento asociado si y solo si la etapa no es
        `SIN_TRACKING`. Una referencia válida mueve la etapa a `EN_ORIGEN`."""
        await cargar(sesion, FuenteSemilla())

        con_elemento = list(
            await sesion.scalars(
                select(PedidoTransito).where(PedidoTransito.id_elemento_rastreado.isnot(None))
            )
        )
        assert len(con_elemento) == 4
        assert all(p.etapa_viaje == "EN_ORIGEN" for p in con_elemento)

    async def test_recargar_no_duplica(self, sesion, sin_pedidos) -> None:
        """Lo que hace seguro correr el script antes de una demostración."""
        primera = await cargar(sesion, FuenteSemilla())
        segunda = await cargar(sesion, FuenteSemilla())

        assert segunda.cargados == 0
        assert segunda.omitidos == primera.cargados

    async def test_un_lote_vacio_no_falla(self, sesion, sin_pedidos) -> None:
        resultado = await cargar(sesion, FuenteFalsa([]))
        assert resultado.leidas == 0

    async def test_una_referencia_gratuita_si_cuenta_como_rastreable(
        self, sesion, sin_pedidos
    ) -> None:
        """El contraste con la prueba anterior, y la rama que se encenderá
        cuando se contraten los proveedores.

        Un MMSI se sigue **hoy** por AISStream, que es gratuita; un contenedor
        necesita Vizion, que está aprobado pero sin contratar. La diferencia no
        es el formato de la referencia sino si existe una fuente que la siga.
        """
        resultado = await cargar(
            sesion,
            FuenteFalsa([_crudo(tipo_referencia="MMSI", numero_referencia="311001711")]),
        )

        assert resultado.cargados == 1
        assert resultado.rastreables == 1
        assert resultado.sin_rastreo_hoy == 0
