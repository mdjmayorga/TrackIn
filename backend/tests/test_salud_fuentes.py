"""Pruebas de `app.services.salud_fuentes` — RF-09 / RNF-12 / RF-24 (`US-03`).

Cubren los dos criterios que `resiliencia.py` no puede cumplir solo, porque
salen de su frontera: que el estado **sobreviva** entre una lectura y la
siguiente, y que los umbrales se lean de `parametros_sistema` en vez de estar
fijos en el código.

Las que tocan la base van marcadas `integration`; las del registro no la
necesitan y corren siempre.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.models.parametro_sistema import ParametroSistema
from app.services import parametros
from app.services.resiliencia import ClaseFallo, PoliticaReintento
from app.services.salud_fuentes import RegistroSalud, politica_vigente

T0 = dt.datetime(2026, 9, 8, 12, 0, 0, tzinfo=dt.UTC)


def _en(segundos: int) -> dt.datetime:
    return T0 + dt.timedelta(seconds=segundos)


# --- El registro: que el estado sobreviva ---------------------------------


def test_una_fuente_nueva_nace_sana() -> None:
    registro = RegistroSalud()
    assert not registro.estado("vizion").degradada


def test_pedir_dos_veces_la_misma_fuente_da_el_mismo_estado() -> None:
    """La razón de ser del registro: sin esto `fallos_consecutivos` se
    reiniciaría en cada consulta y la espera creciente nunca crecería."""
    registro = RegistroSalud()
    registro.estado("vizion").registrar_fallo(
        instante=T0, clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado"
    )
    assert registro.estado("vizion").fallos_consecutivos == 1


def test_el_nombre_de_la_fuente_se_normaliza() -> None:
    """`Vizion` y `vizion` son la misma fuente, no dos."""
    registro = RegistroSalud()
    registro.estado("  VIZION ").registrar_fallo(
        instante=T0, clase=ClaseFallo.TRANSITORIO, motivo="error_servidor"
    )
    assert registro.estado("vizion").fallos_consecutivos == 1
    assert len(registro.resumen(ahora=T0)) == 1


def test_la_caida_de_una_fuente_no_arrastra_a_la_otra() -> None:
    """Vizion y Portcast son contratos distintos, con credenciales distintas."""
    registro = RegistroSalud()
    registro.estado("vizion").registrar_fallo(
        instante=T0, clase=ClaseFallo.PERMANENTE, motivo="credencial_invalida"
    )
    assert registro.estado("vizion").degradada
    assert not registro.estado("portcast").degradada


def test_el_registro_arranca_vacio() -> None:
    """Un despliegue sin fuentes conectadas es un estado válido, no un error:
    es la misma decisión que `ingesta: null` (TASK-03)."""
    assert RegistroSalud().resumen(ahora=T0) == []
    assert not RegistroSalud().hay_degradadas


def test_el_resumen_va_ordenado_por_nombre() -> None:
    """Una lista que cambia de orden sola es ruido en un diff y en una prueba."""
    registro = RegistroSalud()
    for nombre in ("vizion", "aisstream", "portcast"):
        registro.estado(nombre)
    assert [f["fuente"] for f in registro.resumen(ahora=T0)] == [
        "aisstream",
        "portcast",
        "vizion",
    ]


def test_el_resumen_lleva_la_antiguedad_del_ultimo_dato_bueno() -> None:
    """RNF-12: no basta con decir que la fuente está caída, hay que decir de
    cuándo es lo último que sí se supo."""
    registro = RegistroSalud()
    fuente = registro.estado("vizion")
    fuente.registrar_exito(instante=_en(0))
    fuente.registrar_fallo(instante=_en(60), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado")

    resumen = registro.resumen(ahora=_en(600))[0]
    assert resumen["antiguedad_s"] == 600
    assert resumen["motivo_ultimo_fallo"] == "tiempo_agotado"


def test_hay_degradadas_detecta_una_sola() -> None:
    registro = RegistroSalud()
    registro.estado("portcast")
    registro.estado("vizion").registrar_fallo(
        instante=T0, clase=ClaseFallo.PERMANENTE, motivo="cuota_agotada"
    )
    assert registro.hay_degradadas


def test_olvidar_todo_deja_el_registro_como_nuevo() -> None:
    registro = RegistroSalud()
    registro.estado("vizion").registrar_fallo(
        instante=T0, clase=ClaseFallo.PERMANENTE, motivo="credencial_invalida"
    )
    registro.olvidar_todo()
    assert registro.resumen(ahora=T0) == []
    assert not registro.estado("vizion").degradada


def test_el_resumen_usa_la_hora_actual_si_no_se_le_da_una() -> None:
    registro = RegistroSalud()
    registro.estado("vizion").registrar_exito(instante=dt.datetime.now(dt.UTC))
    antiguedad = registro.resumen()[0]["antiguedad_s"]
    assert isinstance(antiguedad, float)
    assert 0 <= antiguedad < 5


# --- Umbrales sin desplegar código (RF-24) --------------------------------


def test_la_politica_del_registro_se_hereda_a_las_fuentes_nuevas() -> None:
    politica = PoliticaReintento(intentos_maximos=2)
    registro = RegistroSalud(politica=politica)
    assert registro.estado("vizion").politica is politica


def test_cambiar_la_politica_alcanza_a_las_fuentes_que_ya_se_seguian() -> None:
    """Es lo que hace que RF-24 se note: ajustar el umbral surte efecto sobre
    las fuentes vivas, sin reiniciar el proceso."""
    registro = RegistroSalud(politica=PoliticaReintento(intentos_maximos=9))
    fuente = registro.estado("vizion")
    for n in range(2):
        fuente.registrar_fallo(
            instante=_en(n), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado"
        )
    assert not fuente.degradada  # con nueve intentos, dos no agotan nada

    registro.usar_politica(PoliticaReintento(intentos_maximos=2))

    # El historial no cambia porque cambien los umbrales, pero la lectura sí.
    assert fuente.fallos_consecutivos == 2
    assert not fuente.debe_reintentar


def test_la_politica_nueva_tambien_rige_para_las_siguientes() -> None:
    registro = RegistroSalud()
    registro.estado("vizion")
    politica = PoliticaReintento(intentos_maximos=1)
    registro.usar_politica(politica)
    assert registro.estado("portcast").politica is politica


@pytest.mark.integration
class TestPoliticaDesdeLaBase:
    """`politica_vigente` es el puente entre los umbrales y la política."""

    async def test_sin_filas_se_usan_los_defectos_del_catalogo(self, sesion) -> None:
        """El sistema reintenta bien con la tabla vacía, igual que `US-04`."""
        for clave in parametros.CATALOGO:
            if clave.startswith("resiliencia_"):
                await sesion.execute(
                    delete(ParametroSistema).where(ParametroSistema.clave == clave)
                )
        await sesion.flush()

        politica = await politica_vigente(sesion)

        assert politica == PoliticaReintento()

    async def test_la_migracion_sembro_los_umbrales(self, sesion) -> None:
        """`0004` los siembra para que sean descubribles por quien administra."""
        for clave in parametros.CATALOGO:
            if clave.startswith("resiliencia_"):
                assert (
                    await sesion.get(ParametroSistema, clave) is not None
                ), f"{clave} no quedó sembrado por la migración 0004"

    async def test_los_valores_sembrados_coinciden_con_el_catalogo(self, sesion) -> None:
        """Si divergen, la política cambiaría según hubiera corrido la migración."""
        politica = await politica_vigente(sesion)
        assert politica == PoliticaReintento()

    async def test_cambiar_la_fila_cambia_la_espera_sin_tocar_codigo(self, sesion) -> None:
        """El sexto criterio de la historia, verificado de punta a punta."""
        await sesion.execute(
            delete(ParametroSistema).where(
                ParametroSistema.clave.in_(
                    ["resiliencia_espera_inicial_s", "resiliencia_ruido_espera"]
                )
            )
        )
        sesion.add_all(
            [
                ParametroSistema(
                    clave="resiliencia_espera_inicial_s",
                    valor="30",
                    tipo_dato="ENTERO",
                    descripcion="Ajustado en la prueba.",
                ),
                ParametroSistema(
                    clave="resiliencia_ruido_espera",
                    valor="0",
                    tipo_dato="DECIMAL",
                    descripcion="Sin ruido, para poder comparar el número exacto.",
                ),
            ]
        )
        await sesion.flush()

        politica = await politica_vigente(sesion)

        assert politica.espera_inicial_s == 30
        assert politica.espera(1) == 30
        assert politica.espera(2) == 60

    async def test_un_umbral_ilegible_cae_al_defecto_sin_dejar_de_reintentar(
        self, sesion, caplog
    ) -> None:
        """Una errata en la configuración no puede dejar el sistema sin reintentos:
        en el peor caso se reintenta con los valores de siempre."""
        await sesion.execute(
            delete(ParametroSistema).where(ParametroSistema.clave == "resiliencia_intentos_maximos")
        )
        sesion.add(
            ParametroSistema(
                clave="resiliencia_intentos_maximos",
                valor="muchos",
                tipo_dato="ENTERO",
                descripcion="Errata deliberada.",
            )
        )
        await sesion.flush()

        politica = await politica_vigente(sesion)

        assert (
            politica.intentos_maximos == parametros.CATALOGO["resiliencia_intentos_maximos"].defecto
        )
        assert "muchos" in caplog.text

    async def test_el_factor_conserva_su_precision_decimal(self, sesion) -> None:
        """1.5 tiene que llegar como 1.5, no truncado a 1."""
        await sesion.execute(
            delete(ParametroSistema).where(
                ParametroSistema.clave.in_(
                    ["resiliencia_factor_espera", "resiliencia_ruido_espera"]
                )
            )
        )
        sesion.add_all(
            [
                ParametroSistema(
                    clave="resiliencia_factor_espera",
                    valor="1.5",
                    tipo_dato="DECIMAL",
                    descripcion="Ajustado en la prueba.",
                ),
                ParametroSistema(
                    clave="resiliencia_ruido_espera",
                    valor="0",
                    tipo_dato="DECIMAL",
                    descripcion="Sin ruido.",
                ),
            ]
        )
        await sesion.flush()

        politica = await politica_vigente(sesion)

        assert politica.factor == 1.5
        assert politica.espera(3) == pytest.approx(5 * 1.5**2)


def test_los_umbrales_de_resiliencia_estan_declarados_en_el_catalogo() -> None:
    """Si falta uno, `politica_vigente` reventaría con `KeyError` en runtime."""
    esperados = {
        "resiliencia_espera_inicial_s",
        "resiliencia_factor_espera",
        "resiliencia_espera_maxima_s",
        "resiliencia_intentos_maximos",
        "resiliencia_ruido_espera",
    }
    assert esperados <= set(parametros.CATALOGO)


def test_los_defectos_del_catalogo_son_los_de_la_politica() -> None:
    """La misma coherencia que se exige entre la migración y el catálogo, ahora
    entre el catálogo y la dataclass: tres sitios con el mismo número."""
    defecto = PoliticaReintento()
    catalogo = parametros.CATALOGO
    assert catalogo["resiliencia_espera_inicial_s"].defecto == defecto.espera_inicial_s
    assert catalogo["resiliencia_factor_espera"].defecto == Decimal(str(defecto.factor))
    assert catalogo["resiliencia_espera_maxima_s"].defecto == defecto.espera_maxima_s
    assert catalogo["resiliencia_intentos_maximos"].defecto == defecto.intentos_maximos
    assert catalogo["resiliencia_ruido_espera"].defecto == Decimal(str(defecto.ruido))
