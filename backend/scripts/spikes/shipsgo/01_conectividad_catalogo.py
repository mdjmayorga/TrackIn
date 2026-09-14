"""
Spike TASK-28 - ShipsGo - Fase 1: conectividad, autenticacion y catalogo.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) Se puede consumir ShipsGo desde la red de Gutis? (A/B con --network)
    (2) Estan en su catalogo las navieras y aerolineas que usa Gutis?
    Todo sin gastar un credito: solo se leen listados.

QUE PRUEBA, EN ORDEN
    1. GET /ocean/shipments?take=1 - confirma el token y captura los headers
       de saldo, si la API los expone fuera de la creacion.
    2. GET /ocean/carriers paginado - catalogo completo de navieras.
    3. GET /air/airlines paginado - catalogo completo de aerolineas, con sus
       prefijos AWB.
    4. Cruce contra NAVIERAS_OBJETIVO y AEROLINEAS_OBJETIVO de _comercial.py.

POR QUE EL CATALOGO VA ANTES QUE LAS REFERENCIAS
    Si Crowley o Seaboard no estan en el catalogo, un contenedor suyo no
    resuelve por bueno que sea. Saberlo antes cuesta cero; descubrirlo al
    crear el envio cuesta uno de los tres creditos gratuitos.

USO
    python backend/scripts/spikes/shipsgo/01_conectividad_catalogo.py --network personal

SALIDA
    Codigo 0 si autentico y los dos catalogos respondieron.
    Evidencia en backend/scripts/spikes/shipsgo/output/01_conectividad_<red>.json
    (el catalogo es informacion publica del proveedor, sin datos de Gutis).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _comercial import (  # noqa: E402
    AEROLINEAS_OBJETIVO,
    NAVIERAS_OBJETIVO,
    TIMEOUT,
    cobertura,
    cuerpo_json,
    imprimir_cobertura,
    imprimir_diag,
    llamar,
    parser_base,
)
from _common import SEP, header, load_env, mask, require, save_evidence, utc_now  # noqa: E402

BASE = "https://api.shipsgo.com/v2"
PAGINA = 100  # maximo que admite el parametro take
TOPE_ITEMS = 5000  # defensa contra un meta.more que nunca se apague


def paginar(client: Any, path: str, clave: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recorre un listado con skip/take hasta que meta.more sea falso."""
    items: list[dict[str, Any]] = []
    diags: list[dict[str, Any]] = []
    skip = 0
    while skip < TOPE_ITEMS:
        response, diag = llamar(client, "GET", BASE + path, params={"skip": skip, "take": PAGINA})
        diags.append(diag)
        if response is None or not diag["ok"]:
            break
        cuerpo = cuerpo_json(response) or {}
        lote = cuerpo.get(clave) or []
        items.extend(lote)
        if not (cuerpo.get("meta") or {}).get("more") or not lote:
            break
        skip += len(lote)
    return items, diags


def prefijos(item: dict[str, Any]) -> set[str]:
    """Los prefijos AWB de una aerolinea, vengan como lista o como texto."""
    crudo = item.get("prefixes")
    if isinstance(crudo, list):
        return {str(p).zfill(3) for p in crudo}
    if isinstance(crudo, (str, int)):
        return {p.zfill(3) for p in re.findall(r"\d+", str(crudo))}
    return set()


def main() -> int:
    args = parser_base("Spike TASK-28 ShipsGo Fase 1: conectividad y catalogo").parse_args()
    env = load_env()
    token = require(env, "SHIPSGO_API_TOKEN")

    import httpx

    timestamp = header(
        "TrackIn - Spike TASK-28 - ShipsGo - Fase 1: conectividad y catalogo",
        args.network,
        {"token": mask(token), "base": BASE},
    )

    with httpx.Client(
        headers={"X-Shipsgo-User-Token": token, "Accept": "application/json"},
        timeout=TIMEOUT,
    ) as client:
        # --- Paso 1: autenticacion --------------------------------------------
        response, auth = llamar(client, "GET", BASE + "/ocean/shipments", params={"take": 1})
        imprimir_diag(auth, "PASO 1 - GET /ocean/shipments?take=1 (autenticacion)")
        envios_existentes = None
        if response is not None and auth["ok"]:
            cuerpo = cuerpo_json(response) or {}
            envios_existentes = len(cuerpo.get("shipments") or [])
            print("  Envios      : " + str(envios_existentes) + " en la primera pagina de la cuenta")
        elif response is not None:
            auth["cuerpo"] = response.text[:300]
            print("  Respuesta   : " + response.text[:200])

        # --- Paso 2 y 3: catalogos --------------------------------------------
        navieras, diags_navieras = paginar(client, "/ocean/carriers", "carriers")
        imprimir_diag(diags_navieras[0], "PASO 2 - GET /ocean/carriers (primera pagina)")
        print("  Navieras    : " + str(len(navieras)) + " en " + str(len(diags_navieras)) + " paginas")

        aerolineas, diags_aerolineas = paginar(client, "/air/airlines", "airlines")
        imprimir_diag(diags_aerolineas[0], "PASO 3 - GET /air/airlines (primera pagina)")
        print("  Aerolineas  : " + str(len(aerolineas)) + " en " + str(len(diags_aerolineas)) + " paginas")

    # --- Paso 4: cobertura ----------------------------------------------------
    cob_navieras = cobertura(
        navieras, NAVIERAS_OBJETIVO, lambda i: {str(i.get("scac") or "").upper()}
    )
    imprimir_cobertura(cob_navieras, "PASO 4a - Navieras objetivo (lista tentativa)")
    cob_aerolineas = cobertura(aerolineas, AEROLINEAS_OBJETIVO, prefijos)
    imprimir_cobertura(cob_aerolineas, "PASO 4b - Aerolineas objetivo (lista tentativa)")

    # Una naviera puede estar en el catalogo pero inactiva: eso tambien importa.
    estados = sorted({str(i.get("status")) for i in navieras + aerolineas})
    print()
    print("  Valores de 'status' en los catalogos: " + ", ".join(estados))

    # --- Lectura ------------------------------------------------------------------
    passed = bool(auth.get("ok")) and bool(navieras) and bool(aerolineas)
    print(SEP)
    print("  LECTURA")
    print(SEP)
    if passed:
        print("  Fase 1 SUPERADA desde red " + args.network + ": el token sirve y los dos")
        print("  catalogos respondieron. Revisar arriba las navieras y aerolineas en [NO]")
        print("  ANTES de gastar creditos con referencias de esos transportistas.")
    elif not auth.get("ok"):
        print("  Fase 1 NO superada: la autenticacion fallo ("
              + str(auth.get("status_code") or auth.get("error_category")) + ").")
        print("  401/403 apunta al token; un error de red, a la red. Comparar con la otra red.")
    else:
        print("  Fase 1 NO superada: autentico, pero algun catalogo vino vacio.")
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "proveedor": "shipsgo",
        "phase": "1-conectividad-catalogo",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "autenticacion": auth,
        "envios_en_primera_pagina": envios_existentes,
        "llamadas_catalogo_navieras": diags_navieras,
        "llamadas_catalogo_aerolineas": diags_aerolineas,
        "total_navieras": len(navieras),
        "total_aerolineas": len(aerolineas),
        "cobertura_navieras": {k: v for k, v in cob_navieras.items()},
        "cobertura_aerolineas": {k: v for k, v in cob_aerolineas.items()},
        "catalogo_navieras": navieras,
        "catalogo_aerolineas": aerolineas,
        "passed": passed,
    }
    save_evidence("shipsgo", "01_conectividad_" + args.network + ".json", evidencia)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
