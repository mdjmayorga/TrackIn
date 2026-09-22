"""Pruebas de `app.services.ingesta.carga` — `TASK-03` / RF-01, RN-17.

Casi todas tocan la base: el módulo existe para escribir en ella, y probarlo
con dobles solo verificaría que las llamadas se hacen, no que la fila entra sin
violar un `CHECK`. Van marcadas `integration` y corren dentro de la transacción
que la fixture `sesion` revierte.

La propiedad central es la de RN-17: **una línea mala no aborta el lote**.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.material import Material
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services.ingesta.carga import (
    RECHAZO_REFERENCIA_INVALIDA,
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
from app.services.ingesta.informe import construir_informe
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
        sin_cambios=1,
        rechazadas=[LineaRechazada("450", 10, RECHAZO_SIN_VIA, "sin vía")],
        rastreables=0,
        sin_rastreo_hoy=4,
    )
    assert resultado.leidas == 8
    assert resultado.sin_tracking == 2
    assert resultado.omitidos == 1


def test_las_recibidas_suman_todos_los_destinos_posibles() -> None:
    """`US-31`, tercer criterio: ninguna línea del archivo puede perderse entre
    las categorías del informe."""
    resultado = ResultadoCarga(
        cargados=3,
        actualizados=2,
        sin_cambios=4,
        cerrados_omitidos=1,
        rechazadas=[LineaRechazada("450", 10, RECHAZO_SIN_VIA, "sin vía")],
    )
    assert resultado.leidas == 11


def test_el_resumen_trae_los_cuatro_numeros_del_criterio() -> None:
    resultado = ResultadoCarga(cargados=3, actualizados=2, ausentes=[("450", 10)])
    resumen = resultado.resumen()
    for parte in ("5 recibidas", "3 insertadas", "2 actualizadas", "0 rechazadas", "1 ausentes"):
        assert parte in resumen


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

    async def test_una_linea_ya_cargada_no_se_duplica(self, sesion) -> None:
        """Idempotencia por clave natural: correr el cargador dos veces es seguro.

        Desde `US-31` el estado es `sin_cambios` y no `omitido`: la línea **sí**
        se vuelve a evaluar contra el archivo, y resulta que no cambia nada.
        Distinguirlo de `actualizado` es lo que informa el tercer criterio.
        """
        await cargar_pedido(sesion, _crudo())
        pedido, estado, _ = await cargar_pedido(sesion, _crudo())

        assert estado == "sin_cambios"
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


# --- Actualización de lo existente — US-31, primer criterio -----------------


@pytest.mark.integration
class TestActualizar:
    """*«Los pedidos nuevos se insertan y los existentes se actualizan por OC
    y posición»*. Lo delicado no es actualizar, es **no** actualizar de más."""

    async def test_lo_que_el_archivo_manda_se_actualiza(self, sesion, sin_pedidos) -> None:
        await cargar(sesion, FuenteFalsa([_crudo(cantidad=100.0)]), señalar_ausentes=False)

        resultado = await cargar(
            sesion,
            FuenteFalsa([_crudo(cantidad=250.0, fecha_entrega_pedido=dt.date(2026, 12, 1))]),
            señalar_ausentes=False,
        )

        assert resultado.cargados == 0
        assert resultado.actualizados == 1
        pedido = await sesion.scalar(select(PedidoTransito))
        assert pedido.cantidad_pedida == Decimal("250.000")
        assert pedido.fecha_entrega_pedido == dt.date(2026, 12, 1)

    async def test_recargar_lo_mismo_no_cuenta_como_actualizacion(
        self, sesion, sin_pedidos
    ) -> None:
        """Distinguir «actualizado» de «sin cambios» es lo que permite ver de un
        vistazo si una carga movió algo."""
        await cargar(sesion, FuenteFalsa([_crudo()]), señalar_ausentes=False)
        resultado = await cargar(sesion, FuenteFalsa([_crudo()]), señalar_ausentes=False)

        assert resultado.actualizados == 0
        assert resultado.sin_cambios == 1

    async def test_no_pisa_el_estado_calculado_ni_lo_confirmado_a_mano(
        self, sesion, sin_pedidos
    ) -> None:
        """El archivo no sabe nada del motor de cálculo ni de lo que confirmó
        una persona. Un `INSERT ... ON CONFLICT DO UPDATE` ingenuo lo borraría.

        La línea lleva referencia porque RN-02 lo exige: sin elemento rastreado,
        `ck_pedidos_transito_sin_tracking` prohíbe salir de `SIN_TRACKING`.
        """
        con_referencia = _crudo(tipo_referencia="MMSI", numero_referencia="311001711")
        await cargar(sesion, FuenteFalsa([con_referencia]), señalar_ausentes=False)
        pedido = await sesion.scalar(select(PedidoTransito))
        pedido.etapa_viaje = "EN_TRANSITO"
        pedido.estado_calculado = "EN_RIESGO"
        pedido.ata_confirmada = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
        pedido.ajuste_manual_dias = 3
        await sesion.flush()
        elemento_antes = pedido.id_elemento_rastreado

        await cargar(
            sesion,
            FuenteFalsa([_crudo(cantidad=999.0)]),  # el archivo ya no trae la referencia
            señalar_ausentes=False,
        )

        await sesion.refresh(pedido)
        assert pedido.cantidad_pedida == Decimal("999.000")  # sí cambió
        assert pedido.etapa_viaje == "EN_TRANSITO"
        assert pedido.estado_calculado == "EN_RIESGO"
        assert pedido.ata_confirmada is not None
        assert pedido.ajuste_manual_dias == 3
        # Que el archivo deje de traer la referencia no desasocia el rastreo.
        assert pedido.id_elemento_rastreado == elemento_antes

    async def test_un_pedido_cerrado_se_deja_intacto(self, sesion, sin_pedidos) -> None:
        """RN-13. Que reaparezca en el archivo se revisa a mano: el cargador no
        reabre nada por su cuenta."""
        await cargar(sesion, FuenteFalsa([_crudo()]), señalar_ausentes=False)
        pedido = await sesion.scalar(select(PedidoTransito))
        pedido.motivo_cierre = "CIERRE_FORZADO"
        pedido.estado_calculado = "CERRADO"
        await sesion.flush()

        resultado = await cargar(
            sesion, FuenteFalsa([_crudo(cantidad=999.0)]), señalar_ausentes=False
        )

        assert resultado.cerrados_omitidos == 1
        assert resultado.actualizados == 0
        await sesion.refresh(pedido)
        assert pedido.cantidad_pedida != Decimal("999.000")

    async def test_la_carga_deja_fecha_de_ultima_carga(self, sesion, sin_pedidos) -> None:
        await cargar(sesion, FuenteFalsa([_crudo()]), señalar_ausentes=False)
        pedido = await sesion.scalar(select(PedidoTransito))
        assert pedido.fecha_ultima_carga is not None
        assert pedido.ausente_desde is None


# --- Ausencias — US-31, segundo criterio -----------------------------------


@pytest.mark.integration
class TestAusentes:
    """*«Un pedido que ya no figura en el archivo se señala para revisión
    manual y NO se elimina»*."""

    async def test_lo_que_no_viene_se_marca_y_no_se_borra(self, sesion, sin_pedidos) -> None:
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10), _crudo(posicion_oc=20)]))

        resultado = await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10)]))

        assert resultado.ausentes == [("4599999999", 20)]
        # Sigue existiendo: lo que se pierde al borrar es su historial (RNF-13).
        sobreviviente = await sesion.scalar(
            select(PedidoTransito).where(PedidoTransito.posicion_oc == 20)
        )
        assert sobreviviente is not None
        assert sobreviviente.ausente_desde is not None

    async def test_la_marca_no_se_reescribe_en_cada_carga(self, sesion, sin_pedidos) -> None:
        """Si se reescribiera, se perdería *desde cuándo* falta — que es la
        diferencia entre investigar y archivar."""
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10), _crudo(posicion_oc=20)]))
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10)]))
        pedido = await sesion.scalar(select(PedidoTransito).where(PedidoTransito.posicion_oc == 20))
        primera_marca = pedido.ausente_desde

        segunda = await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10)]))

        assert segunda.ausentes == []
        await sesion.refresh(pedido)
        assert pedido.ausente_desde == primera_marca

    async def test_si_vuelve_a_aparecer_se_limpia_la_marca(self, sesion, sin_pedidos) -> None:
        """Una línea que va y viene es un síntoma del archivo, no del pedido."""
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10), _crudo(posicion_oc=20)]))
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10)]))

        resultado = await cargar(
            sesion, FuenteFalsa([_crudo(posicion_oc=10), _crudo(posicion_oc=20)])
        )

        assert resultado.reaparecidos == 1
        pedido = await sesion.scalar(select(PedidoTransito).where(PedidoTransito.posicion_oc == 20))
        assert pedido.ausente_desde is None

    async def test_un_cerrado_que_falta_no_se_marca(self, sesion, sin_pedidos) -> None:
        """Ya no se le espera en el archivo: marcarlo sería ruido en la bandeja."""
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10), _crudo(posicion_oc=20)]))
        cerrado = await sesion.scalar(
            select(PedidoTransito).where(PedidoTransito.posicion_oc == 20)
        )
        cerrado.motivo_cierre = "RECEPCION_CONFORME"
        cerrado.estado_calculado = "CERRADO"
        cerrado.fecha_recepcion_planta = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
        cerrado.cantidad_recibida = Decimal("100.000")
        await sesion.flush()

        resultado = await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10)]))

        assert resultado.ausentes == []
        await sesion.refresh(cerrado)
        assert cerrado.ausente_desde is None

    async def test_se_puede_desactivar_para_cargas_parciales(self, sesion, sin_pedidos) -> None:
        """Un archivo que no es el universo completo marcaría media base."""
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10), _crudo(posicion_oc=20)]))

        resultado = await cargar(
            sesion, FuenteFalsa([_crudo(posicion_oc=10)]), señalar_ausentes=False
        )

        assert resultado.ausentes == []

    async def test_una_linea_rechazada_no_marca_ausente_lo_que_si_vino(
        self, sesion, sin_pedidos
    ) -> None:
        """La línea estaba en el archivo aunque no se pudiera persistir: es un
        rechazo, no una ausencia, y confundirlos duplicaría el aviso."""
        await cargar(sesion, FuenteFalsa([_crudo(posicion_oc=10)]))

        resultado = await cargar(
            sesion, FuenteFalsa([_crudo(posicion_oc=10, via_transporte="PENDIENTE")])
        )

        assert len(resultado.rechazadas) == 1
        assert resultado.ausentes == [("4599999999", 10)]


# --- Referencias inválidas — US-32, quinto y sexto criterio ----------------


@pytest.mark.integration
class TestReferenciaInvalida:
    """Una referencia mala **no** impide que el pedido entre (RN-17), pero
    tampoco puede desaparecer del informe: hasta `US-32` no se contaba en
    ninguna parte."""

    async def test_el_pedido_entra_aunque_la_referencia_no_sirva(self, sesion, sin_pedidos) -> None:
        resultado = await cargar(
            sesion,
            # `MSCU1234567`: formato correcto, dígito verificador equivocado.
            FuenteFalsa([_crudo(tipo_referencia="CONTENEDOR", numero_referencia="MSCU1234567")]),
            señalar_ausentes=False,
        )

        assert resultado.cargados == 1
        assert len(resultado.rechazadas) == 0  # la línea no se rechaza
        pedido = await sesion.scalar(select(PedidoTransito))
        assert pedido is not None
        assert pedido.etapa_viaje == "SIN_TRACKING"  # RN-02: no se asoció nada
        assert pedido.id_elemento_rastreado is None

    async def test_la_referencia_mala_queda_en_el_informe_con_su_clave(
        self, sesion, sin_pedidos
    ) -> None:
        """Lo que se gana: el número mal transcrito se puede ir a corregir."""
        resultado = await cargar(
            sesion,
            FuenteFalsa([_crudo(tipo_referencia="CONTENEDOR", numero_referencia="MSCU1234567")]),
            señalar_ausentes=False,
        )

        (invalida,) = resultado.referencias_invalidas
        assert (invalida.oc_numero, invalida.posicion_oc) == ("4599999999", 10)
        assert invalida.motivo == RECHAZO_REFERENCIA_INVALIDA
        assert "dígito verificador" in invalida.detalle

    async def test_no_se_cuenta_ni_como_rastreable_ni_como_sin_rastreo_hoy(
        self, sesion, sin_pedidos
    ) -> None:
        """Son tres cosas distintas: se sigue hoy, se seguiría con créditos, y
        no se seguirá nunca porque el número está mal."""
        resultado = await cargar(
            sesion,
            FuenteFalsa([_crudo(tipo_referencia="CONTENEDOR", numero_referencia="MSCU1234567")]),
            señalar_ausentes=False,
        )

        assert resultado.rastreables == 0
        assert resultado.sin_rastreo_hoy == 0
        assert len(resultado.referencias_invalidas) == 1

    async def test_un_contenedor_bien_transcrito_si_se_asocia(self, sesion, sin_pedidos) -> None:
        """El contraste: mismo tipo, mismo formato, dígito correcto."""
        resultado = await cargar(
            sesion,
            FuenteFalsa([_crudo(tipo_referencia="CONTENEDOR", numero_referencia="MSCU1234566")]),
            señalar_ausentes=False,
        )

        assert resultado.referencias_invalidas == []
        # ShipsGo aún no tiene créditos: válida, pero no rastreable hoy.
        assert resultado.sin_rastreo_hoy == 1
        pedido = await sesion.scalar(select(PedidoTransito))
        assert pedido is not None
        assert pedido.id_elemento_rastreado is not None

    async def test_el_informe_la_marca_como_entro_sin_rastreo(self, sesion, sin_pedidos) -> None:
        """La distinción que necesita quien lee: hay un pedido en la base, lo
        que falta es poder seguirlo."""
        resultado = await cargar(
            sesion,
            FuenteFalsa([_crudo(tipo_referencia="CONTENEDOR", numero_referencia="MSCU1234567")]),
            señalar_ausentes=False,
        )

        informe = construir_informe("prueba", resultado)

        assert informe.no_entraron == 0
        assert informe.entraron_sin_rastreo == 1
