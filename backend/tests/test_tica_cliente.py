"""Pruebas de `app.services.rastreo.tica_cliente` — `US-49`.

Con las **respuestas reales de TICA** grabadas el 28/09/2026 por
`scripts/spikes/tica/01_capturar_respuestas.py`: la búsqueda de la guía hija
`ZIVHYD017`, su guía madre y una búsqueda sin resultados. Sin red.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

from app.services import resiliencia
from app.services.rastreo import tica_cliente
from app.services.rastreo.tica_cliente import ClienteTICA, ErrorTICA, Respuesta

_SALIDA = Path(__file__).resolve().parents[1] / "scripts/spikes/tica/output"
_BUSQUEDA = _SALIDA / "02_busqueda_hawb.html"
_MADRE = _SALIDA / "03_guia_madre.html"
_VACIA = _SALIDA / "04_busqueda_vacia.html"

pytestmark = pytest.mark.skipif(
    not (_BUSQUEDA.exists() and _MADRE.exists() and _VACIA.exists()),
    reason="faltan las respuestas grabadas del spike de TICA",
)

DESDE = dt.date(2026, 8, 1)
HASTA = dt.date(2026, 9, 28)


def _leer(archivo: Path) -> str:
    return archivo.read_text(encoding="utf-8")


class TransporteGrabado:
    """Devuelve las páginas grabadas y anota cada petición."""

    def __init__(self, resultado: Path = _BUSQUEDA, estado: int = 200) -> None:
        self.resultado = resultado
        self.estado = estado
        self.peticiones: list[tuple[str, str, dict[str, str] | None]] = []

    async def __call__(
        self, metodo: str, url: str, *, datos: dict[str, str] | None = None
    ) -> Respuesta:
        self.peticiones.append((metodo, url, datos))
        if self.estado != 200:
            return Respuesta(self.estado, "<html>Access Denied</html>")
        if "hcgconspadre" in url:
            return Respuesta(200, _leer(_MADRE))
        if metodo == "POST":
            return Respuesta(200, _leer(self.resultado))
        # El formulario vacío: cualquier página de TICA trae un `GXState`.
        return Respuesta(200, _leer(_VACIA))


def _cliente(transporte: TransporteGrabado) -> ClienteTICA:
    return ClienteTICA(transporte, pausa_s=0)


# --- Lectura del HTML -------------------------------------------------------


def test_lee_la_guia_hija_tal_como_la_declaro_el_manifiesto() -> None:
    [guia] = tica_cliente.parsear_busqueda(_leer(_BUSQUEDA))

    assert guia.numero == "ZIVHYD017"
    assert guia.es_hija
    assert guia.manifiesto == "26017849"
    assert guia.fecha_arribo == dt.date(2026, 9, 18)
    assert guia.aduana_codigo == "188AJU"  # Juan Santamaría
    assert guia.agente_nombre == "SPARX LOGISTICS COSTA RICA SOCIEDAD ANONIMA"
    assert guia.embarque_codigo == "170BOG"


def test_limpia_el_espacio_duro_que_trae_el_sitio() -> None:
    """TICA rellena con `\\xa0`: sin limpiarlo, `ALAJUELA` no compara."""
    [guia] = tica_cliente.parsear_busqueda(_leer(_BUSQUEDA))
    assert guia.aduana_nombre == "ALAJUELA"


def test_conserva_el_enlace_a_la_guia_madre() -> None:
    [guia] = tica_cliente.parsear_busqueda(_leer(_BUSQUEDA))
    assert guia.enlace_madre is not None
    assert guia.enlace_madre.startswith("hcgconspadre.aspx?")


def test_lee_la_guia_madre() -> None:
    madre = tica_cliente.parsear_madre(_leer(_MADRE))

    assert madre is not None
    assert madre.numero == "57434927513"
    assert madre.tipo_documento == "AWB"
    assert madre.transportista_nombre == "TACA INTERNATIONAL AIRLINES S A"
    assert madre.prefijo == "574"


def test_una_busqueda_sin_resultados_es_una_lista_vacia() -> None:
    assert tica_cliente.parsear_busqueda(_leer(_VACIA)) == []


def test_lee_el_anio_de_dos_digitos() -> None:
    assert tica_cliente.leer_fecha("18/09/26") == dt.date(2026, 9, 18)


def test_una_pagina_sin_formulario_es_un_bloqueo_y_no_se_reintenta() -> None:
    """Es lo que devuelve un desafío de Akamai: no hay `GXState`."""
    with pytest.raises(ErrorTICA) as error:
        tica_cliente.extraer_estado("<html><body>Please enable JavaScript</body></html>")
    assert error.value.motivo == "acceso_bloqueado"
    assert error.value.clase is resiliencia.ClaseFallo.PERMANENTE


def test_una_pagina_sin_grilla_es_un_cambio_del_sitio() -> None:
    pagina = re.sub(r'name="Grid2ContainerDataV"', 'name="Otra"', _leer(_BUSQUEDA))
    with pytest.raises(ErrorTICA) as error:
        tica_cliente.parsear_busqueda(pagina)
    assert error.value.motivo == "formato_inesperado"
    assert error.value.clase is resiliencia.ClaseFallo.PERMANENTE


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [
        (200, None),
        (403, "acceso_bloqueado"),
        (302, "acceso_bloqueado"),
        (429, "limite_de_tasa"),
        (503, "error_del_servidor"),
    ],
)
def test_clasifica_el_codigo_http(estado: int, motivo: str | None) -> None:
    assert tica_cliente.clasificar_respuesta(estado) == motivo


def test_el_limite_de_tasa_y_el_servidor_caido_son_transitorios() -> None:
    for motivo in ("limite_de_tasa", "error_del_servidor"):
        assert resiliencia.clasificar(motivo) is resiliencia.ClaseFallo.TRANSITORIO


# --- El cliente -------------------------------------------------------------


async def test_rastrear_una_guia_hija_hace_tres_peticiones() -> None:
    transporte = TransporteGrabado()
    cliente = _cliente(transporte)

    rastreo = await cliente.rastrear("ZIVHYD017", DESDE, HASTA)

    assert rastreo.encontrado
    assert rastreo.ultimo is not None and rastreo.ultimo.fecha_arribo == dt.date(2026, 9, 18)
    assert rastreo.madre is not None and rastreo.madre.numero == "57434927513"
    assert [p[0] for p in transporte.peticiones] == ["GET", "POST", "GET"]
    assert cliente.peticiones == 3


async def test_si_no_aparece_no_pide_la_madre() -> None:
    """Antes del arribo es lo normal, y cuesta dos peticiones, no tres."""
    transporte = TransporteGrabado(resultado=_VACIA)
    rastreo = await _cliente(transporte).rastrear("ZIVHYD017", DESDE, HASTA)

    assert not rastreo.encontrado
    assert rastreo.madre is None
    assert len(transporte.peticiones) == 2


async def test_envia_las_fechas_y_la_guia_con_el_evento_del_boton() -> None:
    transporte = TransporteGrabado()
    await _cliente(transporte).buscar("ZIVHYD017", DESDE, HASTA)

    _, _, datos = transporte.peticiones[1]
    assert datos is not None
    assert datos["vVFCH1"] == "01/08/2026"
    assert datos["vVFCHF"] == "28/09/2026"
    assert datos["vCGNROCON"] == "ZIVHYD017"
    estado = json.loads(datos["GXState"])
    assert estado["_EventName"] == "EENTER."


async def test_un_bloqueo_se_reporta_en_la_primera_peticion() -> None:
    """No se insiste: una sola petición y el motivo a la vista."""
    transporte = TransporteGrabado(estado=403)
    with pytest.raises(ErrorTICA) as error:
        await _cliente(transporte).rastrear("ZIVHYD017", DESDE, HASTA)

    assert error.value.motivo == "acceso_bloqueado"
    assert len(transporte.peticiones) == 1


async def test_espera_entre_peticiones(monkeypatch: pytest.MonkeyPatch) -> None:
    """La pausa es cortesía con un sitio público: entre peticiones, no antes."""
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)

    monkeypatch.setattr(tica_cliente.asyncio, "sleep", dormir)
    await ClienteTICA(TransporteGrabado(), pausa_s=1.5).rastrear("ZIVHYD017", DESDE, HASTA)

    assert esperas == [1.5, 1.5]


async def test_el_payload_no_guarda_el_enlace_que_caduca() -> None:
    rastreo = await _cliente(TransporteGrabado()).rastrear("ZIVHYD017", DESDE, HASTA)

    [guia] = rastreo.payload["conocimientos"]
    assert "enlace_madre" not in guia
    assert guia["fecha_arribo"] == "2026-09-18"
    assert rastreo.payload["madre"]["numero"] == "57434927513"
    json.dumps(rastreo.payload)  # tiene que poder ir a una columna JSONB
