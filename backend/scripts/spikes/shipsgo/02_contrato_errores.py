"""
Spike TASK-28 - ShipsGo - Fase 2: contrato de errores.

PREGUNTA DEL SPIKE QUE RESPONDE
    Como responde ShipsGo cuando algo sale mal, y cuanto cuesta equivocarse?
    El adaptador real (US-45/US-46) tiene que mapear cada error a una clase
    de fallo de US-03: permanente (no reintentar) o transitorio (reintentar).
    Aca se mide el mapa.

QUE PRUEBA
    Solo casos que fallan ANTES de crear un envio, para no gastar creditos:

    1. Sin token                         -> se espera 401
    2. Token invalido                    -> se espera 401 o 403
    3. Crear maritimo sin identificador  -> no hay nada que crear
    4. Crear maritimo con contenedor que viola el patron del esquema
    5. Crear aereo con AWB que viola el patron del esquema

    En cada uno se registran el status, el mensaje y los headers de saldo.
    El saldo se lee antes y despues para confirmar que ninguno cobro.

LO QUE NO SE PRUEBA A PROPOSITO
    Un contenedor con formato valido pero inexistente. Es la pregunta mas
    interesante (cobra o no un envio que no resuelve?), pero crearlo gasta
    un credito real. Se responde en la Fase 3 si una referencia real falla.

USO
    python backend/scripts/spikes/shipsgo/02_contrato_errores.py --network personal

SALIDA
    Codigo 0 si ningun caso creo un envio.
    Evidencia en backend/scripts/spikes/shipsgo/output/02_errores_<red>.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _comercial import TIMEOUT, cuerpo_json, imprimir_diag, llamar, parser_base  # noqa: E402
from _common import SEP, header, load_env, mask, require, save_evidence, utc_now  # noqa: E402

BASE = "https://api.shipsgo.com/v2"

CASOS: list[dict[str, Any]] = [
    {
        "nombre": "sin_token",
        "token": None,
        "metodo": "GET",
        "path": "/ocean/carriers",
        "params": {"take": 1},
        "esperado": "401",
    },
    {
        "nombre": "token_invalido",
        "token": "trackin-spike-token-invalido-0000",
        "metodo": "GET",
        "path": "/ocean/carriers",
        "params": {"take": 1},
        "esperado": "401 o 403",
    },
    {
        "nombre": "crear_maritimo_sin_identificador",
        "metodo": "POST",
        "path": "/ocean/shipments",
        "json": {"reference": "TRACKIN-SPIKE-ERR-1"},
        "esperado": "4xx de validacion, sin cobro",
    },
    {
        "nombre": "crear_maritimo_contenedor_mal_formado",
        "metodo": "POST",
        "path": "/ocean/shipments",
        "json": {"reference": "TRACKIN-SPIKE-ERR-2", "container_number": "ABC123"},
        "esperado": "4xx de validacion, sin cobro",
    },
    {
        "nombre": "crear_aereo_awb_mal_formado",
        "metodo": "POST",
        "path": "/air/shipments",
        "json": {"reference": "TRACKIN-SPIKE-ERR-3", "awb_number": "12345"},
        "esperado": "4xx de validacion, sin cobro",
    },
]


def leer_saldo(client: Any, auth: dict[str, str]) -> dict[str, str]:
    """Headers de saldo de una lectura gratuita; vacio si la API no los expone ahi."""
    _, diag = llamar(client, "GET", BASE + "/ocean/shipments", headers=auth, params={"take": 1})
    return diag.get("saldo") or {}


def main() -> int:
    args = parser_base("Spike TASK-28 ShipsGo Fase 2: contrato de errores").parse_args()
    env = load_env()
    token = require(env, "SHIPSGO_API_TOKEN")

    import httpx

    timestamp = header(
        "TrackIn - Spike TASK-28 - ShipsGo - Fase 2: contrato de errores",
        args.network,
        {"token": mask(token)},
    )

    resultados: list[dict[str, Any]] = []
    creados: list[dict[str, Any]] = []

    with httpx.Client(headers={"Accept": "application/json"}, timeout=TIMEOUT) as client:
        auth = {"X-Shipsgo-User-Token": token}
        saldo_antes = leer_saldo(client, auth)

        for caso in CASOS:
            cabeceras = dict(auth)
            if "token" in caso:
                cabeceras = {"X-Shipsgo-User-Token": caso["token"]} if caso["token"] else {}
            response, diag = llamar(
                client,
                caso["metodo"],
                BASE + caso["path"],
                headers=cabeceras,
                params=caso.get("params"),
                json=caso.get("json"),
            )
            diag["caso"] = caso["nombre"]
            diag["esperado"] = caso["esperado"]
            if response is not None:
                cuerpo = cuerpo_json(response)
                diag["mensaje"] = (
                    cuerpo.get("message") if isinstance(cuerpo, dict) else response.text[:300]
                )
                # Un caso que no deberia crear nada y devuelve un envio es la
                # alarma de esta fase: queda registrado para borrarlo a mano.
                if isinstance(cuerpo, dict) and cuerpo.get("shipment"):
                    creados.append({"caso": caso["nombre"], "shipment_id": cuerpo["shipment"].get("id")})
            imprimir_diag(diag, "CASO - " + caso["nombre"] + "  (esperado: " + caso["esperado"] + ")")
            if "mensaje" in diag:
                print("  Mensaje     : " + str(diag["mensaje"])[:200])
            resultados.append(diag)

        saldo_despues = leer_saldo(client, auth)

    print(SEP)
    print("  LECTURA")
    print(SEP)
    print("  Saldo antes  : " + (str(saldo_antes) if saldo_antes else "la API no lo expone en lecturas"))
    print("  Saldo despues: " + (str(saldo_despues) if saldo_despues else "la API no lo expone en lecturas"))
    print()
    print("  {:<40} {:<8} {}".format("Caso", "HTTP", "Mensaje"))
    for r in resultados:
        print("  {:<40} {:<8} {}".format(
            r["caso"], str(r.get("status_code", r.get("error_category"))), str(r.get("mensaje", ""))[:40]
        ))
    print()
    if creados:
        print("  [!!] ALGUN CASO CREO UN ENVIO. Revisar y borrarlo en el panel de ShipsGo:")
        for c in creados:
            print("       " + c["caso"] + " -> shipment_id " + str(c["shipment_id"]))
    else:
        print("  Ningun caso creo un envio. Para el adaptador de US-45/US-46:")
        print("  - 401/403 -> fallo PERMANENTE (credencial): degradar la fuente, no reintentar.")
        print("  - 4xx de validacion -> PERMANENTE por referencia: marcarla para revision.")
        print("  - 402 NOT_ENOUGH_CREDITS (documentado) -> PERMANENTE hasta recargar.")
        print("  - 409 ALREADY_EXISTS (documentado, 0 creditos) -> exito: usar el id devuelto.")
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "proveedor": "shipsgo",
        "phase": "2-contrato-errores",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "saldo_antes": saldo_antes,
        "saldo_despues": saldo_despues,
        "casos": resultados,
        "envios_creados_por_error": creados,
        "passed": not creados,
    }
    save_evidence("shipsgo", "02_errores_" + args.network + ".json", evidencia)
    return 0 if not creados else 1


if __name__ == "__main__":
    sys.exit(main())
