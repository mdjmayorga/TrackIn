"""
Spike TASK-28 - TrackingMore - Fase 1: conectividad, autenticacion y catalogo.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) Se puede consumir TrackingMore desde la red de Gutis? (A/B con --network)
    (2) Estan en su catalogo las navieras y aerolineas que usa Gutis?
    Sin gastar cuota: solo se leen listados.

QUE PRUEBA, EN ORDEN
    1. GET /v4/couriers/all - confirma la clave, mide latencia y trae el
       catalogo completo (unas 1 600 empresas, en su mayoria de paqueteria).
    2. GET /v4/trackings/get - lectura gratuita de los envios de la cuenta,
       para capturar headers de cuota si los expone.
    3. Cruce contra NAVIERAS_OBJETIVO y AEROLINEAS_OBJETIVO de _comercial.py.

OJO AL LEER LA COBERTURA
    El catalogo es de "couriers". Las aerolineas de carga pueden NO aparecer
    aunque /v4/awb las rastree, porque ese endpoint detecta la aerolinea por
    el prefijo del MAWB. Un [NO] en aerolineas no es concluyente; en navieras,
    si: sin la naviera en el catalogo no hay rastreo de contenedor.

USO
    python backend/scripts/spikes/trackingmore/01_conectividad_catalogo.py --network personal

SALIDA
    Codigo 0 si autentico y el catalogo respondio.
    Evidencia en backend/scripts/spikes/trackingmore/output/01_conectividad_<red>.json
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

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

BASE = "https://api.trackingmore.com/v4"


def main() -> int:
    args = parser_base("Spike TASK-28 TrackingMore Fase 1: conectividad y catalogo").parse_args()
    env = load_env()
    clave = require(env, "TRACKINGMORE_API_KEY")

    import httpx

    timestamp = header(
        "TrackIn - Spike TASK-28 - TrackingMore - Fase 1: conectividad y catalogo",
        args.network,
        {"api_key": mask(clave), "base": BASE},
    )

    with httpx.Client(
        headers={
            "Tracking-Api-Key": clave,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=TIMEOUT,
    ) as client:
        # --- Paso 1: autenticacion y catalogo ---------------------------------
        response, auth = llamar(client, "GET", BASE + "/couriers/all")
        imprimir_diag(auth, "PASO 1 - GET /v4/couriers/all (autenticacion + catalogo)")
        cuerpo = cuerpo_json(response) if response is not None else None
        meta = cuerpo.get("meta") if isinstance(cuerpo, dict) else None
        couriers = cuerpo.get("data") if isinstance(cuerpo, dict) else None
        couriers = couriers if isinstance(couriers, list) else []
        auth["meta"] = meta
        print("  Meta        : " + str(meta))
        print("  Couriers    : " + str(len(couriers)))

        # --- Paso 2: lectura gratuita de la cuenta ----------------------------
        response2, lectura = llamar(client, "GET", BASE + "/trackings/get")
        imprimir_diag(lectura, "PASO 2 - GET /v4/trackings/get (envios de la cuenta)")
        cuerpo2 = cuerpo_json(response2) if response2 is not None else None
        if isinstance(cuerpo2, dict):
            lectura["meta"] = cuerpo2.get("meta")
            print("  Meta        : " + str(cuerpo2.get("meta")))

    # Que tipos de empresa hay en el catalogo: dice si es un catalogo de
    # paqueteria con algo de carga, o si tiene navieras y aerolineas de verdad.
    tipos = Counter(str(c.get("courier_type") or c.get("type") or "-") for c in couriers)
    print()
    print("  Tipos en el catalogo: " + ", ".join(t + "=" + str(n) for t, n in tipos.most_common(10)))

    cob_navieras = cobertura(
        couriers, NAVIERAS_OBJETIVO, lambda c: {str(c.get("courier_code") or "").upper()}
    )
    imprimir_cobertura(cob_navieras, "PASO 3a - Navieras objetivo en el catalogo")
    cob_aerolineas = cobertura(couriers, AEROLINEAS_OBJETIVO, lambda _c: set())
    imprimir_cobertura(cob_aerolineas, "PASO 3b - Aerolineas objetivo (no concluyente, ver docstring)")

    passed = bool(auth.get("ok")) and bool(couriers)
    print(SEP)
    print("  LECTURA")
    print(SEP)
    if passed:
        print("  Fase 1 SUPERADA desde red " + args.network + ": la clave sirve y el catalogo")
        print("  respondio. Las navieras en [NO] no se pueden rastrear por contenedor aqui.")
    else:
        print("  Fase 1 NO superada: " + str(auth.get("status_code") or auth.get("error_category"))
              + " / meta " + str(meta))
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "proveedor": "trackingmore",
        "phase": "1-conectividad-catalogo",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "autenticacion": auth,
        "lectura_cuenta": lectura,
        "total_couriers": len(couriers),
        "tipos_en_catalogo": dict(tipos),
        "cobertura_navieras": cob_navieras,
        "cobertura_aerolineas": cob_aerolineas,
        "passed": passed,
    }
    save_evidence("trackingmore", "01_conectividad_" + args.network + ".json", evidencia)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
