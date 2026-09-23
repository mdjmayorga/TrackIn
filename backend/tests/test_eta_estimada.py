"""Pruebas de `app.services.eta_estimada` — `US-08` / RN-16.

El núcleo es aritmética y se prueba sin base; la parte que consulta PostGIS y
el parámetro va marcada `integration`.

Lo que se fija con más cuidado es **cuándo NO se estima**, porque es el criterio
que evita el fallo visible: una nave fondeada a 0,3 nudos daría una ETA de meses,
y una fecha absurda en la grilla se lee como un error del sistema.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models.elemento_rastreado import ElementoRastreado
from app.models.maestro_destino import MaestroDestino
from app.models.material import Material
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.services import eta_estimada, historial

DESDE = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
#: Una milla náutica en metros, para escribir los casos en unidades legibles.
MN = eta_estimada.METROS_POR_MILLA_NAUTICA


# --- El cálculo puro -------------------------------------------------------


def test_la_formula_es_distancia_entre_velocidad() -> None:
    """100 mn a 10 nudos son 10 horas."""
    resultado = eta_estimada.calcular(
        distancia_m=100 * MN, velocidad_nudos=10.0, desde=DESDE, velocidad_minima_nudos=1.0
    )

    assert resultado.horas == pytest.approx(10.0)
    assert resultado.eta == DESDE + dt.timedelta(hours=10)
    assert bool(resultado) is True


def test_acepta_la_velocidad_como_decimal() -> None:
    """`elementos_rastreados.velocidad_actual` es `NUMERIC`, no `float`."""
    resultado = eta_estimada.calcular(
        distancia_m=100 * MN,
        velocidad_nudos=Decimal("10.00"),
        desde=DESDE,
        velocidad_minima_nudos=Decimal("1.0"),
    )

    assert resultado.eta == DESDE + dt.timedelta(hours=10)


def test_conserva_los_insumos_para_poder_auditarlo() -> None:
    """Cuarto criterio: *«expone la distancia, la velocidad y la hora usadas»*."""
    resultado = eta_estimada.calcular(
        distancia_m=100 * MN, velocidad_nudos=10.0, desde=DESDE, velocidad_minima_nudos=1.0
    )

    assert resultado.distancia_m == pytest.approx(100 * MN)
    assert resultado.velocidad_nudos == 10.0
    assert resultado.desde == DESDE


def test_el_desglose_se_lee_solo() -> None:
    desglose = eta_estimada.calcular(
        distancia_m=100 * MN, velocidad_nudos=10.0, desde=DESDE, velocidad_minima_nudos=1.0
    ).desglose

    assert "100 mn" in desglose
    assert "10.0 nudos" in desglose
    assert "10.0 h" in desglose


# --- Cuándo NO se estima ---------------------------------------------------


def test_por_debajo_del_minimo_no_se_estima() -> None:
    """Segundo criterio. Una nave fondeada a 0,3 nudos daría una ETA de meses,
    y eso es peor que no dar ninguna: se lee como un error del sistema."""
    resultado = eta_estimada.calcular(
        distancia_m=1000 * MN, velocidad_nudos=0.3, desde=DESDE, velocidad_minima_nudos=1.0
    )

    assert resultado.eta is None
    assert bool(resultado) is False
    assert resultado.motivo == eta_estimada.DEMASIADO_LENTO
    # Pero conserva los insumos: sirve para explicar por qué no hay fecha.
    assert resultado.velocidad_nudos == 0.3


def test_justo_en_el_minimo_si_se_estima() -> None:
    """La frontera es `<`, no `<=`: a la velocidad mínima todavía se navega."""
    resultado = eta_estimada.calcular(
        distancia_m=10 * MN, velocidad_nudos=1.0, desde=DESDE, velocidad_minima_nudos=1.0
    )

    assert resultado.eta is not None


@pytest.mark.parametrize(
    ("distancia", "velocidad", "desde", "motivo"),
    [
        (100 * MN, 10.0, None, eta_estimada.SIN_POSICION),
        (None, 10.0, DESDE, eta_estimada.SIN_POSICION),
        (100 * MN, None, DESDE, eta_estimada.SIN_VELOCIDAD),
    ],
)
def test_sin_los_insumos_no_se_inventa_una_fecha(
    distancia: float | None, velocidad: float | None, desde: dt.datetime | None, motivo: str
) -> None:
    resultado = eta_estimada.calcular(
        distancia_m=distancia,
        velocidad_nudos=velocidad,
        desde=desde,
        velocidad_minima_nudos=1.0,
    )

    assert resultado.eta is None
    assert resultado.motivo == motivo


def test_el_desglose_explica_la_ausencia() -> None:
    desglose = eta_estimada.calcular(
        distancia_m=None, velocidad_nudos=None, desde=None, velocidad_minima_nudos=1.0
    ).desglose

    assert desglose.startswith("ETA no estimable:")


def test_el_resultado_no_se_retoca() -> None:
    """`frozen=True`: es evidencia del cálculo, no un borrador."""
    resultado = eta_estimada.calcular(
        distancia_m=100 * MN, velocidad_nudos=10.0, desde=DESDE, velocidad_minima_nudos=1.0
    )
    with pytest.raises(AttributeError):
        resultado.eta = DESDE  # type: ignore[misc]


# --- Contra la base y PostGIS ----------------------------------------------


@pytest.mark.integration
class TestEstimarContraLaBase:
    """Lo que solo la base puede decir: la distancia real y el parámetro."""

    async def _pedido(self, sesion, posicion=None, velocidad=None) -> PedidoTransito:
        destino = await sesion.scalar(
            select(MaestroDestino).where(MaestroDestino.codigo == "CRMOB")
        )
        assert destino is not None
        proveedor = await sesion.scalar(select(Proveedor).where(Proveedor.codigo == "P-ETA-1"))
        if proveedor is None:
            proveedor = Proveedor(codigo="P-ETA-1", nombre="Proveedor")
            sesion.add(proveedor)
        material = await sesion.scalar(select(Material).where(Material.codigo == "M-ETA-1"))
        if material is None:
            material = Material(codigo="M-ETA-1", descripcion="Material", unidad_medida="KG")
            sesion.add(material)
        await sesion.flush()

        elemento = ElementoRastreado(
            tipo_tracking_externo="MMSI",
            tracking_externo="311001711",
            via_transporte="MARITIMO",
            velocidad_actual=Decimal(str(velocidad)) if velocidad is not None else None,
            ultima_actualizacion_api=DESDE,
        )
        if posicion is not None:
            elemento.posicion_actual = historial.punto_wkt(*posicion)
        sesion.add(elemento)
        await sesion.flush()

        pedido = PedidoTransito(
            oc_numero="4566000001",
            posicion_oc=10,
            tracking_interno="TRK-4566000001-010",
            id_proveedor=proveedor.id,
            id_material=material.id,
            id_destino=destino.id,
            via_transporte="MARITIMO",
            cantidad_pedida=Decimal("1.000"),
            unidad_medida="KG",
            fecha_entrega_pedido=dt.date(2026, 10, 10),
            lead_time_destino_dias=destino.lead_time_dias,
            etapa_viaje="EN_TRANSITO",
            estado_calculado="EN_TRANSITO",
            id_elemento_rastreado=elemento.id,
        )
        sesion.add(pedido)
        await sesion.flush()
        return pedido

    async def test_la_distancia_sale_de_postgis(self, sesion) -> None:
        """El buque del spike, en el Caribe panameño a ~358 km de Moín."""
        pedido = await self._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=12.5)

        resultado = await eta_estimada.estimar(sesion, pedido)

        assert resultado.distancia_m is not None
        assert 350_000 < resultado.distancia_m < 365_000
        assert resultado.eta is not None

    async def test_la_eta_cae_donde_dice_la_aritmetica(self, sesion) -> None:
        pedido = await self._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=12.5)

        resultado = await eta_estimada.estimar(sesion, pedido)

        assert resultado.horas is not None
        millas = resultado.distancia_m / MN  # type: ignore[operator]
        assert resultado.horas == pytest.approx(millas / 12.5, rel=1e-6)

    async def test_sin_posicion_no_estima(self, sesion) -> None:
        """Lo corriente: ShipsGo no garantiza posición y AIS no cubre puertos."""
        pedido = await self._pedido(sesion, posicion=None, velocidad=12.5)

        resultado = await eta_estimada.estimar(sesion, pedido)

        assert resultado.eta is None
        assert resultado.motivo == eta_estimada.SIN_POSICION

    async def test_sin_velocidad_no_estima(self, sesion) -> None:
        """El caso de ShipsGo: entrega posición pero **no** velocidad."""
        pedido = await self._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=None)

        resultado = await eta_estimada.estimar(sesion, pedido)

        assert resultado.eta is None
        assert resultado.motivo == eta_estimada.SIN_VELOCIDAD

    async def test_un_pedido_sin_rastreo_no_estima(self, sesion) -> None:
        pedido = await self._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=12.5)
        pedido.id_elemento_rastreado = None
        pedido.etapa_viaje = "SIN_TRACKING"
        pedido.estado_calculado = "SIN_TRACKING"
        await sesion.flush()

        resultado = await eta_estimada.estimar(sesion, pedido)

        assert resultado.motivo == eta_estimada.SIN_POSICION

    async def test_el_minimo_sale_de_parametros_sistema(self, sesion) -> None:
        """Ajustable sin desplegar, como el resto de los umbrales (`US-17`)."""
        pedido = await self._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=2.0)

        await sesion.execute(
            delete(ParametroSistema).where(
                ParametroSistema.clave == eta_estimada.CLAVE_VELOCIDAD_MINIMA
            )
        )
        sesion.add(
            ParametroSistema(
                clave=eta_estimada.CLAVE_VELOCIDAD_MINIMA,
                valor="5.0",
                tipo_dato="DECIMAL",
                descripcion="Mínimo alto de prueba",
            )
        )
        await sesion.flush()

        resultado = await eta_estimada.estimar(sesion, pedido)

        assert resultado.eta is None
        assert resultado.motivo == eta_estimada.DEMASIADO_LENTO


# --- Cómo entra en la fecha proyectada -------------------------------------


@pytest.mark.integration
class TestIntegracionConElMotor:
    """`US-08` alimenta a `US-09` por la precedencia de RN-14."""

    async def test_la_estimada_produce_fecha_proyectada(self, sesion) -> None:
        from app.services import proyeccion
        from app.services.recalculo import recalcular

        prueba = TestEstimarContraLaBase()
        pedido = await prueba._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=12.5)

        resultado = await recalcular(sesion, pedido)
        await sesion.flush()

        assert resultado.proyeccion.origen == proyeccion.ORIGEN_ETA_ESTIMADA
        assert pedido.fecha_proyectada_disponible is not None

    async def test_si_la_fuente_trae_eta_no_se_estima(self, sesion) -> None:
        """No se gasta una consulta PostGIS en algo que no cambiaría el resultado."""
        from app.services import proyeccion
        from app.services.recalculo import recalcular

        prueba = TestEstimarContraLaBase()
        pedido = await prueba._pedido(sesion, posicion=(-79.885643, 9.36328), velocidad=12.5)
        elemento = await sesion.get(ElementoRastreado, pedido.id_elemento_rastreado)
        assert elemento is not None
        elemento.eta_api = dt.datetime(2026, 9, 30, tzinfo=dt.UTC)
        await sesion.flush()

        resultado = await recalcular(sesion, pedido)

        assert resultado.proyeccion.origen == proyeccion.ORIGEN_ETA_FUENTE
