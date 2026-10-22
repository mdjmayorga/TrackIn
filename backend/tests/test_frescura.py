"""¿Está cargado el Z-tracking de esta semana? — `US-23`.

Acuerdo con Compras del 22/10/2026: SAP se actualiza los lunes y el Z-tracking se
carga en TrackIn a más tardar el martes. Las fechas de las pruebas caen en la
semana del lunes 19/10/2026 al domingo 25/10/2026.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import delete

from app.models.carga_ztracking import CargaZTracking
from app.models.parametro_sistema import ParametroSistema
from app.models.usuario import Usuario
from app.services.ingesta.frescura import ZONA_CR, estado_semanal

pytestmark = pytest.mark.integration


def _cr(dia: int, hora: int = 10, minuto: int = 0) -> dt.datetime:
    """Un instante de octubre de 2026 en hora de Costa Rica."""
    return dt.datetime(2026, 10, dia, hora, minuto, tzinfo=ZONA_CR)


@pytest.fixture
async def sin_cargas(sesion) -> Usuario:
    await sesion.execute(delete(CargaZTracking))
    cuenta = Usuario(
        usuario="compras.frescura", nombre_completo="Compras", rol="COMPRAS", hash_contrasena="x"
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


async def _carga(sesion, cuenta: Usuario, cuando: dt.datetime, estado: str = "APLICADA") -> None:
    sesion.add(
        CargaZTracking(
            id_usuario=cuenta.id,
            archivo="ZTRACKING.xlsx",
            tamano_bytes=1000,
            realizada_en=cuando,
            estado=estado,
        )
    )
    await sesion.flush()


async def test_sin_ninguna_carga_lo_dice(sesion, sin_cargas) -> None:
    estado = await estado_semanal(sesion, instante=_cr(22))

    assert estado.situacion == "NUNCA"
    assert estado.ultima is None
    assert estado.semana_desde == dt.date(2026, 10, 19)


async def test_con_la_carga_del_lunes_esta_al_dia_toda_la_semana(sesion, sin_cargas) -> None:
    await _carga(sesion, sin_cargas, _cr(19, 9))

    for dia in (19, 20, 22, 25):
        assert (await estado_semanal(sesion, instante=_cr(dia, 23))).situacion == "AL_DIA"


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [(19, "TOCA_CARGAR"), (20, "TOCA_CARGAR"), (21, "ATRASADA"), (25, "ATRASADA")],
)
async def test_sin_la_de_esta_semana_recuerda_hasta_el_martes_y_despues_avisa(
    sesion, sin_cargas, dia, esperado
) -> None:
    await _carga(sesion, sin_cargas, _cr(13))  # la del martes anterior

    estado = await estado_semanal(sesion, instante=_cr(dia))

    assert estado.situacion == esperado
    assert estado.ultima is not None and estado.dia_limite == 2


async def test_una_carga_rechazada_no_cuenta(sesion, sin_cargas) -> None:
    """Un archivo rechazado entero no cambió ningún pedido."""
    await _carga(sesion, sin_cargas, _cr(13))
    await _carga(sesion, sin_cargas, _cr(20), estado="RECHAZADA")

    estado = await estado_semanal(sesion, instante=_cr(21))

    assert estado.situacion == "ATRASADA"
    assert estado.ultima is not None
    assert estado.ultima.realizada_en.astimezone(ZONA_CR).date() == dt.date(2026, 10, 13)


async def test_la_semana_se_cuenta_en_hora_de_costa_rica(sesion, sin_cargas) -> None:
    """Domingo 18/10 a las 19:00 en Costa Rica ya es lunes 19/10 en UTC: no es de esta semana."""
    await _carga(sesion, sin_cargas, _cr(18, 19))

    estado = await estado_semanal(sesion, instante=_cr(19, 10))

    assert estado.situacion == "TOCA_CARGAR"


async def test_el_dia_limite_es_un_parametro(sesion, sin_cargas) -> None:
    await _carga(sesion, sin_cargas, _cr(13))
    await sesion.execute(
        delete(ParametroSistema).where(ParametroSistema.clave == "dia_limite_carga")
    )
    sesion.add(
        ParametroSistema(clave="dia_limite_carga", valor="3", tipo_dato="ENTERO", descripcion="t")
    )
    await sesion.flush()

    assert (await estado_semanal(sesion, instante=_cr(21))).situacion == "TOCA_CARGAR"  # miércoles
    assert (await estado_semanal(sesion, instante=_cr(22))).situacion == "ATRASADA"


async def test_el_endpoint_lo_publica_para_cualquier_rol(
    client, como_rol, sesion, sin_cargas
) -> None:
    """Planta también lo ve: es un dato de frescura, no una acción."""
    from app.db.session import get_db
    from app.main import app

    await _carga(sesion, sin_cargas, _cr(13))

    async def _misma_sesion():
        yield sesion

    app.dependency_overrides[get_db] = _misma_sesion
    como_rol("PLANTA")
    try:
        respuesta = await client.get("/api/v1/cargas/estado")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["situacion"] in {"TOCA_CARGAR", "ATRASADA", "AL_DIA"}
    assert cuerpo["ultima"]["usuario"]["usuario"] == "compras.frescura"
    assert cuerpo["dia_limite"] == 2
