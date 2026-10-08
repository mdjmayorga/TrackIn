"""Pruebas de `/api/v1/cargas` — subir el Excel del Z-tracking (`US-58`).

La lectura y la carga ya están probadas en `test_ztracking` y `test_carga`. Aquí
se prueba lo nuevo: que el archivo llegue por HTTP, que un archivo equivocado
no toque ningún pedido, quién puede cargar y que quede registro.

La sesión de la prueba se presta al endpoint con `commit` convertido en `flush`
y `rollback` limitado a un punto de guardado: todo sigue dentro de la
transacción que se revierte al terminar.
"""

from __future__ import annotations

import io
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import delete, func, select

from app.api.cargas import resolutor_de_destinos
from app.api.dependencias import Autenticado, usuario_actual
from app.db.session import get_db
from app.main import app
from app.models.carga_ztracking import CargaZTracking
from app.models.pedido_transito import PedidoTransito
from app.models.sesion import Sesion
from app.models.usuario import Usuario
from app.services.ingesta import carga_archivo
from test_ztracking import _WK36

pytestmark = pytest.mark.integration

URL = "/api/v1/cargas"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class _SesionDePrueba:
    """`commit` → `flush`; `rollback` → vuelve al último punto de guardado."""

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion
        self._punto: Any = None

    async def abrir(self) -> _SesionDePrueba:
        self._punto = await self._sesion.begin_nested()
        return self

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._sesion, nombre)

    async def commit(self) -> None:
        # Como un commit de verdad: lo confirmado ya no lo deshace el próximo
        # `rollback`. Se cierra el punto de guardado y se abre otro.
        await self._sesion.flush()
        await self._punto.commit()
        self._punto = await self._sesion.begin_nested()

    async def rollback(self) -> None:
        await self._punto.rollback()
        self._punto = await self._sesion.begin_nested()


async def _usuario(sesion, rol: str) -> Usuario:
    usuario = Usuario(
        usuario=f"carga-{rol.lower()}",
        nombre_completo=f"Carga {rol.title()}",
        rol=rol,
        activo=True,
        hash_contrasena="x",
    )
    sesion.add(usuario)
    await sesion.flush()
    return usuario


@pytest.fixture
async def api(sesion) -> AsyncGenerator[tuple[AsyncClient, Usuario], None]:
    """Cliente de Compras con un usuario real (la carga lo referencia) y sin pedidos."""
    await sesion.execute(delete(PedidoTransito))
    usuario = await _usuario(sesion, "COMPRAS")
    prestada = await _SesionDePrueba(sesion).abrir()

    async def _misma_sesion():
        yield prestada

    app.dependency_overrides[get_db] = _misma_sesion
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=usuario, sesion=Sesion(id=0, id_usuario=usuario.id)
    )
    # Nunca ShipsGo en las pruebas: el resolutor real leería la cuenta.
    app.dependency_overrides[resolutor_de_destinos] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, usuario
    finally:
        for dependencia in (get_db, usuario_actual, resolutor_de_destinos):
            app.dependency_overrides.pop(dependencia, None)


def _excel(hojas: dict[str, list[list[Any]]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(nombre)
        for fila in filas:
            ws.append(fila)
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _ztracking(*lineas_produccion: list[Any], ida: list[list[Any]] | None = None) -> bytes:
    return _excel(
        {
            "PRODUCCION": _WK36.hoja(*lineas_produccion, primera_celda=81),
            "IDA": _WK36.hoja(*(ida or [])),
        }
    )


async def _subir(cliente: AsyncClient, contenido: bytes, nombre: str = "WK40.xlsx"):
    return await cliente.post(URL, files={"archivo": (nombre, contenido, XLSX)})


async def _pedidos(sesion) -> int:
    return await sesion.scalar(select(func.count()).select_from(PedidoTransito))


async def _cargas(sesion) -> list[CargaZTracking]:
    return list(await sesion.scalars(select(CargaZTracking).order_by(CargaZTracking.id)))


# --- La carga --------------------------------------------------------------


async def test_subir_el_excel_carga_los_pedidos_y_devuelve_el_informe(api, sesion) -> None:
    cliente, usuario = api
    contenido = _ztracking(
        _WK36.linea(oc_numero="4500090001", posicion_oc="10"),
        _WK36.linea(oc_numero="4500090002", posicion_oc="20"),
        # Sin vía: no entra, y el informe dice cuál y por qué.
        _WK36.linea(oc_numero="4500090003", posicion_oc="30", via_transporte="N/A"),
    )

    respuesta = await _subir(cliente, contenido, "2026 - OCTUBRE - WK40.xlsx")

    assert respuesta.status_code == 201, respuesta.text
    carga = respuesta.json()
    assert carga["estado"] == "APLICADA"
    assert carga["archivo"] == "2026 - OCTUBRE - WK40.xlsx"
    assert carga["usuario"] == {"usuario": usuario.usuario, "nombre_completo": "Carga Compras"}
    assert (carga["recibidas"], carga["insertadas"], carga["no_entraron"]) == (3, 2, 1)
    assert carga["incidencias"][0]["clave"] == "4500090003-30"
    assert carga["incidencias"][0]["consecuencia"] == "no_entro"
    assert sum(carga["por_motivo"].values()) == 1
    assert await _pedidos(sesion) == 2


async def test_queda_registrada_quien_cargo_y_cuando(api, sesion) -> None:
    cliente, usuario = api

    await _subir(cliente, _ztracking(_WK36.linea(oc_numero="4500090001")))

    (carga,) = await _cargas(sesion)
    assert carga.id_usuario == usuario.id
    assert carga.estado == "APLICADA"
    assert carga.realizada_en is not None
    assert carga.informe["recibidas"] == 1


async def test_recargar_el_mismo_archivo_no_cambia_nada(api, sesion) -> None:
    cliente, _ = api
    contenido = _ztracking(_WK36.linea(oc_numero="4500090001"))

    await _subir(cliente, contenido)
    segunda = (await _subir(cliente, contenido)).json()

    assert (segunda["insertadas"], segunda["actualizadas"], segunda["sin_cambios"]) == (0, 0, 1)


async def test_lo_que_deja_de_venir_queda_ausente_y_no_se_borra(api, sesion) -> None:
    cliente, _ = api
    await _subir(
        cliente,
        _ztracking(_WK36.linea(oc_numero="4500090001"), _WK36.linea(oc_numero="4500090002")),
    )

    segunda = (await _subir(cliente, _ztracking(_WK36.linea(oc_numero="4500090001")))).json()

    assert segunda["ausentes"] == 1
    assert await _pedidos(sesion) == 2


# --- Un archivo equivocado no toca nada ------------------------------------


@pytest.mark.parametrize(
    ("contenido", "nombre", "mensaje"),
    [
        (b"no soy un excel", "WK40.xlsx", "no se pudo abrir como Excel"),
        (b"a,b,c\n1,2,3\n", "WK40.csv", "no es un Excel"),
        (b"", "WK40.xlsx", "está vacío"),
    ],
)
async def test_un_archivo_que_no_es_excel_se_rechaza(api, sesion, contenido, nombre, mensaje):
    cliente, _ = api

    respuesta = await _subir(cliente, contenido, nombre)

    assert respuesta.status_code == 422
    assert mensaje in respuesta.json()["detail"]


async def test_un_excel_sin_las_hojas_del_ztracking_no_marca_ausente_nada(api, sesion) -> None:
    """El caso peligroso: se lee bien, pero no es el Z-tracking. Sin la guarda,
    la carga no vería ninguna línea y daría por ausentes **todos** los pedidos."""
    cliente, _ = api
    await _subir(cliente, _ztracking(_WK36.linea(oc_numero="4500090001")))

    respuesta = await _subir(cliente, _excel({"Hoja1": [["otra", "cosa"], [1, 2]]}), "otro.xlsx")

    assert respuesta.status_code == 422
    assert "le faltan las hojas PRODUCCION, IDA" in respuesta.json()["detail"]
    ausentes = await sesion.scalar(
        select(func.count()).where(PedidoTransito.ausente_desde.is_not(None))
    )
    assert ausentes == 0


async def test_las_hojas_sin_ninguna_linea_tambien_se_rechazan(api, sesion) -> None:
    cliente, _ = api

    respuesta = await _subir(cliente, _ztracking())

    assert respuesta.status_code == 422
    assert "ninguna línea legible" in respuesta.json()["detail"]


async def test_una_hoja_con_otras_columnas_se_rechaza_con_el_nombre_original(api) -> None:
    cliente, _ = api
    contenido = _excel({"PRODUCCION": [["A", "B"], [1, 2]], "IDA": [["A", "B"], [1, 2]]})

    respuesta = await _subir(cliente, contenido, "WK40.xlsx")

    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert "no parece un Z-tracking" in detalle
    # El temporal del servidor no se filtra al mensaje: se nombra lo que subió.
    assert "WK40.xlsx" in detalle
    assert ".tmp" not in detalle


async def test_el_rechazo_queda_registrado_con_su_motivo(api, sesion) -> None:
    cliente, usuario = api

    await _subir(cliente, _excel({"Hoja1": [["x"]]}), "C:\\Users\\alguien\\otro.xlsx")

    (carga,) = await _cargas(sesion)
    assert carga.estado == "RECHAZADA"
    assert carga.archivo == "otro.xlsx"  # sin la ruta del equipo de quien lo subió
    assert "le faltan las hojas" in carga.motivo_rechazo
    assert carga.id_usuario == usuario.id
    assert carga.informe is None


async def test_un_archivo_demasiado_grande_se_rechaza(api, monkeypatch) -> None:
    cliente, _ = api
    monkeypatch.setattr(carga_archivo, "TAMANO_MAXIMO_BYTES", 10)

    respuesta = await _subir(cliente, _ztracking(_WK36.linea()))

    assert respuesta.status_code == 422
    assert "el máximo es" in respuesta.json()["detail"]


async def test_con_otra_carga_en_curso_responde_409(api, monkeypatch) -> None:
    cliente, _ = api

    async def _ocupado(*_args, **_kwargs):
        raise carga_archivo.CargaEnCurso("Hay otra carga del Z-tracking en curso.")

    monkeypatch.setattr(carga_archivo, "cargar_archivo", _ocupado)

    respuesta = await _subir(cliente, _ztracking(_WK36.linea()))

    assert respuesta.status_code == 409
    assert "en curso" in respuesta.json()["detail"]


# --- Quién puede cargar -----------------------------------------------------


@pytest.mark.parametrize("rol", ["LOGISTICA", "PLANIFICACION"])
async def test_solo_compras_y_el_administrador_cargan(api, sesion, rol) -> None:
    cliente, _ = api
    otro = await _usuario(sesion, rol)
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=otro, sesion=Sesion(id=0, id_usuario=otro.id)
    )

    respuesta = await _subir(cliente, _ztracking(_WK36.linea()))

    assert respuesta.status_code == 403
    assert await _cargas(sesion) == []


async def test_el_administrador_tambien_carga(api, sesion) -> None:
    cliente, _ = api
    admin = await _usuario(sesion, "ADMINISTRADOR")
    app.dependency_overrides[usuario_actual] = lambda: Autenticado(
        usuario=admin, sesion=Sesion(id=0, id_usuario=admin.id)
    )

    respuesta = await _subir(cliente, _ztracking(_WK36.linea()))

    assert respuesta.status_code == 201


async def test_sin_sesion_no_se_carga(sesion) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        respuesta = await _subir(cliente, b"x")

    assert respuesta.status_code == 401


# --- El historial -----------------------------------------------------------


async def test_el_historial_muestra_lo_mas_reciente_primero(api, sesion) -> None:
    cliente, _ = api
    await _subir(cliente, _ztracking(_WK36.linea()), "primero.xlsx")
    await _subir(cliente, b"roto", "segundo.xlsx")

    historial = (await cliente.get(URL)).json()

    assert [c["archivo"] for c in historial[:2]] == ["segundo.xlsx", "primero.xlsx"]
    assert [c["estado"] for c in historial[:2]] == ["RECHAZADA", "APLICADA"]
    assert "incidencias" not in historial[0]


async def test_el_detalle_trae_el_informe_completo(api, sesion) -> None:
    cliente, _ = api
    creada = (
        await _subir(
            cliente, _ztracking(_WK36.linea(), _WK36.linea(oc_numero="x", via_transporte="N/A"))
        )
    ).json()

    detalle = await cliente.get(f"{URL}/{creada['id']}")

    assert detalle.status_code == 200
    assert detalle.json()["incidencias"] == creada["incidencias"]
    assert (await cliente.get(f"{URL}/999999999")).status_code == 404


def test_el_resolutor_sin_token_no_usa_shipsgo(monkeypatch) -> None:
    """Sin token, la carga sigue sin completar destinos desde ShipsGo."""
    import asyncio

    from app.api import cargas

    monkeypatch.setattr(cargas.settings, "SHIPSGO_API_TOKEN", None)

    async def _primero():
        generador = resolutor_de_destinos()
        return await anext(generador)

    assert asyncio.run(_primero()) is None


def test_validar_nombre_quita_la_ruta() -> None:
    assert carga_archivo.validar_nombre("C:\\x\\y\\WK40.XLSX") == "WK40.XLSX"
    assert carga_archivo.validar_nombre(str(Path("a") / "b.xlsm")) == "b.xlsm"
    with pytest.raises(carga_archivo.ArchivoInvalido):
        carga_archivo.validar_nombre("   ")
