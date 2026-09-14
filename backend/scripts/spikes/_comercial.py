"""
Helpers compartidos por el spike TASK-28: fuentes comerciales de rastreo
(ShipsGo y TrackingMore).

POR QUE UN MODULO APARTE DE _common.py
    _common.py resuelve lo que necesitan todos los spikes: leer el .env,
    imprimir la cabecera y guardar la evidencia. Las fuentes comerciales
    agregan tres problemas que AISStream y OpenSky no tenian:

    1. Cobran por envio. Cada llamada registra el saldo que devuelva el
       proveedor, y ningun script gasta un credito sin --confirmar.
    2. Trabajan con referencias reales de embarques de Gutis. Esos numeros
       NO se suben al repositorio: viven en referencias.json (ignorado por
       git), las respuestas crudas van a output/raw/ (tambien ignorado) y la
       evidencia versionada los guarda enmascarados.
    3. Hay que comparar dos proveedores con las mismas referencias y contra
       la misma lista de navieras y aerolineas. Por eso la lista vive aca.

ORDEN DE EJECUCION
    Sin referencias (0 creditos):
        shipsgo/01_conectividad_catalogo.py   trackingmore/01_conectividad_catalogo.py
        shipsgo/02_contrato_errores.py        trackingmore/02_contrato_errores.py
    Con referencias (gasta creditos; sin --confirmar solo muestra el plan):
        shipsgo/03_crear_envios.py            trackingmore/03_consultar_awb.py
    Despues, varias veces al dia durante la semana (0 creditos):
        shipsgo/04_observar.py

ESTO NO ES CODIGO PRODUCTIVO. Vive en scripts/spikes/ y es descartable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import SPIKES_DIR, SUB, describe_http_error

REFERENCIAS_PATH = SPIKES_DIR / "referencias.json"
REFERENCIAS_EJEMPLO = SPIKES_DIR / "referencias.example.json"

TIMEOUT = 30.0

#: Tipos de referencia admitidos por via, segun el contrato de TASK-30. El
#: HAWB se admite solo para probar que NO resuelve (tercer criterio de TASK-28).
TIPOS_POR_VIA: dict[str, tuple[str, ...]] = {
    "MARITIMO": ("CONTENEDOR", "BL", "BOOKING"),
    "AEREO": ("MAWB", "HAWB"),
}


# ---------------------------------------------------------------------------
# Referencias de embarque
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Referencia:
    alias: str
    via: str
    tipo: str
    numero: str
    destino: str | None
    transportista: str | None
    notas: str | None

    @property
    def enmascarada(self) -> str:
        return enmascarar(self.numero, self.tipo)

    def resumen(self) -> dict[str, Any]:
        """Lo unico de la referencia que llega a la evidencia versionada."""
        return {
            "alias": self.alias,
            "via": self.via,
            "tipo": self.tipo,
            "numero_enmascarado": self.enmascarada,
            "destino": self.destino,
            "transportista": self.transportista,
        }


def enmascarar(numero: str, tipo: str) -> str:
    """
    Enmascara el numero conservando lo que sirve para leer la evidencia.

    Del contenedor queda el codigo de propietario (identifica la naviera) y
    del MAWB el prefijo de la aerolinea. El resto no hace falta para analizar.
    """
    digitos = re.sub(r"\D", "", numero)
    if tipo == "CONTENEDOR" and len(numero) == 11:
        return numero[:4] + "****" + numero[-3:]
    if tipo == "MAWB" and len(digitos) == 11:
        return digitos[:3] + "-*****" + digitos[-3:]
    if len(numero) <= 5:
        return "*" * len(numero)
    return numero[:3] + "*" * (len(numero) - 5) + numero[-2:]


def cargar_referencias() -> list[Referencia]:
    """
    Lee referencias.json. Aborta con instrucciones si no existe.

    Las entradas con placeholder o con via/tipo invalidos se descartan con
    aviso: preferimos correr con las buenas a abortar por una mal escrita.
    """
    if not REFERENCIAS_PATH.is_file():
        sys.exit(
            "[FATAL] No existe " + str(REFERENCIAS_PATH) + "\n"
            "        Copiar referencias.example.json a referencias.json y poner las\n"
            "        referencias reales. El archivo esta en .gitignore: los numeros\n"
            "        de embarques de Gutis no se suben al repositorio."
        )
    try:
        data = json.loads(REFERENCIAS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit("[FATAL] referencias.json no es JSON valido: " + str(exc))

    entradas = data.get("referencias", []) if isinstance(data, dict) else data
    referencias: list[Referencia] = []
    for i, entrada in enumerate(entradas, start=1):
        alias = str(entrada.get("alias") or "ref" + str(i)).strip()
        via = str(entrada.get("via") or "").strip().upper()
        tipo = str(entrada.get("tipo") or "").strip().upper()
        numero = re.sub(r"\s+", "", str(entrada.get("numero") or "")).upper()

        if not numero or numero.startswith("<"):
            print("  [!] referencias.json: '" + alias + "' sin numero real, se ignora")
            continue
        if via not in TIPOS_POR_VIA:
            print("  [!] referencias.json: '" + alias + "' via invalida " + repr(via))
            continue
        if tipo not in TIPOS_POR_VIA[via]:
            print(
                "  [!] referencias.json: '" + alias + "' tipo " + repr(tipo)
                + " no aplica a " + via + " (admitidos: " + ", ".join(TIPOS_POR_VIA[via]) + ")"
            )
            continue

        referencias.append(
            Referencia(
                alias=alias,
                via=via,
                tipo=tipo,
                numero=numero,
                destino=(str(entrada.get("destino") or "").strip().upper() or None),
                transportista=(str(entrada.get("transportista") or "").strip().upper() or None),
                notas=(str(entrada.get("notas") or "").strip() or None),
            )
        )

    if not referencias:
        sys.exit("[FATAL] referencias.json no tiene ninguna referencia utilizable.")
    return referencias


def filtrar_por_alias(referencias: list[Referencia], solo: list[str] | None) -> list[Referencia]:
    """Aplica --solo. Aborta si se pidio un alias que no existe."""
    if not solo:
        return referencias
    conocidos = {r.alias for r in referencias}
    faltan = [a for a in solo if a not in conocidos]
    if faltan:
        sys.exit("[FATAL] Alias inexistentes en referencias.json: " + ", ".join(faltan))
    return [r for r in referencias if r.alias in solo]


# --- Digitos de control: un numero mal copiado es un credito perdido --------

# ISO 6346: valor de cada letra, saltando los multiplos de 11.
_VALORES_ISO6346: dict[str, int] = {}
_valor = 10
for _letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if _valor % 11 == 0:
        _valor += 1
    _VALORES_ISO6346[_letra] = _valor
    _valor += 1


def problema_contenedor(numero: str) -> str | None:
    """None si el numero cumple ISO 6346, incluido el digito de control."""
    if not re.fullmatch(r"[A-Z]{4}\d{7}", numero):
        return "no tiene la forma 4 letras + 7 digitos"
    suma = 0
    for i, caracter in enumerate(numero[:10]):
        valor = _VALORES_ISO6346[caracter] if caracter.isalpha() else int(caracter)
        suma += valor * (2**i)
    esperado = suma % 11 % 10
    if esperado != int(numero[10]):
        return "digito de control ISO 6346 invalido (esperado " + str(esperado) + ")"
    return None


def problema_mawb(numero: str) -> str | None:
    """
    None si el MAWB tiene 11 digitos y su digito de control es correcto.

    El ultimo digito del serial de 8 es el resto de los 7 primeros entre 7.
    Un HAWB casi nunca lo cumple, lo que sirve de pista para detectarlo.
    """
    digitos = re.sub(r"\D", "", numero)
    if len(digitos) != 11:
        return "no tiene 11 digitos (prefijo de aerolinea + 8); puede ser un HAWB"
    serial = digitos[3:]
    esperado = int(serial[:7]) % 7
    if esperado != int(serial[7]):
        return "digito de control del serial invalido (esperado " + str(esperado) + "); puede ser un HAWB"
    return None


def problema_de_formato(ref: Referencia) -> str | None:
    if ref.tipo == "CONTENEDOR":
        return problema_contenedor(ref.numero)
    if ref.tipo == "MAWB":
        return problema_mawb(ref.numero)
    return None


def mawb_con_guion(numero: str) -> str:
    digitos = re.sub(r"\D", "", numero)
    return digitos[:3] + "-" + digitos[3:] if len(digitos) == 11 else numero


# ---------------------------------------------------------------------------
# Cobertura: navieras y aerolineas que interesan a Gutis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Objetivo:
    nombre: str
    patron: str  # regex sobre el texto del item, en mayusculas
    codigos: tuple[str, ...] = ()  # SCAC de la naviera o prefijo AWB de la aerolinea


#: Navieras con servicio al Caribe y al Pacifico de Costa Rica. Lista
#: TENTATIVA: reemplazarla por las que Gutis use de verdad en cuanto las pase
#: Planeacion. Las tres ultimas son regionales y las mas probables de faltar
#: en un agregador.
NAVIERAS_OBJETIVO: tuple[Objetivo, ...] = (
    Objetivo("Maersk", r"MAERSK", ("MAEU", "MAEI")),
    Objetivo("MSC", r"MEDITERRANEAN SHIPPING|\bMSC\b", ("MSCU", "MEDU")),
    Objetivo("CMA CGM", r"CMA[ -]?CGM", ("CMDU",)),
    Objetivo("Hapag-Lloyd", r"HAPAG", ("HLCU",)),
    Objetivo("Evergreen", r"EVERGREEN", ("EGLV",)),
    Objetivo("ONE", r"OCEAN NETWORK EXPRESS|\bONE\b", ("ONEY",)),
    Objetivo("ZIM", r"\bZIM\b", ("ZIMU",)),
    Objetivo("COSCO", r"COSCO", ("COSU",)),
    Objetivo("Hamburg Sud", r"HAMBURG S", ("SUDU",)),
    Objetivo("Crowley", r"CROWLEY", ("CMCU",)),
    Objetivo("Seaboard Marine", r"SEABOARD", ("SMLU",)),
    Objetivo("King Ocean", r"KING OCEAN", ()),
)

#: Aerolineas con carga en la ruta India/China/Europa/EE. UU. -> SJO, con su
#: prefijo AWB. Tambien TENTATIVA: el prefijo de los MAWB reales dira cuales
#: importan.
AEROLINEAS_OBJETIVO: tuple[Objetivo, ...] = (
    Objetivo("Lufthansa Cargo", r"LUFTHANSA", ("020",)),
    Objetivo("Qatar Airways Cargo", r"QATAR", ("157",)),
    Objetivo("Emirates SkyCargo", r"EMIRATES", ("176",)),
    Objetivo("Turkish Cargo", r"TURKISH", ("235",)),
    Objetivo("KLM Cargo", r"\bKLM\b", ("074",)),
    Objetivo("Air France Cargo", r"AIR FRANCE", ("057",)),
    Objetivo("Iberia Cargo", r"IBERIA", ("075",)),
    Objetivo("American Airlines Cargo", r"AMERICAN AIRLINES", ("001",)),
    Objetivo("United Cargo", r"UNITED AIRLINES|UNITED CARGO", ("016",)),
    Objetivo("Avianca", r"AVIANCA", ("134",)),
    Objetivo("Avianca Cargo (Tampa)", r"AVIANCA CARGO|TAMPA", ("729",)),
    Objetivo("Copa Airlines", r"\bCOPA\b", ("230",)),
    Objetivo("LATAM Cargo", r"LATAM|\bLAN\b", ("045",)),
    Objetivo("Aeromexico Cargo", r"AEROMEXICO|AEROMÉXICO", ("139",)),
    Objetivo("Cargolux", r"CARGOLUX", ("172",)),
    Objetivo("Atlas Air", r"ATLAS AIR", ("369",)),
    Objetivo("Cathay Pacific Cargo", r"CATHAY", ("160",)),
    Objetivo("China Southern", r"CHINA SOUTHERN", ("784",)),
    Objetivo("Air China Cargo", r"AIR CHINA", ("999",)),
    Objetivo("Singapore Airlines Cargo", r"SINGAPORE", ("618",)),
    Objetivo("Air India", r"AIR INDIA", ("098",)),
    Objetivo("Etihad Cargo", r"ETIHAD", ("607",)),
    Objetivo("UPS Airlines", r"\bUPS\b", ("406",)),
    Objetivo("FedEx", r"FEDEX|FEDERAL EXPRESS", ("023",)),
)


def texto_de(item: dict[str, Any]) -> str:
    """Texto buscable de un item de catalogo: sus valores escalares."""
    return " ".join(str(v) for v in item.values() if isinstance(v, (str, int))).upper()


def cobertura(
    catalogo: Iterable[dict[str, Any]],
    objetivos: Iterable[Objetivo],
    codigos_de: Callable[[dict[str, Any]], set[str]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Para cada objetivo, los items del catalogo que lo cubren.

    Coincide por codigo (SCAC o prefijo AWB) o por el nombre. El codigo es la
    senal fuerte; el nombre cubre los catalogos que no traen codigo.
    """
    items = list(catalogo)
    resultado: dict[str, list[dict[str, Any]]] = {}
    for objetivo in objetivos:
        patron = re.compile(objetivo.patron)
        resultado[objetivo.nombre] = [
            item
            for item in items
            if set(objetivo.codigos) & codigos_de(item) or patron.search(texto_de(item))
        ]
    return resultado


def imprimir_cobertura(resultado: dict[str, list[dict[str, Any]]], titulo: str) -> None:
    print(SUB)
    print("  " + titulo)
    print(SUB)
    for nombre, items in resultado.items():
        marca = "[SI]" if items else "[NO]"
        detalle = "; ".join(texto_de(i)[:60] for i in items[:3])
        print("  {:<26} {:<5} {}".format(nombre, marca, detalle))
    faltan = [n for n, items in resultado.items() if not items]
    print()
    print("  Cubiertas: " + str(len(resultado) - len(faltan)) + " de " + str(len(resultado)))
    if faltan:
        print("  Sin cobertura: " + ", ".join(faltan))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def cabeceras_saldo(response: Any) -> dict[str, str]:
    """Headers que hablan de creditos, cuota o limites. Se guardan todos."""
    return {
        k: v
        for k, v in response.headers.items()
        if any(t in k.lower() for t in ("credit", "quota", "limit", "remaining"))
    }


def llamar(client: Any, metodo: str, url: str, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
    """
    Hace la llamada y devuelve (response o None, diagnostico).

    El diagnostico nunca incluye el cuerpo completo: puede traer datos de
    embarques reales. Quien llama decide que guardar y donde.
    """
    diag: dict[str, Any] = {"metodo": metodo, "path": url.split("/v", 1)[-1]}
    inicio = time.perf_counter()
    try:
        response = client.request(metodo, url, **kwargs)
    except Exception as exc:  # noqa: BLE001 - queremos clasificar cualquier fallo
        categoria, explicacion = describe_http_error(exc)
        diag.update(
            ok=False,
            error_category=categoria,
            error_detail=explicacion,
            elapsed_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )
        return None, diag

    diag.update(
        ok=200 <= response.status_code < 300,
        status_code=response.status_code,
        elapsed_ms=round((time.perf_counter() - inicio) * 1000, 1),
        saldo=cabeceras_saldo(response),
    )
    return response, diag


def cuerpo_json(response: Any) -> Any:
    """El JSON de la respuesta, o None si no lo es (portal cautivo, proxy)."""
    try:
        return response.json()
    except ValueError:
        return None


def imprimir_diag(diag: dict[str, Any], titulo: str) -> None:
    print(SUB)
    print("  " + titulo)
    print(SUB)
    if diag.get("ok"):
        print("  Estado      : [OK] HTTP " + str(diag.get("status_code")))
    elif "status_code" in diag:
        print("  Estado      : [HTTP " + str(diag["status_code"]) + "]")
    else:
        print("  Estado      : [FALLO] " + str(diag.get("error_category")))
        print("  Detalle     : " + str(diag.get("error_detail")))
    print("  Latencia    : " + str(diag.get("elapsed_ms", "-")) + " ms")
    if diag.get("saldo"):
        print("  Saldo       : " + json.dumps(diag["saldo"]))


def guardar_crudo(subdir: str, nombre: str, data: Any) -> Path | None:
    """
    Guarda la respuesta cruda en scripts/spikes/<subdir>/output/raw/.

    Ese directorio esta en .gitignore: trae los numeros de embarque sin
    enmascarar. Sirve para analizar a mano y, cuando se escriba el adaptador
    real, como fixture de pruebas.
    """
    destino = SPIKES_DIR / subdir / "output" / "raw"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        archivo = destino / nombre
        archivo.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return archivo
    except OSError as exc:
        print("  [!] No se pudo guardar la respuesta cruda: " + str(exc))
        return None


def parser_base(descripcion: str) -> argparse.ArgumentParser:
    """Mismo --network obligatorio que los spikes TG-10 y TG-11."""
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument(
        "--network",
        choices=["personal", "gutis"],
        required=True,
        help="Red desde la que se ejecuta. Se estampa en la evidencia.",
    )
    return parser
