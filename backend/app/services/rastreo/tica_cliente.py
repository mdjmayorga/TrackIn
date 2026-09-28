"""Cliente de TICA, el sistema aduanero de Hacienda — `US-49` / RF-06, RN-05.

El hallazgo del 28/09/2026
---------------------------

Gutis recibe **guías hijas** (HAWB): las emite el agente de carga, que agrupa
varios clientes bajo una guía madre (MAWB) de la aerolínea. Ninguna fuente
comercial las rastrea —la aerolínea no las conoce— y `TASK-28` ya había medido
que ShipsGo exige la MAWB.

Pero **la aduana sí las conoce**. Todo envío que entra a Costa Rica se declara en
el manifiesto de carga, con la guía madre y sus hijas desconsolidadas. La
consulta pública «Conocimientos de Embarque» de TICA, sin usuario, busca por
número de guía y devuelve:

| Dato | Para qué sirve |
|---|---|
| Fecha de arribo del manifiesto | **La llegada real a Costa Rica** (RN-05), con fuente oficial |
| Aduana de descarga (`188AJU` = Juan Santamaría) | Confirma el destino |
| Agente de carga (desconsolidador) | Saber a quién pedirle la MAWB antes de la próxima |
| **La guía madre** | El número que ShipsGo sí rastrea |

Medido con `ZIVHYD017` (OC 4500018603-10): el Z-tracking decía «ETA CR 8 SEP» y
seguía en `PENDIENTE` el 28/09; TICA mostró que llegó el **18/09**, con guía
madre `574-34927513`. Diez días de atraso que nadie había registrado.

Lo que TICA **no** hace: seguir el envío en tránsito. La guía aparece cuando se
transmite el manifiesto, cerca del arribo. Por eso esta fuente confirma la
llegada; no reemplaza a ShipsGo.

Cómo se consulta, y cómo no
----------------------------

El sitio es GeneXus sobre ASP.NET, sin API. La consulta son tres peticiones:

1. `GET` del formulario, que entrega el estado de la página (`GXState`).
2. `POST` del mismo formulario con el evento `EENTER.`, las fechas y la guía.
   La grilla vuelve en el campo oculto `Grid2ContainerDataV`, y el enlace a la
   guía madre en `Grid2ContainerData`.
3. `GET` de ese enlace (`hcgconspadre.aspx?...`), cifrado por sesión.

**El sitio está detrás de Akamai Bot Manager.** Esto se consulta como lo haría
una persona con el navegador: un `User-Agent` que dice quién pregunta, una pausa
entre peticiones, pocas consultas al día y solo por guías de Gutis. Si Akamai
responde con un bloqueo o un desafío, el cliente **lo reporta como
`acceso_bloqueado` y se detiene**: no se reintenta en bucle ni se intenta
esquivar. `acceso_bloqueado` es permanente para `US-03`, así que degrada la
fuente y deja el motivo a la vista. Si eso pasa, la salida es formal: el agente
aduanal de Gutis tiene usuario de TICA y Hacienda ofrece servicios web para
usuarios registrados.

Por qué el transporte se inyecta
---------------------------------

Igual que en ShipsGo: todo lo de aquí se prueba con las respuestas reales
grabadas en `scripts/spikes/tica/output/`, y el transporte `httpx` de
`transporte_http` entra sin tocar nada más.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from app.services import resiliencia

logger = logging.getLogger(__name__)

BASE: Final = "https://ticaconsultas.hacienda.go.cr/Tica/"
RUTA_BUSQUEDA: Final = "hcgconocimientos.aspx"

#: Quién pregunta. Si alguien en Hacienda mira el registro, tiene que poder
#: saber de dónde vienen estas consultas.
USER_AGENT: Final = "TrackIn/0.1 (Laboratorios Gutis; consulta de guias propias)"

#: El evento del botón «Confirmar» y la grilla que refresca, leídos del
#: `onclick` del formulario el 28/09/2026.
EVENTO_BUSCAR: Final = "EENTER."
ID_GRILLA: Final = "41"

#: Segundos entre una petición y la siguiente. Es cortesía con un sitio público,
#: no una técnica: una persona tarda más que esto en hacer clic.
PAUSA_S: Final = 1.0

#: El sitio escribe las fechas del formulario así.
_FORMATO_FECHA: Final = "%d/%m/%Y"

_RE_ESTADO: Final = re.compile(r"name=\"GXState\" value='(.*?)'", re.S)
_RE_GRILLA: Final = re.compile(r"name=\"Grid2ContainerDataV\" value='(.*?)'", re.S)
_RE_ENLACE_MADRE: Final = re.compile(r"hcgconspadre\.aspx\?[A-Za-z0-9+/=]+")


class ErrorTICA(RuntimeError):
    """Fallo de TICA ya clasificado para la política de `US-03`."""

    def __init__(self, motivo: str, detalle: str = "") -> None:
        super().__init__(detalle or motivo)
        self.motivo = motivo
        self.detalle = detalle

    @property
    def clase(self) -> resiliencia.ClaseFallo:
        return resiliencia.clasificar(self.motivo)


@dataclass(frozen=True, slots=True)
class Respuesta:
    """Lo mínimo que el cliente necesita de una respuesta HTTP."""

    estado: int
    texto: str


class Transporte(Protocol):
    """El puerto HTTP. Mantiene las cookies de la sesión entre peticiones:
    el enlace a la guía madre solo vale dentro de la sesión que lo generó."""

    async def __call__(
        self, metodo: str, url: str, *, datos: dict[str, str] | None = None
    ) -> Respuesta: ...


@dataclass(frozen=True, slots=True)
class Conocimiento:
    """Una fila de la búsqueda: la guía tal como la declaró el manifiesto."""

    numero: str
    #: `HWB` para una guía hija, `AWB` para una madre.
    tipo_documento: str
    manifiesto: str
    fecha_arribo: dt.date
    deposito: str
    aduana_codigo: str
    aduana_nombre: str
    agente_ruc: str
    agente_nombre: str
    embarque_codigo: str
    embarque_nombre: str
    estado: str
    #: Enlace a la guía madre, válido solo en la sesión que hizo la búsqueda.
    enlace_madre: str | None = None

    @property
    def es_hija(self) -> bool:
        return self.tipo_documento == "HWB"


@dataclass(frozen=True, slots=True)
class GuiaMadre:
    """La guía de la aerolínea que ampara a la hija."""

    numero: str
    tipo_documento: str
    transportista_ruc: str
    transportista_nombre: str
    estado: str

    @property
    def prefijo(self) -> str | None:
        """Los tres dígitos de la aerolínea, si es un MAWB bien formado."""
        solo_digitos = self.numero.replace("-", "")
        return solo_digitos[:3] if len(solo_digitos) == 11 and solo_digitos.isdigit() else None


@dataclass(frozen=True, slots=True)
class ResultadoRastreo:
    """Lo que TICA sabe de una guía."""

    numero: str
    conocimientos: tuple[Conocimiento, ...] = ()
    madre: GuiaMadre | None = None
    #: Las filas crudas, para guardarlas como payload (RNF-13).
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def encontrado(self) -> bool:
        return bool(self.conocimientos)

    @property
    def ultimo(self) -> Conocimiento | None:
        """El arribo más reciente: si el número se repite, manda el último."""
        if not self.conocimientos:
            return None
        return max(self.conocimientos, key=lambda c: c.fecha_arribo)


# --- Lectura del HTML -------------------------------------------------------


def extraer_estado(pagina: str) -> dict[str, Any]:
    """El `GXState` de la página. Sin él no hay formulario que enviar.

    Una página sin `GXState` no es la de TICA: es lo que devuelve un desafío de
    Akamai o una página de error. Se clasifica como bloqueo, no se reintenta.
    """
    hallado = _RE_ESTADO.search(pagina)
    if hallado is None:
        raise ErrorTICA(
            "acceso_bloqueado",
            "la respuesta no trae el formulario de TICA; posible desafío anti-bot",
        )
    try:
        estado = json.loads(html.unescape(hallado.group(1)))
    except ValueError as exc:
        raise ErrorTICA("formato_inesperado", "GXState ilegible") from exc
    if not isinstance(estado, dict):
        raise ErrorTICA("formato_inesperado", "GXState no es un objeto")
    return estado


def _filas(pagina: str) -> list[list[str]]:
    """Las filas de la grilla, del campo oculto `Grid2ContainerDataV`."""
    hallado = _RE_GRILLA.search(pagina)
    if hallado is None:
        raise ErrorTICA(
            "formato_inesperado",
            "la página no trae la grilla de resultados; ¿cambió el sitio?",
        )
    try:
        filas = json.loads(html.unescape(hallado.group(1)))
    except ValueError as exc:
        raise ErrorTICA("formato_inesperado", "grilla ilegible") from exc
    return [[str(celda).replace("\xa0", " ").strip() for celda in fila] for fila in filas]


def leer_fecha(texto: str) -> dt.date:
    """`18/09/26` → 2026-09-18. TICA escribe el año con dos dígitos."""
    return dt.datetime.strptime(texto.strip(), "%d/%m/%y").date()


def parsear_busqueda(pagina: str) -> list[Conocimiento]:
    """Las guías que devolvió la búsqueda, con su enlace a la madre.

    Las columnas salen del encabezado de la grilla medido el 28/09/2026. Los
    enlaces aparecen en el mismo orden que las filas, uno por fila.
    """
    enlaces = _RE_ENLACE_MADRE.findall(pagina)
    conocimientos = []
    for indice, fila in enumerate(_filas(pagina)):
        if len(fila) < 23:
            raise ErrorTICA("formato_inesperado", f"fila con {len(fila)} columnas, se esperaban 24")
        conocimientos.append(
            Conocimiento(
                numero=fila[8],
                tipo_documento=fila[11],
                manifiesto=fila[2],
                fecha_arribo=leer_fecha(fila[4]),
                deposito=fila[3],
                aduana_codigo=fila[14],
                aduana_nombre=fila[15],
                agente_ruc=fila[12],
                agente_nombre=fila[13],
                embarque_codigo=fila[17],
                embarque_nombre=fila[18],
                estado=fila[22],
                enlace_madre=enlaces[indice] if indice < len(enlaces) else None,
            )
        )
    return conocimientos


def parsear_madre(pagina: str) -> GuiaMadre | None:
    """La guía madre, de la página `hcgconspadre.aspx`."""
    filas = _filas(pagina)
    if not filas:
        return None
    fila = filas[0]
    if len(fila) < 15:
        raise ErrorTICA("formato_inesperado", f"guía madre con {len(fila)} columnas")
    return GuiaMadre(
        numero=fila[2],
        tipo_documento=fila[3],
        transportista_ruc=fila[4],
        transportista_nombre=fila[5],
        estado=fila[14],
    )


def clasificar_respuesta(estado: int) -> str | None:
    """Traduce el código HTTP a un motivo de `resiliencia`. `None` = sin fallo."""
    if estado == 200:
        return None
    if estado in (401, 403):
        # Akamai responde 403 cuando decide que la petición es de un bot. No se
        # insiste: se degrada la fuente y queda el motivo a la vista.
        return "acceso_bloqueado"
    if estado == 429:
        return "limite_de_tasa"
    if 300 <= estado < 400:
        # El sitio no redirige al consultar; una redirección es una página de
        # desafío o de error, no un resultado.
        return "acceso_bloqueado"
    return "error_del_servidor"


# --- El cliente -------------------------------------------------------------


class ClienteTICA:
    """Búsqueda de guías en el manifiesto de carga. No persiste nada."""

    def __init__(self, transporte: Transporte, base: str = BASE, pausa_s: float = PAUSA_S) -> None:
        self._transporte = transporte
        self._base = base if base.endswith("/") else base + "/"
        self._pausa_s = pausa_s
        self._peticiones = 0

    @property
    def peticiones(self) -> int:
        """Cuántas peticiones se hicieron. El script de verificación lo reporta."""
        return self._peticiones

    async def _pedir(self, metodo: str, ruta: str, datos: dict[str, str] | None = None) -> str:
        if self._peticiones and self._pausa_s:
            await asyncio.sleep(self._pausa_s)
        self._peticiones += 1
        respuesta = await self._transporte(metodo, self._base + ruta, datos=datos)
        motivo = clasificar_respuesta(respuesta.estado)
        if motivo is not None:
            raise ErrorTICA(motivo, f"{metodo} {ruta.split('?')[0]} → {respuesta.estado}")
        return respuesta.texto

    async def buscar(self, numero: str, desde: dt.date, hasta: dt.date) -> list[Conocimiento]:
        """Busca la guía entre dos fechas de arribo. Dos peticiones."""
        formulario = await self._pedir("GET", RUTA_BUSQUEDA)
        estado = extraer_estado(formulario)
        estado.update({"_EventName": EVENTO_BUSCAR, "_EventGridId": ID_GRILLA, "_EventRowId": ""})
        datos = {
            "vVFCH1": desde.strftime(_FORMATO_FECHA),
            "vVFCHF": hasta.strftime(_FORMATO_FECHA),
            "vCGNROCON": numero,
            "GXState": json.dumps(estado),
        }
        resultado = await self._pedir("POST", RUTA_BUSQUEDA, datos)
        # La página de resultados también es de TICA: si no trae el estado es
        # que en el medio apareció otra cosa.
        extraer_estado(resultado)
        return parsear_busqueda(resultado)

    async def guia_madre(self, conocimiento: Conocimiento) -> GuiaMadre | None:
        """La guía madre de una hija. Una petición, en la misma sesión."""
        if not conocimiento.enlace_madre:
            return None
        return parsear_madre(await self._pedir("GET", conocimiento.enlace_madre))

    async def rastrear(self, numero: str, desde: dt.date, hasta: dt.date) -> ResultadoRastreo:
        """Busca la guía y, si es hija, resuelve su madre. Tres peticiones como
        mucho; dos si no aparece, que es lo normal antes del arribo."""
        conocimientos = await self.buscar(numero, desde, hasta)
        if not conocimientos:
            return ResultadoRastreo(numero=numero)

        ultimo = max(conocimientos, key=lambda c: c.fecha_arribo)
        madre = await self.guia_madre(ultimo) if ultimo.es_hija else None
        payload: dict[str, Any] = {
            "fuente": "tica",
            "conocimientos": [_a_dict(c) for c in conocimientos],
            "madre": _a_dict(madre) if madre else None,
        }
        logger.info(
            "TICA: %s arribó el %s (manifiesto %s)%s.",
            numero,
            ultimo.fecha_arribo,
            ultimo.manifiesto,
            f", guía madre {madre.numero}" if madre else "",
        )
        return ResultadoRastreo(numero, tuple(conocimientos), madre, payload)


def _a_dict(dato: Conocimiento | GuiaMadre) -> dict[str, Any]:
    salida = {nombre: getattr(dato, nombre) for nombre in dato.__slots__}
    salida.pop("enlace_madre", None)  # caduca con la sesión: guardarlo no sirve
    return {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in salida.items()}


__all__ = [
    "BASE",
    "PAUSA_S",
    "USER_AGENT",
    "ClienteTICA",
    "Conocimiento",
    "ErrorTICA",
    "GuiaMadre",
    "Respuesta",
    "ResultadoRastreo",
    "Transporte",
    "clasificar_respuesta",
    "extraer_estado",
    "leer_fecha",
    "parsear_busqueda",
    "parsear_madre",
]
