"""
Spike TASK-28 - TrackingMore - Fase 2: contrato de errores.

PREGUNTA DEL SPIKE QUE RESPONDE
    Como responde TrackingMore cuando algo sale mal? Su API tiene dos capas de
    codigo: el HTTP y un meta.code propio (p. ej. 4101 "Tracking No. already
    exists"). El adaptador tiene que leer el segundo, no solo el primero.

QUE PRUEBA
    1. Sin clave                          -> se espera 401
    2. Clave invalida                     -> se espera 401
    3. Crear tracking sin campos          -> validacion, nada que crear

LO QUE NO SE PRUEBA A PROPOSITO
    /v4/awb con un numero mal formado. Cada consulta de AWB cuesta 50
    creditos y no sabemos si una rechazada cobra. No vale la pena el riesgo
    durante una prueba de 7 dias.

USO
    python backend/scripts/spikes/trackingmore/02_contrato_errores.py --network personal

SALIDA
    Evidencia en backend/scripts/spikes/trackingmore/output/02_errores_<red>.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _comercial import TIMEOUT, cuerpo_json, imprimir_diag, llamar, parser_base  # noqa: E402
from _common import SEP, header, load_env, mask, require, save_evidence, utc_now  # noqa: E402

BASE = "https://api.trackingmore.com/v4"


def main() -> int:
    args = parser_base("Spike TASK-28 TrackingMore Fase 2: contrato de errores").parse_args()
    env = load_env()
    clave = require(env, "TRACKINGMORE_API_KEY")

    import httpx

    timestamp = header(
        "TrackIn - Spike TASK-28 - TrackingMore - Fase 2: contrato de errores",
        args.network,
        {"api_key": mask(clave)},
    )

    casos: list[dict[str, Any]] = [
        {"nombre": "sin_clave", "clave": None, "metodo": "GET", "path": "/couriers/all",
         "esperado": "401"},
        {"nombre": "clave_invalida", "clave": "trackin-spike-clave-invalida-0000", "metodo": "GET",
         "path": "/couriers/all", "esperado": "401"},
        {"nombre": "crear_tracking_sin_campos", "clave": clave, "metodo": "POST",
         "path": "/trackings/create", "json": {}, "esperado": "4xx de validacion"},
    ]

    resultados: list[dict[str, Any]] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for caso in casos:
            cabeceras = {"Accept": "application/json", "Content-Type": "application/json"}
            if caso["clave"]:
                cabeceras["Tracking-Api-Key"] = caso["clave"]
            response, diag = llamar(
                client, caso["metodo"], BASE + caso["path"], headers=cabeceras, json=caso.get("json")
            )
            diag["caso"] = caso["nombre"]
            diag["esperado"] = caso["esperado"]
            cuerpo = cuerpo_json(response) if response is not None else None
            if isinstance(cuerpo, dict):
                diag["meta"] = cuerpo.get("meta")
            elif response is not None:
                diag["cuerpo_texto"] = response.text[:300]
            imprimir_diag(diag, "CASO - " + caso["nombre"] + "  (esperado: " + caso["esperado"] + ")")
            print("  Meta        : " + str(diag.get("meta") or diag.get("cuerpo_texto")))
            resultados.append(diag)

    print(SEP)
    print("  LECTURA")
    print(SEP)
    print("  {:<30} {:<8} {}".format("Caso", "HTTP", "meta"))
    for r in resultados:
        print("  {:<30} {:<8} {}".format(
            r["caso"], str(r.get("status_code", r.get("error_category"))), str(r.get("meta"))[:60]
        ))
    print()
    print("  Para el adaptador: el HTTP no basta, hay que clasificar por meta.code.")
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "proveedor": "trackingmore",
        "phase": "2-contrato-errores",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "casos": resultados,
    }
    save_evidence("trackingmore", "02_errores_" + args.network + ".json", evidencia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
