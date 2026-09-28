"""Spike TICA — captura las respuestas reales para las pruebas de `tica_cliente`.

    python scripts/spikes/tica/01_capturar_respuestas.py ZIVHYD017 01/08/2026 28/09/2026

Hace **cuatro peticiones** y ninguna más: el formulario, la búsqueda de la guía
pedida, su guía madre y una búsqueda de una guía inexistente (para tener el caso
vacío). Todas públicas, sin usuario, con un `User-Agent` que dice quién pregunta.

Guarda el HTML tal cual en `output/`. Es evidencia de cómo responde TICA el día
de la captura: si el sitio cambia, las pruebas siguen describiendo lo medido y
este script vuelve a capturar.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import httpx

BASE = "https://ticaconsultas.hacienda.go.cr/Tica/"
SALIDA = Path(__file__).resolve().parent / "output"
UA = {"User-Agent": "TrackIn/0.1 (Laboratorios Gutis; consulta de guias propias)"}


def _estado(pagina: str) -> dict:
    hallado = re.search(r"name=\"GXState\" value='(.*?)'", pagina, re.S)
    return json.loads(html.unescape(hallado.group(1)))


def _buscar(cliente: httpx.Client, guia: str, desde: str, hasta: str) -> str:
    formulario = cliente.get(BASE + "hcgconocimientos.aspx").text
    estado = _estado(formulario)
    estado.update({"_EventName": "EENTER.", "_EventGridId": "41", "_EventRowId": ""})
    datos = {"vVFCH1": desde, "vVFCHF": hasta, "vCGNROCON": guia, "GXState": json.dumps(estado)}
    return cliente.post(BASE + "hcgconocimientos.aspx", data=datos).text


def main() -> None:
    guia, desde, hasta = sys.argv[1:4]
    SALIDA.mkdir(exist_ok=True)
    with httpx.Client(timeout=30, headers=UA) as cliente:
        resultado = _buscar(cliente, guia, desde, hasta)
        (SALIDA / "02_busqueda_hawb.html").write_text(resultado, encoding="utf-8")

        enlace = re.search(r"hcgconspadre\.aspx\?[A-Za-z0-9+/=]+", resultado)
        if enlace:
            madre = cliente.get(BASE + enlace.group(0)).text
            (SALIDA / "03_guia_madre.html").write_text(madre, encoding="utf-8")

        vacio = _buscar(cliente, "NOEXISTE0000", desde, hasta)
        (SALIDA / "04_busqueda_vacia.html").write_text(vacio, encoding="utf-8")
    print("Capturado en", SALIDA)


if __name__ == "__main__":
    main()
